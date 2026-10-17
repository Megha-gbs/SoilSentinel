"""
Soil Sentinel - Model and Prediction Package.

Contains the deterministic baseline risk scoring engine, prediction interfaces,
audit logging, forecast/scenario outlooks, ranked recommendations, and scenario comparisons for the
Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index.
"""

from src.Model.risk_scoring import (
    calculate_baseline_risk_score,
    score_feature_dataframe,
    classify_risk_category,
    RiskScoringResult,
    INDEX_NAME,
    ASSUMPTIONS_LABEL,
)
from src.Model.predict import (
    predict_record,
    predict_dataframe,
    predict_from_csv,
    REQUIRED_FEATURE_COLUMNS,
    IDENTIFIER_COLUMNS,
)
from src.Model.audit_log import (
    create_audit_entry,
    write_audit_entries,
    log_prediction_single,
    log_predictions_batch,
    log_outlook_entry,
    read_audit_log,
    AUDIT_LOG_FIELDS,
    DEFAULT_AUDIT_LOG_PATH,
    ENGINE_VERSION,
)
from src.Model.outlook import (
    fetch_weather_forecast,
    evaluate_forecast_outlook,
    evaluate_scenario_outlook,
    check_antecedent_status,
    WeatherForecastResult,
    OutlookResult,
)
from src.Model.recommendations import (
    generate_ranked_recommendations,
    RankedRecommendationPlan,
    RecommendationItem,
)
from src.Model.scenarios import (
    compare_baseline_to_scenarios,
    ScenarioComparisonItem,
    BaselineScenarioComparisonReport,
)
from src.Model.recovery import (
    evaluate_historical_recovery,
    RecoveryAssessment,
)
from src.Model.crop_eligibility import (
    evaluate_crop_eligibility,
    determine_cropping_season,
    CropEligibilityResult,
    CropOption,
    WITHHELD_CRITICAL_HIGH_RISK,
    WITHHELD_ACUTE_DESICCATION,
    WITHHELD_THERMAL_EXTREME,
    WITHHELD_DEGRADED_SOC,
    WITHHELD_ACIDIC_SODIC_PH,
    WITHHELD_MISSING_DATA,
    AGRONOMIC_DISCLAIMER,
)
from src.Model.service import (
    SoilSentinelService,
    get_dashboard_payload,
)

__all__ = [
    # Risk Scoring
    "calculate_baseline_risk_score",
    "score_feature_dataframe",
    "classify_risk_category",
    "RiskScoringResult",
    "INDEX_NAME",
    "ASSUMPTIONS_LABEL",
    # Prediction
    "predict_record",
    "predict_dataframe",
    "predict_from_csv",
    "REQUIRED_FEATURE_COLUMNS",
    "IDENTIFIER_COLUMNS",
    # Audit Logging
    "create_audit_entry",
    "write_audit_entries",
    "log_prediction_single",
    "log_predictions_batch",
    "log_outlook_entry",
    "read_audit_log",
    "AUDIT_LOG_FIELDS",
    "DEFAULT_AUDIT_LOG_PATH",
    "ENGINE_VERSION",
    # Outlook
    "fetch_weather_forecast",
    "evaluate_forecast_outlook",
    "evaluate_scenario_outlook",
    "check_antecedent_status",
    "WeatherForecastResult",
    "OutlookResult",
    # Recommendations
    "generate_ranked_recommendations",
    "RankedRecommendationPlan",
    "RecommendationItem",
    # Scenarios Comparison
    "compare_baseline_to_scenarios",
    "ScenarioComparisonItem",
    "BaselineScenarioComparisonReport",
    # Historical Recovery
    "evaluate_historical_recovery",
    "RecoveryAssessment",
    # Crop Recommendation Eligibility
    "evaluate_crop_eligibility",
    "determine_cropping_season",
    "CropEligibilityResult",
    "CropOption",
    "WITHHELD_CRITICAL_HIGH_RISK",
    "WITHHELD_ACUTE_DESICCATION",
    "WITHHELD_THERMAL_EXTREME",
    "WITHHELD_DEGRADED_SOC",
    "WITHHELD_ACIDIC_SODIC_PH",
    "WITHHELD_MISSING_DATA",
    "AGRONOMIC_DISCLAIMER",
    # Unified Service & Dashboard Handoff
    "SoilSentinelService",
    "get_dashboard_payload",
]
