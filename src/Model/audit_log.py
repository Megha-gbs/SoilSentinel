"""
Soil Sentinel - Portable Prediction Audit Logging Module.

Provides lightweight, append-only audit logging for predictions of the
Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index.

Key Properties:
1. Portable: Pure standard library (csv, datetime, pathlib, typing). Zero external dependencies.
2. Standardized: Standard ISO 8601 UTC timestamps, explicit calculation status,
   and preservation of null/UNKNOWN values for strict-mode records.
3. Privacy & Safety: No PII, no credentials, no entire raw records stored.
4. Duplicate Prevention: Single point of logging integration.
5. IBM LinuxONE (s390x) Compatible: Architecture-independent text CSV writing.
"""

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Ensure project root resolution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

logger = logging.getLogger("audit_log")

# Scoring engine implementation version
ENGINE_VERSION = "v1.0.0-baseline"
INDEX_NAME = "Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index"
OUTLOOK_INDEX_NAME = "Provisional Hydro-Thermal Stress Outlook"
DEFAULT_AUDIT_LOG_PATH = "logs/audit_log.csv"

# Exact standard audit log CSV fieldnames
AUDIT_LOG_FIELDS = [
    "timestamp_utc",
    "assessment_id",
    "input_date",
    "location_id",
    "index_name",
    "engine_version",
    "source_id",
    "allow_partial",
    "status",
    "score",
    "risk_category",
    "recommendation_ids",
]

LEGACY_AUDIT_LOG_FIELDS = [
    "timestamp_utc",
    "input_date",
    "location_id",
    "index_name",
    "engine_version",
    "source_id",
    "allow_partial",
    "status",
    "score",
    "risk_category",
]


def resolve_log_path(log_path: Union[str, Path]) -> Path:
    """Resolve log path relative to PROJECT_ROOT if not absolute."""
    p = Path(log_path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p


def create_audit_entry(
    prediction: Dict[str, Any],
    source_id: str = "feature_record",
    allow_partial: bool = True,
    timestamp: Optional[datetime] = None,
    assessment_id: Optional[str] = None,
    recommendation_ids: Optional[Union[List[str], str]] = None,
) -> Dict[str, Any]:
    """
    Construct a validated, single audit log entry dictionary.

    Parameters:
        prediction: Prediction result dictionary (from predict_record).
        source_id: Input filename or dataset source identifier.
        allow_partial: Whether partial-history fallback was enabled.
        timestamp: Optional datetime; defaults to current UTC time.
        assessment_id: Optional assessment run identifier.
        recommendation_ids: Optional list or string of recommendation identifiers.

    Returns:
        Dictionary conforming to AUDIT_LOG_FIELDS.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    elif timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    # Format timestamp as ISO 8601 string with UTC indicator
    ts_str = timestamp.isoformat()

    # Resolve assessment_id
    resolved_assessment_id = (
        assessment_id
        or prediction.get("assessment_id")
        or ""
    )

    # Format recommendation_ids as clean semicolon-delimited string
    resolved_rec_ids = (
        recommendation_ids
        if recommendation_ids is not None
        else prediction.get("recommendation_ids")
    )
    if isinstance(resolved_rec_ids, (list, tuple, set)):
        rec_ids_str = ";".join(str(r).strip() for r in resolved_rec_ids if str(r).strip())
    elif resolved_rec_ids is not None:
        rec_ids_str = str(resolved_rec_ids).strip()
    else:
        rec_ids_str = ""

    # Extract date identifier (supports prediction date, forecast start date, or scenario)
    input_date = str(
        prediction.get("date")
        or prediction.get("forecast_start_date")
        or prediction.get("scenario_name")
        or "UNKNOWN"
    )

    # Extract location identifier (explicit location_id, region name, coordinates, or fallback)
    location_id = prediction.get("location_id") or prediction.get("region")
    if not location_id:
        lat = (
            prediction.get("sampled_latitude")
            or prediction.get("nominal_latitude")
            or prediction.get("latitude")
        )
        lon = (
            prediction.get("sampled_longitude")
            or prediction.get("nominal_longitude")
            or prediction.get("longitude")
        )
        if lat is not None and lon is not None:
            location_id = f"{lat},{lon}"
        else:
            location_id = "UNKNOWN"

    status = str(prediction.get("status") or "UNKNOWN")
    score_val = prediction.get("score")
    if score_val is not None and score_val != "":
        try:
            f_score = float(score_val)
            if f_score == f_score:  # check for NaN
                score_str = f"{f_score:.2f}"
            else:
                score_str = ""
        except (ValueError, TypeError):
            score_str = ""
    else:
        score_str = ""  # Explicit empty string for null score

    risk_cat = str(prediction.get("risk_category") or "UNKNOWN")
    index_name = str(prediction.get("index_name") or INDEX_NAME)
    engine_ver = str(prediction.get("engine_version") or ENGINE_VERSION)

    entry = {
        "timestamp_utc": ts_str,
        "assessment_id": str(resolved_assessment_id),
        "input_date": input_date,
        "location_id": str(location_id),
        "index_name": index_name,
        "engine_version": engine_ver,
        "source_id": str(source_id),
        "allow_partial": bool(allow_partial),
        "status": status,
        "score": score_str,
        "risk_category": risk_cat,
        "recommendation_ids": rec_ids_str,
    }
    return entry


def migrate_legacy_audit_log(p: Path) -> None:
    """
    Safely upgrades an existing legacy 10-column audit log to the 12-column schema
    in-place, preserving all historical records and populating empty strings for
    absent assessment_id and recommendation_ids.
    """
    if not p.exists() or p.stat().st_size == 0:
        return
    with open(p, mode="r", newline="", encoding="utf-8") as f:
        reader = list(csv.reader(f))
    if not reader:
        return
    header = reader[0]
    if "assessment_id" in header and "recommendation_ids" in header:
        return  # Already up to date

    upgraded_rows = [AUDIT_LOG_FIELDS]
    for row in reader[1:]:
        if not row:
            continue
        row_dict = {header[i]: row[i] for i in range(min(len(header), len(row)))}
        new_row = [str(row_dict.get(col, "")) for col in AUDIT_LOG_FIELDS]
        upgraded_rows.append(new_row)

    with open(p, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(upgraded_rows)


def write_audit_entries(
    entries: List[Dict[str, Any]],
    log_path: Union[str, Path] = DEFAULT_AUDIT_LOG_PATH
) -> Path:
    """
    Append audit log entries to the destination CSV file.
    Automatically creates the destination directory and writes the header
    if the file does not already exist. Migrates legacy files safely in-place.

    Parameters:
        entries: List of audit entry dictionaries.
        log_path: Path to audit log CSV.

    Returns:
        Resolved Path to the audit log CSV.
    """
    if not entries:
        return resolve_log_path(log_path)

    p = resolve_log_path(log_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    if p.exists() and p.stat().st_size > 0:
        migrate_legacy_audit_log(p)

    write_header = not p.exists() or p.stat().st_size == 0

    with open(p, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=AUDIT_LOG_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(entries)

    logger.debug("Appended %d audit entries to %s", len(entries), p)
    return p


def read_audit_log(log_path: Union[str, Path] = DEFAULT_AUDIT_LOG_PATH) -> Any:
    """
    Read audit log CSV into a pandas DataFrame with full backward-compatibility.
    Guarantees 'assessment_id' and 'recommendation_ids' columns exist even when reading older files.
    """
    import pandas as pd
    p = resolve_log_path(log_path)
    if not p.exists() or p.stat().st_size == 0:
        return pd.DataFrame(columns=AUDIT_LOG_FIELDS)
    df = pd.read_csv(p, keep_default_na=False)
    for col in AUDIT_LOG_FIELDS:
        if col not in df.columns:
            df[col] = ""
    return df


def log_prediction_single(
    prediction: Dict[str, Any],
    source_id: str = "feature_record",
    allow_partial: bool = True,
    log_path: Union[str, Path] = DEFAULT_AUDIT_LOG_PATH,
    assessment_id: Optional[str] = None,
    recommendation_ids: Optional[Union[List[str], str]] = None,
) -> Path:
    """Convenience helper to log a single prediction record."""
    entry = create_audit_entry(
        prediction=prediction,
        source_id=source_id,
        allow_partial=allow_partial,
        assessment_id=assessment_id,
        recommendation_ids=recommendation_ids,
    )
    return write_audit_entries([entry], log_path=log_path)


def log_predictions_batch(
    predictions: List[Dict[str, Any]],
    source_id: str = "feature_table",
    allow_partial: bool = True,
    log_path: Union[str, Path] = DEFAULT_AUDIT_LOG_PATH,
    assessment_id: Optional[str] = None,
    recommendation_ids: Optional[Union[List[str], str]] = None,
) -> Path:
    """Convenience helper to log a batch of prediction records."""
    entries = [
        create_audit_entry(
            prediction=pred,
            source_id=source_id,
            allow_partial=allow_partial,
            assessment_id=assessment_id or pred.get("assessment_id"),
            recommendation_ids=recommendation_ids or pred.get("recommendation_ids"),
        )
        for pred in predictions
    ]
    return write_audit_entries(entries, log_path=log_path)


def log_outlook_entry(
    outlook: Dict[str, Any],
    source_id: str = "open_meteo_forecast",
    log_path: Union[str, Path] = DEFAULT_AUDIT_LOG_PATH,
    assessment_id: Optional[str] = None,
    recommendation_ids: Optional[Union[List[str], str]] = None,
) -> Path:
    """Convenience helper to log an outlook or scenario evaluation entry."""
    entry = create_audit_entry(
        prediction=outlook,
        source_id=source_id,
        allow_partial=True,
        assessment_id=assessment_id,
        recommendation_ids=recommendation_ids,
    )
    return write_audit_entries([entry], log_path=log_path)

