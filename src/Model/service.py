"""
Soil Sentinel - Unified Backend Integration Service & Dashboard Handoff Engine.

Provides the single entry point connecting validated data loading, deterministic risk
assessment, multi-factor explanation, ranked recommendations, baseline-versus-hypothetical
scenario simulation, longitudinal recovery tracking, crop recommendation eligibility, and
append-only audit logging.

DESIGNED SPECIFICALLY FOR STREAMLIT DASHBOARD INTEGRATION:
1. Zero ML dependencies: Pure Python 3, NumPy, and Pandas. Fully compatible with IBM LinuxONE.
2. Complete Type Safety & JSON-serializability: All payloads return clean native Python primitives
   (dict, list, str, float, bool) ready for direct consumption by st.metric, st.dataframe,
   plotly/altair charts, and UI expanders.
3. Interactive Scenario Testing: Supports evaluating custom scenario parameter sweeps (rainfall
   variation, temperature shifts, organic carbon enhancement) against the baseline state.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from src.Model.risk_scoring import (
    calculate_baseline_risk_score,
    classify_risk_category,
    RiskScoringResult,
    INDEX_NAME,
    ASSUMPTIONS_LABEL,
)
from src.Model.predict import (
    predict_dataframe,
    predict_from_csv,
    predict_record,
    REQUIRED_FEATURE_COLUMNS,
    IDENTIFIER_COLUMNS,
)
from src.Model.recommendations import (
    generate_ranked_recommendations,
    RankedRecommendationPlan,
)
from src.Model.scenarios import (
    compare_baseline_to_scenarios,
    BaselineScenarioComparisonReport,
    ScenarioComparisonItem,
)
from src.Model.recovery import (
    evaluate_historical_recovery,
    RecoveryAssessment,
)
from src.Model.crop_eligibility import (
    evaluate_crop_eligibility,
    CropEligibilityResult,
    AGRONOMIC_DISCLAIMER,
)
from src.Model.audit_log import (
    create_audit_entry,
    write_audit_entries,
    log_prediction_single,
    DEFAULT_AUDIT_LOG_PATH,
    ENGINE_VERSION,
)

logger = logging.getLogger("soil_sentinel_service")

# Default relative paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_FEATURE_TABLE_PATH = PROJECT_ROOT / "data" / "feature_table.csv"


class SoilSentinelService:
    """
    Unified backend service orchestrating all SoilSentinel assessment modules.
    """

    def __init__(
        self,
        data_path: Optional[Union[str, Path]] = None,
        audit_log_path: Optional[Union[str, Path]] = None,
        auto_score: bool = True
    ):
        """
        Initialize service with dataset path and optional audit log path.

        Parameters:
            data_path: Path to feature_table.csv or scored predictions CSV.
                       If None, defaults to 'data/feature_table.csv'.
            audit_log_path: Path to audit log CSV. Defaults to 'logs/audit_log.csv'.
            auto_score: Whether to score all records on initialization.
        """
        self.data_path = Path(data_path) if data_path else DEFAULT_FEATURE_TABLE_PATH
        self.audit_log_path = Path(audit_log_path) if audit_log_path else DEFAULT_AUDIT_LOG_PATH
        self.df_scored: Optional[pd.DataFrame] = None
        self.df_raw: Optional[pd.DataFrame] = None

        if self.data_path.exists() and auto_score:
            self.reload_data()

    def reload_data(self) -> None:
        """Load and score dataset from data_path."""
        if not self.data_path.exists():
            raise FileNotFoundError(f"Dataset not found at: {self.data_path}")

        logger.info(f"Loading and scoring SoilSentinel data from: {self.data_path}")
        self.df_raw = pd.read_csv(self.data_path)
        
        # Check if already scored
        if "score" in self.df_raw.columns and "moisture_deficit_sub_score" in self.df_raw.columns:
            self.df_scored = self.df_raw.copy()
        else:
            self.df_scored = predict_from_csv(
                input_path=self.data_path,
                output_path=None,
                allow_partial=True
            )

        # Sort chronologically by date if date column exists
        if "date" in self.df_scored.columns:
            self.df_scored["date"] = self.df_scored["date"].astype(str)
            self.df_scored = self.df_scored.sort_values(by="date").reset_index(drop=True)

    def load_dataframe(self, df: pd.DataFrame) -> None:
        """Load an in-memory DataFrame directly into the service."""
        if df.empty:
            raise ValueError("Cannot load empty DataFrame.")
        self.df_raw = df.copy()
        self.df_scored = predict_dataframe(self.df_raw, allow_partial=True)
        if "date" in self.df_scored.columns:
            self.df_scored["date"] = self.df_scored["date"].astype(str)
            self.df_scored = self.df_scored.sort_values(by="date").reset_index(drop=True)

    def get_available_dates(self) -> List[str]:
        """Return sorted list of available date strings."""
        if self.df_scored is None or self.df_scored.empty:
            return []
        if "date" in self.df_scored.columns:
            return sorted(self.df_scored["date"].unique().tolist())
        return []

    def get_latest_date(self) -> Optional[str]:
        """Return the most recent date string in the loaded dataset."""
        dates = self.get_available_dates()
        return dates[-1] if dates else None

    def get_raw_record(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve raw feature record for a given date (or latest)."""
        if self.df_raw is None or self.df_raw.empty:
            raise ValueError("No data loaded. Call reload_data() or load_dataframe().")

        eval_date = date or self.get_latest_date()
        if eval_date is None:
            raise ValueError("No records found in dataset.")

        matches = self.df_raw[self.df_raw["date"].astype(str) == str(eval_date)]
        if matches.empty:
            raise KeyError(f"Date '{eval_date}' not found in loaded dataset.")
        return matches.iloc[0].to_dict()

    def get_scored_record(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve scored prediction record for a given date (or latest)."""
        if self.df_scored is None or self.df_scored.empty:
            raise ValueError("No data loaded. Call reload_data() or load_dataframe().")

        eval_date = date or self.get_latest_date()
        if eval_date is None:
            raise ValueError("No records found in dataset.")

        matches = self.df_scored[self.df_scored["date"].astype(str) == str(eval_date)]
        if matches.empty:
            raise KeyError(f"Date '{eval_date}' not found in loaded dataset.")
        return matches.iloc[0].to_dict()

    def get_dashboard_payload(
        self,
        date: Optional[str] = None,
        allow_partial: bool = True,
        log_audit: bool = False,
        include_scenarios: bool = True,
        custom_scenarios: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate complete, consolidated dashboard payload for a target date.

        Parameters:
            date: Target date 'YYYY-MM'. If None, evaluates the latest available date.
            allow_partial: Whether to allow provisional scoring if rolling history is unobserved.
            log_audit: Whether to append an audit entry for this evaluation.
            include_scenarios: Whether to compute scenario comparisons.
            custom_scenarios: Optional list of custom scenario definitions to compare.

        Returns:
            JSON-serializable dictionary containing all modules' results.
        """
        if self.df_scored is None or self.df_scored.empty:
            self.reload_data()

        eval_date = date or self.get_latest_date()
        if eval_date is None:
            raise ValueError("No records available in dataset to evaluate.")

        # 1. Retrieve Raw Record and Scored Record
        raw_record = self.get_raw_record(eval_date)
        scored_record = self.get_scored_record(eval_date)

        # 2. Risk Assessment Object
        risk_result: RiskScoringResult = calculate_baseline_risk_score(
            raw_record,
            allow_partial=allow_partial
        )
        risk_dict = risk_result.to_dict()

        # Compute top risk drivers and data quality info
        indicators = risk_dict.get("indicators") or {}
        sorted_indicators = sorted(
            [
                {
                    "indicator_key": k,
                    "indicator_name": v.get("name", k),
                    "sub_score": v.get("sub_score", 0.0) or 0.0,
                    "weight": v.get("weight", 0.0) or 0.0,
                    "weighted_score": v.get("weighted_score", 0.0) or 0.0,
                }
                for k, v in indicators.items()
            ],
            key=lambda x: x["weighted_score"],
            reverse=True
        )
        risk_dict["top_risk_drivers"] = [item["indicator_name"] for item in sorted_indicators[:3]]
        risk_dict["data_quality"] = {
            "status": "COMPLETE" if risk_result.status == "VALID" else ("PROVISIONAL" if risk_result.status == "PROVISIONAL" else "DEGRADED"),
            "evidence_tier": "TIER_1_EMPIRICAL" if risk_result.status == "VALID" else "TIER_2_PROVISIONAL",
            "observation_completeness": 1.0 if risk_result.status == "VALID" else 0.8,
            "missing_features": [k for k in REQUIRED_FEATURE_COLUMNS if k not in raw_record or pd.isna(raw_record.get(k))],
            "data_sources": ["NASA POWER (Meteorology)", "SoilGrids 250m (Pedology)"]
        }

        # 3. Ranked Recommendations
        rec_plan: RankedRecommendationPlan = generate_ranked_recommendations(
            scoring_result=risk_result,
            record=raw_record
        )
        rec_dict = rec_plan.to_dict()

        # 4. Longitudinal Recovery Tracking
        recovery_assessment: RecoveryAssessment = evaluate_historical_recovery(
            df_scored=self.df_scored,
            target_date=eval_date
        )
        recovery_dict = recovery_assessment.to_dict()

        # 5. Crop Recommendation Eligibility
        crop_eligibility: CropEligibilityResult = evaluate_crop_eligibility(
            data=risk_result,
            date=eval_date
        )
        crop_dict = crop_eligibility.to_dict()

        # 6. Scenario Comparisons
        scenario_dict: Optional[Dict[str, Any]] = None
        if include_scenarios:
            scenarios_to_run = ["dry_spell", "normal_climatology", "heavy_rainfall"]
            if custom_scenarios and isinstance(custom_scenarios, list):
                scenarios_to_run = [str(s) for s in custom_scenarios]
            scenario_report: BaselineScenarioComparisonReport = compare_baseline_to_scenarios(
                baseline_record=raw_record,
                scenarios=scenarios_to_run
            )
            scenario_dict = scenario_report.to_dict()

        # 7. Historical Series Summary for Plotting
        historical_series: List[Dict[str, Any]] = []
        if self.df_scored is not None and "date" in self.df_scored.columns:
            s_col = "score" if "score" in self.df_scored.columns else "baseline_risk_score"
            cat_col = "risk_category" if "risk_category" in self.df_scored.columns else None
            for _, r in self.df_scored.iterrows():
                val = r.get(s_col)
                cat = r.get(cat_col) if cat_col else classify_risk_category(val)
                historical_series.append({
                    "date": str(r.get("date")),
                    "score": round(float(val), 2) if (val is not None and not pd.isna(val)) else None,
                    "risk_category": str(cat) if cat else "UNKNOWN"
                })

        # 8. Append-Only Audit Logging (Optional)
        audit_logged = False
        assessment_id = f"ASM-{eval_date}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        rec_ids = [
            r.get("recommendation_id")
            for r in rec_dict.get("top_three_recommendations", [])
            if r.get("recommendation_id")
        ]
        if log_audit:
            try:
                log_prediction_single(
                    prediction=scored_record,
                    source_id="dashboard_service",
                    allow_partial=allow_partial,
                    log_path=self.audit_log_path,
                    assessment_id=assessment_id,
                    recommendation_ids=rec_ids,
                )
                audit_logged = True
            except Exception as e:
                logger.warning(f"Could not log audit entry: {e}")

        # 9. Assemble Consolidated Payload
        payload = {
            "metadata": {
                "assessment_id": assessment_id,
                "assessment_status": risk_result.status,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "engine_version": ENGINE_VERSION,
                "index_name": INDEX_NAME,
                "assumptions_label": ASSUMPTIONS_LABEL,
                "evaluation_date": eval_date,
                "audit_logged": audit_logged,
            },
            "risk_assessment": risk_dict,
            "recommendations": rec_dict,
            "recovery_tracking": recovery_dict,
            "crop_eligibility": crop_dict,
            "scenario_comparison": scenario_dict,
            "historical_series": historical_series,
            "audit_reference": {
                "assessment_id": assessment_id,
                "audit_logged": audit_logged,
                "log_path": str(self.audit_log_path),
                "engine_version": ENGINE_VERSION,
                "source_id": "dashboard_service",
                "recommendation_ids": rec_ids,
                "pii_redacted": True,
            },
        }
        return payload

    def evaluate_custom_scenario(
        self,
        date: Optional[str] = None,
        custom_precipitation: float = 0.5,
        custom_temperature: float = 38.0,
        horizon_days: int = 30
    ) -> Dict[str, Any]:
        """
        Evaluate an interactive custom meteorological scenario against the baseline record.

        Parameters:
            date: Target date (defaults to latest).
            custom_precipitation: Hypothetical precipitation rate (mm/day).
            custom_temperature: Hypothetical air temperature (C).
            horizon_days: Projection window (default: 30 days).

        Returns:
            Dictionary with baseline vs scenario comparison details.
        """
        eval_date = date or self.get_latest_date()
        raw_rec = self.get_raw_record(eval_date)

        report = compare_baseline_to_scenarios(
            baseline_record=raw_rec,
            scenarios=["custom"],
            custom_precipitation=custom_precipitation,
            custom_temperature=custom_temperature,
            horizon_days=horizon_days
        )
        report_dict = report.to_dict()
        return report_dict.get("comparisons", {}).get("custom", {})


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

_GLOBAL_SERVICE: Optional[SoilSentinelService] = None


def get_dashboard_payload(
    date: Optional[str] = None,
    data_path: Optional[Union[str, Path]] = None,
    allow_partial: bool = True,
    log_audit: bool = False
) -> Dict[str, Any]:
    """
    Convenience function returning the full dashboard payload for a target date.
    Caches the service instance for performance across repeated dashboard runs.
    """
    global _GLOBAL_SERVICE
    if _GLOBAL_SERVICE is None or (data_path and Path(data_path) != _GLOBAL_SERVICE.data_path):
        _GLOBAL_SERVICE = SoilSentinelService(data_path=data_path)
    return _GLOBAL_SERVICE.get_dashboard_payload(
        date=date,
        allow_partial=allow_partial,
        log_audit=log_audit
    )
