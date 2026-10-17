"""
Soil Sentinel - Portable Prediction Interface.

Provides a unified, deterministic prediction interface for the
Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index.

Supports:
1. Single feature record prediction (`predict_record`).
2. Batch DataFrame prediction (`predict_dataframe`).
3. CLI / CSV workflow reading `data/feature_table.csv` and saving to `outputs/predictions.csv`.
4. Lightweight, portable audit logging via `src.Model.audit_log`.

CRITICAL CONSTRAINTS & PORTABILITY:
- Uses ONLY the deterministic baseline scoring system from `src.Model.risk_scoring`.
- Does NOT load, deserialize, or touch `models/soil_risk_model.joblib`.
- Pure Python 3.10+, NumPy, and Pandas. Designed for portability to IBM LinuxONE (s390x).
- Does NOT modify `data/feature_table.csv`.
- Preserves explicit missing-history handling (strict vs permissive modes).
- Avoids duplicate audit log entries by maintaining a single logging point per execution.
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Model.risk_scoring import (
    calculate_baseline_risk_score,
    RiskScoringResult,
    INDEX_NAME,
    ASSUMPTIONS_LABEL,
)
from src.Model.audit_log import (
    DEFAULT_AUDIT_LOG_PATH,
    log_prediction_single,
    log_predictions_batch,
)

logger = logging.getLogger("predict")

# Essential features required in feature records for evaluation
REQUIRED_FEATURE_COLUMNS = [
    "soil_moisture_rootzone_fraction",
    "soil_temperature_layer1_c",
    "topsoil_soc_g_kg",
    "topsoil_ph_mean",
]

# Standard identifier fields to preserve in predictions if present
IDENTIFIER_COLUMNS = [
    "region",
    "nominal_latitude",
    "nominal_longitude",
    "sampled_latitude",
    "sampled_longitude",
    "year",
    "month",
    "date",
    "season",
]


def predict_record(
    record: Union[Dict[str, Any], pd.Series],
    allow_partial: bool = True,
    audit_log_path: Optional[Union[str, Path]] = None,
    source_id: str = "feature_record"
) -> Dict[str, Any]:
    """
    Predict the Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index
    for a single feature record.

    Parameters:
        record: Dictionary or pd.Series with feature names and values.
        allow_partial: If True, uses single-month precipitation fallback when
                       3-month rolling mean is unobserved (e.g. at sequence start).
                       If False (strict mode), returns INSUFFICIENT_HISTORY with score=None.
        audit_log_path: Optional path to append an audit entry for this single prediction.
                        Defaults to None (skipped unless explicitly requested).
        source_id: Source label for audit tracking.

    Returns:
        Flattened dictionary containing identifiers, index name, score, category,
        status, sub-scores, buffering details, and explanation.
    """
    res: RiskScoringResult = calculate_baseline_risk_score(record, allow_partial=allow_partial)

    # Base output dictionary
    out: Dict[str, Any] = {}

    def _sanitize_val(v: Any) -> Any:
        if v is None:
            return None
        try:
            if not isinstance(v, (list, dict, tuple)) and pd.isna(v):
                return None
        except Exception:
            if isinstance(v, (float, np.floating)) and np.isnan(v):
                return None
        return v

    # 1. Preserve identifier fields if present in input record
    for id_col in IDENTIFIER_COLUMNS:
        if id_col in record:
            out[id_col] = _sanitize_val(record[id_col])

    # 2. Core Index Results
    out["index_name"] = INDEX_NAME
    out["score"] = res.score
    out["risk_category"] = res.risk_category
    out["status"] = res.status
    out["dynamic_environmental_stress"] = res.dynamic_environmental_stress
    out["baseline_soil_vulnerability"] = res.baseline_soil_vulnerability

    # 3. Contributing Indicators (Sub-scores & Buffering Details)
    ind = res.indicators
    if ind:
        out["moisture_deficit_sub_score"] = ind.get("moisture_deficit", {}).get("sub_score")
        out["precipitation_deficit_sub_score"] = ind.get("precipitation_deficit", {}).get("sub_score")
        out["precipitation_deficit_raw_unbuffered"] = ind.get("precipitation_deficit", {}).get("raw_unbuffered_score")
        out["moisture_buffering_factor"] = ind.get("precipitation_deficit", {}).get("moisture_buffering_factor")
        out["thermal_stress_sub_score"] = ind.get("thermal_stress", {}).get("sub_score")
        out["soc_vulnerability_sub_score"] = ind.get("soc_vulnerability", {}).get("sub_score")
        out["ph_deviation_sub_score"] = ind.get("ph_deviation", {}).get("sub_score")
    else:
        out["moisture_deficit_sub_score"] = None
        out["precipitation_deficit_sub_score"] = None
        out["precipitation_deficit_raw_unbuffered"] = None
        out["moisture_buffering_factor"] = None
        out["thermal_stress_sub_score"] = None
        out["soc_vulnerability_sub_score"] = None
        out["ph_deviation_sub_score"] = None

    # 4. Contextual Raw Physical Features (if available)
    raw_keys = [
        "soil_moisture_rootzone_fraction",
        "precipitation_rolling_3m_mean_mm_day",
        "precipitation_mm_day",
        "soil_temperature_layer1_c",
        "topsoil_soc_g_kg",
        "topsoil_ph_mean",
    ]
    for rk in raw_keys:
        if rk in record:
            out[rk] = _sanitize_val(record[rk])

    # 5. Metadata and Explanations
    out["explanation"] = res.explanation
    out["assumptions_label"] = ASSUMPTIONS_LABEL

    # 6. Audit Logging for Single-Record Prediction (if enabled)
    if audit_log_path is not None:
        log_prediction_single(
            prediction=out,
            source_id=source_id,
            allow_partial=allow_partial,
            log_path=audit_log_path
        )

    return out


def predict_dataframe(
    df: pd.DataFrame,
    allow_partial: bool = True,
    audit_log_path: Optional[Union[str, Path]] = None,
    source_id: str = "dataframe"
) -> pd.DataFrame:
    """
    Predict the Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index
    for every row in an existing feature DataFrame.

    Parameters:
        df: Input DataFrame conforming to feature table schema.
        allow_partial: True for permissive boundary fallback mode;
                       False for strict abort on missing rolling history.
        audit_log_path: Optional path to write audit entries for every record in the batch.
                        Defaults to None. When provided, batch audit logging is performed once.
        source_id: Identifier for audit tracking.

    Returns:
        Structured predictions DataFrame.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected pandas DataFrame, got {type(df).__name__}")

    if df.empty:
        raise ValueError("Cannot predict on an empty DataFrame (0 rows).")

    # Validate presence of essential required feature columns
    missing_cols = [c for c in REQUIRED_FEATURE_COLUMNS if c not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Input DataFrame is missing required feature column(s): {missing_cols}. "
            f"Required columns are: {REQUIRED_FEATURE_COLUMNS}"
        )

    records: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        # Do not log inside predict_record to avoid duplicate entries during batch processing
        pred_dict = predict_record(row, allow_partial=allow_partial, audit_log_path=None)
        records.append(pred_dict)

    df_preds = pd.DataFrame(records)

    # Single point of audit logging for batch prediction
    if audit_log_path is not None:
        log_predictions_batch(
            predictions=records,
            source_id=source_id,
            allow_partial=allow_partial,
            log_path=audit_log_path
        )

    return df_preds


def predict_from_csv(
    input_path: Union[str, Path] = "data/feature_table.csv",
    output_path: Optional[Union[str, Path]] = "outputs/predictions.csv",
    allow_partial: bool = True,
    audit_log_path: Optional[Union[str, Path]] = DEFAULT_AUDIT_LOG_PATH
) -> pd.DataFrame:
    """
    Read feature table CSV, compute index predictions, record audit log, and optionally save to CSV.

    Parameters:
        input_path: Path to input feature table CSV.
        output_path: Path to output predictions CSV (created only if needed).
                     If None, output is not written to disk.
        allow_partial: If True, allows single-month fallback for initial boundary NaNs.
        audit_log_path: Path to audit log CSV. Defaults to 'logs/audit_log.csv'.
                        If None, audit logging is disabled.

    Returns:
        Predictions DataFrame.
    """
    inp = Path(input_path)
    if not inp.is_absolute():
        inp = PROJECT_ROOT / inp

    if not inp.exists():
        raise FileNotFoundError(f"Feature table input file not found: {inp}")

    # Guard: Do not allow accidental overwrite of source feature table
    if output_path is not None:
        out_p = Path(output_path)
        if not out_p.is_absolute():
            out_p = PROJECT_ROOT / out_p
        if inp.resolve() == out_p.resolve():
            raise ValueError(
                f"Output path cannot be identical to input path ({inp}). "
                "Overwriting the source feature table is prohibited."
            )

    logger.info("Reading feature table from %s", inp)
    df_features = pd.read_csv(inp)

    source_label = inp.name if inp.is_file() else str(inp)
    logger.info("Computing predictions across %d records (allow_partial=%s)...", len(df_features), allow_partial)

    # Perform batch prediction and single-point audit logging
    df_preds = predict_dataframe(
        df_features,
        allow_partial=allow_partial,
        audit_log_path=audit_log_path,
        source_id=source_label
    )

    if output_path is not None:
        out_p = Path(output_path)
        if not out_p.is_absolute():
            out_p = PROJECT_ROOT / out_p
        out_p.parent.mkdir(parents=True, exist_ok=True)
        df_preds.to_csv(out_p, index=False)
        logger.info("Predictions successfully written to %s (shape: %s)", out_p, df_preds.shape)

    return df_preds


def main():
    """Command-line interface for the SoilSentinel Prediction Engine with Audit Logging."""
    parser = argparse.ArgumentParser(
        description="Soil Sentinel - Portable Prediction Interface (Deterministic Scoring)"
    )
    parser.add_argument(
        "--input", "-i",
        default="data/feature_table.csv",
        help="Path to feature table CSV (default: data/feature_table.csv)"
    )
    parser.add_argument(
        "--output", "-o",
        default="outputs/predictions.csv",
        help="Path to output predictions CSV (default: outputs/predictions.csv)"
    )
    parser.add_argument(
        "--audit-log", "-a",
        default=DEFAULT_AUDIT_LOG_PATH,
        help=f"Path to audit log CSV (default: {DEFAULT_AUDIT_LOG_PATH})"
    )
    parser.add_argument(
        "--no-audit",
        action="store_true",
        help="Disable prediction audit logging"
    )
    parser.add_argument(
        "--strict", "-s",
        action="store_true",
        help="Enable strict mode (reject missing 3-month rolling history with INSUFFICIENT_HISTORY instead of fallback)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress console summary output"
    )

    args = parser.parse_args()
    allow_partial = not args.strict
    audit_log_path = None if args.no_audit else args.audit_log

    try:
        df_preds = predict_from_csv(
            input_path=args.input,
            output_path=args.output,
            allow_partial=allow_partial,
            audit_log_path=audit_log_path
        )
    except Exception as e:
        print(f"Error executing prediction: {e}", file=sys.stderr)
        sys.exit(1)

    if not args.quiet:
        print("=====================================================================")
        print("Soil Sentinel - Seasonal Hydro-Thermal Stress & Baseline Vulnerability")
        print("Prediction Engine Execution Summary")
        print("=====================================================================")
        print(f"Input file:     {args.input}")
        print(f"Output file:    {args.output}")
        if audit_log_path:
            print(f"Audit log:      {audit_log_path}")
        else:
            print("Audit log:      Disabled")
        print(f"Mode:           {'Strict (allow_partial=False)' if args.strict else 'Permissive (allow_partial=True)'}")
        print(f"Total rows:     {len(df_preds)}")
        
        valid_scores = df_preds["score"].dropna()
        if not valid_scores.empty:
            print(f"Score range:    {valid_scores.min():.2f} to {valid_scores.max():.2f}")
            print(f"Score mean:     {valid_scores.mean():.2f}")
            print(f"Score median:   {valid_scores.median():.2f}")

        print("\nCounts by Risk Category:")
        print(df_preds["risk_category"].value_counts(dropna=False).to_string())

        print("\nCounts by Calculation Status:")
        print(df_preds["status"].value_counts(dropna=False).to_string())
        print("=====================================================================")


if __name__ == "__main__":
    main()
