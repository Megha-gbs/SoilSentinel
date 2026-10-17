"""
Soil Sentinel - Model Architecture Note & Safety Guards.

The SoilSentinel risk assessment framework implements a deterministic, rule-based
scoring system rather than a machine learning model trained on historical ground labels.

Implementation:
- Scoring engine: `src.Model.risk_scoring.calculate_baseline_risk_score`
- Batch prediction: `src.Model.predict.predict_dataframe`
- Audit logging: `src.Model.audit_log.log_predictions_batch`
- Forecast/Scenario outlook: `src.Model.outlook.evaluate_forecast_outlook`
- Unified service: `src.Model.service.SoilSentinelService`

Notice:
SoilSentinel does NOT load, deserialize, or depend on serialized machine learning
model binaries (`models/soil_risk_model.joblib`), ensuring deterministic execution,
full auditability, and zero native binary dependencies on architectures such as
IBM LinuxONE (s390x).
"""

from pathlib import Path
from typing import Any, Optional


def load_trained_model(model_path: Optional[str] = None) -> Any:
    """
    Safety guard to prevent loading or executing empty/unverified model artifacts.

    Raises RuntimeError explicitly explaining that SoilSentinel uses the deterministic
    Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index instead of a trained
    serialized binary.
    """
    raise RuntimeError(
        "SoilSentinel does not load or execute trained ML model binaries. "
        "The file 'models/soil_risk_model.joblib' is an unpopulated placeholder. "
        "Use the deterministic scoring engine in `src.Model.risk_scoring` or "
        "`src.Model.service.SoilSentinelService` instead."
    )
