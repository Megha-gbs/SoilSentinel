# SoilSentinel: Backend Integration & Dashboard Handoff Contract

**Target Audience:** Frontend / Streamlit Dashboard Teammate  
**Backend Scope:** Data Collection, Preprocessing, Risk Scoring, Explanations, Ranked Recommendations, Hypothetical Scenarios, Historical Recovery Tracking, and Crop Recommendation Eligibility.  
**Platform Compatibility:** Python 3.10+ (Tested on Windows AMD64 and LinuxONE s390x; pure Python, NumPy, Pandas; zero serialized `.joblib` model binary dependencies).

---

## 1. Quickstart for Streamlit

The entire backend functionality is unified into a single service interface with **zero raw calculation required by the frontend**.

```python
import streamlit as st
from src.Model.service import SoilSentinelService, get_dashboard_payload

# 1. Initialize backend service (cached automatically across reruns)
@st.cache_resource
def load_service():
    return SoilSentinelService()

svc = load_service()

# 2. Get available dates for user dropdown
available_dates = svc.get_available_dates()  # e.g. ['2020-01', ..., '2024-12']
selected_date = st.selectbox("Select Evaluation Month", available_dates, index=len(available_dates)-1)

# 3. Fetch comprehensive, ready-to-render dashboard payload
payload = svc.get_dashboard_payload(date=selected_date)

# 4. Display high-level metrics
st.metric(
    label="Baseline Hydro-Thermal Risk Score",
    value=f"{payload['risk_assessment']['score']:.1f} / 100",
    delta=f"{payload['recovery_tracking']['mom_delta']:+.1f} MoM" if payload['recovery_tracking']['mom_delta'] is not None else None
)
```

---

## 2. Python API Interfaces

### `SoilSentinelService`
Located in `src/Model/service.py` (also exported from `src.Model`).

```python
class SoilSentinelService:
    def __init__(
        self,
        data_path: Optional[Union[str, Path]] = None,
        audit_log_path: Optional[Union[str, Path]] = None,
        auto_score: bool = True
    ): ...

    def get_available_dates(self) -> List[str]:
        """Returns sorted list of available date strings ['YYYY-MM', ...]."""

    def get_latest_date(self) -> Optional[str]:
        """Returns the most recent date string in the dataset."""

    def get_dashboard_payload(
        self,
        date: Optional[str] = None,
        allow_partial: bool = True,
        log_audit: bool = False,
        include_scenarios: bool = True,
        custom_scenarios: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Returns the consolidated JSON-serializable payload dictionary."""

    def evaluate_custom_scenario(
        self,
        date: Optional[str] = None,
        custom_precipitation: float = 0.5,
        custom_temperature: float = 38.0,
        horizon_days: int = 30
    ) -> Dict[str, Any]:
        """Evaluates interactive slider parameters against baseline."""
```

### Module-Level Shortcut: `get_dashboard_payload`
```python
from src.Model import get_dashboard_payload

payload = get_dashboard_payload(date="2024-12")
```

---

## 3. Consolidated Payload JSON Schema

The dictionary returned by `get_dashboard_payload(date)` contains 8 top-level blocks:

```json
{
  "metadata": { ... },
  "risk_assessment": { ... },
  "recommendations": { ... },
  "recovery_tracking": { ... },
  "crop_eligibility": { ... },
  "scenario_comparison": { ... },
  "historical_series": [ ... ],
  "ml_prediction": { ... }
}
```

### 3.1 `metadata`
| Field | Type | Description |
| :--- | :--- | :--- |
| `assessment_id` | `str` | Unique evaluation identifier (`"ASM-YYYY-MM-YYYYMMDDHHMMSS"`). |
| `assessment_status`| `str` | Data readiness status: `"COMPLETE"`, `"PROVISIONAL_PARTIAL_HISTORY"`, or `"INVALID_INPUT"`. |
| `evaluation_date` | `str` | Target month evaluated (`"YYYY-MM"`). |
| `generated_at_utc` | `str` | ISO 8601 UTC timestamp of execution. |
| `engine_version` | `str` | Backend software version (`"v1.0.0-baseline"`). |
| `index_name` | `str` | `"Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index"`. |
| `assumptions_label` | `str` | `"PROVISIONAL_ENGINEERING_HEURISTIC"`. |
| `audit_logged` | `bool` | Whether an audit trail entry was appended. |

### 3.2 `risk_assessment`
| Field | Type | Description |
| :--- | :--- | :--- |
| `score` | `float` | Composite index score in range `[0.0, 100.0]`. |
| `risk_category` | `str` | `"Low"` (< 35), `"Medium"` (35-65), or `"High"` (>= 65). |
| `status` | `str` | `"COMPLETE"`, `"PROVISIONAL_PARTIAL_HISTORY"`, or error code. |
| `dynamic_environmental_stress` | `float` | Weighted sum of dynamic weather sub-scores (70% weight). |
| `baseline_soil_vulnerability` | `float` | Weighted sum of static soil sub-scores (30% weight). |
| `top_risk_drivers` | `list[str]` | The top 3 ranked stress drivers contributing to the overall score. |
| `explanation` | `str` | Transparent narrative summarizing primary stress driver. |
| `data_quality` | `dict` | Evidence tier, completeness, and missing features metadata. |
| `indicators` | `dict` | Nested dictionaries for all 5 component indicators: |
| ↳ `moisture_deficit` | `dict` | `sub_score`, `weight` (0.30), `weighted_score`, `raw_value`. |
| ↳ `precipitation_deficit` | `dict` | `sub_score`, `weight` (0.25), `moisture_buffering_factor`. |
| ↳ `thermal_stress` | `dict` | `sub_score`, `weight` (0.15), `raw_value` (°C). |
| ↳ `soc_vulnerability` | `dict` | `sub_score`, `weight` (0.15), `raw_value` (g/kg). |
| ↳ `ph_deviation` | `dict` | `sub_score`, `weight` (0.15), `raw_value` (pH units). |

### 3.3 `recommendations`
| Field | Type | Description |
| :--- | :--- | :--- |
| `status` | `str` | `"COMPLETE"`, `"INSUFFICIENT_HISTORY"`, or `"INVALID_INPUT"`. |
| `overall_risk_score` | `float` | Baseline score for reference. |
| `overall_risk_category`| `str` | Baseline category for reference. |
| `primary_stressor` | `str` | Name of the highest-contributing indicator. |
| `critical_actions` | `list[str]` | Highlights of actions requiring immediate attention. |
| `top_three_recommendations` | `list[dict]` | Top 3 prioritized interventions for farmer UI display. |
| `recommendations` | `list[dict]` | Full list of 5 ranked interventions sorted descending by weighted impact. |
| ↳ `recommendation_id` | `str` | Unique action code (e.g. `"REC-PRECIP-CRI"`, `"REC-MOISTURE-HIG"`). |
| ↳ `indicator_key` | `str` | e.g. `"moisture_deficit"`, `"soc_vulnerability"`. |
| ↳ `urgency` | `str` | `"CRITICAL"`, `"HIGH"`, `"MODERATE"`, or `"MAINTENANCE"`. |
| ↳ `action_type` | `str` | `"PREVENTION"`, `"RESTORATION"`, or `"MAINTENANCE"`. |
| ↳ `title` | `str` | Actionable heading. |
| ↳ `reason` | `str` | Agronomic justification based on observed physical sub-scores. |
| ↳ `primary_intervention` | `str` | Core agronomic intervention summary. |
| ↳ `actionable_steps` | `list[str]` | Concrete field practices (e.g. mulching, FYM dose). |
| ↳ `cost_category` | `str` | Indicative cost tier (e.g. `"Low Cost (Mulch)"`, `"Moderate Investment"`). |
| ↳ `limitations` | `str` | Agronomic boundary limitations and caveats. |
| ↳ `expected_benefit` | `str` | Expected physical improvement. |
| ↳ `observed_metric` | `str` | Context string displaying raw input value and sub-score. |
| `disclaimer` | `str` | Non-ML agronomic screening disclaimer. |

### 3.4 `recovery_tracking`
| Field | Type | Description |
| :--- | :--- | :--- |
| `recovery_status` | `str` | Standardized longitudinal trajectory state: |
| | | - `"RECOVERING"`: Easing stress (3m slope <= -2.5 pts/mo). |
| | | - `"ESCALATING_STRESS"`: Worsening stress (3m slope >= +2.5 pts/mo). |
| | | - `"CHRONIC_HIGH_STRESS"`: High risk (>=65) for >= 3 consecutive months. |
| | | - `"STABLE_RESILIENT"`: Low risk (<35) for >= 3 consecutive months. |
| | | - `"SEASONAL_CYCLING"`: Normal within-season cyclical fluctuations. |
| | | - `"INSUFFICIENT_HISTORY"`: Boundary sequence (< 3 observed months). |
| `observation_count` | `int` | Number of sequential observations in historical window. |
| `mom_delta` | `float` or `None` | Month-over-Month change: $Score(t) - Score(t-1)$. |
| `yoy_delta` | `float` or `None` | Year-over-Year change: $Score(t) - Score(t-12)$. |
| `historical_mean` | `float` | Historical average score over observed record. |
| `historical_min` | `float` | All-time minimum score. |
| `historical_max` | `float` | All-time maximum stress peak. |
| `historical_percentile`| `float` | Current score percentile rank vs. historical record [0-100%]. |
| `consecutive_months_in_category` | `int` | Sequential run length in current risk category. |
| `trajectory_slope_3m` | `float` | Linear rate of change (pts/month) over recent quarter. |
| `peak_stress_recovery_points` | `float` | Relief points recovered from historical maximum ($Max - Current$). |
| `evidence_summary` | `str` | Human-readable longitudinal synthesis. |

### 3.5 `crop_eligibility`
| Field | Type | Description |
| :--- | :--- | :--- |
| `is_eligible` | `bool` | `True` if planting advisory is permitted; `False` if withheld. |
| `withhold_reasons` | `list[str]` | Violated biophysical safety constraints: |
| | | - `"WITHHELD_CRITICAL_HIGH_RISK"`: Overall score >= 75.0. |
| | | - `"WITHHELD_ACUTE_DESICCATION"`: Moisture deficit sub-score >= 80.0. |
| | | - `"WITHHELD_THERMAL_EXTREME"`: Thermal stress sub-score >= 80.0. |
| | | - `"WITHHELD_DEGRADED_SOC"`: SOC depletion sub-score >= 85.0. |
| | | - `"WITHHELD_ACIDIC_SODIC_PH"`: pH deviation sub-score >= 80.0. |
| | | - `"WITHHELD_MISSING_DATA"`: Incomplete or unobserved data. |
| `withhold_explanations`| `list[str]` | Detailed agronomic reasons for withholding recommendations. |
| `season` | `str` | Detected agro-climatic season: `"Kharif"`, `"Rabi"`, or `"Zaid"`. |
| `recommended_crops` | `list[dict]` | Suitable functional crops when eligible: |
| ↳ `crop_name` | `str` | e.g. `"Chickpea (Gram)"`, `"Pearl Millet (Bajra)"`. |
| ↳ `category` | `str` | e.g. `"Cool-season Pulse"`, `"Coarse Cereal"`. |
| ↳ `water_requirement` | `str` | `"Low"`, `"Moderate"`, or `"High"`. |
| ↳ `growth_duration_days` | `str` | e.g. `"95-110 days"`. |
| ↳ `agronomic_rationale` | `str` | Why the crop is suited to the current soil/climate profile. |
| ↳ `suitable_soils` | `str` | Soil textural preference. |
| `restricted_crops` | `list[dict]` | Crops prohibited due to high moisture demand (e.g. Paddy). |
| `management_advisory` | `str` | High-level seasonal planting advice. |
| `disclaimer` | `str` | Mandatory non-ML screening disclaimer. |

### 3.6 `scenario_comparison`
| Field | Type | Description |
| :--- | :--- | :--- |
| `status` | `str` | `"CALCULATED"` or error status. |
| `baseline_date` | `str` | Target date evaluated. |
| `baseline_score` | `float` | Current baseline score. |
| `baseline_category` | `str` | Current baseline category. |
| `static_soil_resilience`| `str` | `"HIGH_RESILIENCE"`, `"MODERATE_RESILIENCE"`, or `"LOW_RESILIENCE_VULNERABLE"`. |
| `comparisons` | `dict` | Comparison entries for canonical scenarios: |
| ↳ `dry_spell` | `dict` | 0.0 mm/day rainfall, +2.0°C temperature anomaly. |
| ↳ `normal_climatology` | `dict` | Historical monthly average rainfall and temperature. |
| ↳ `heavy_rainfall` | `dict` | 15.0 mm/day monsoon surge. |
| ↳ Each scenario contains: | | `scenario_atmospheric_score`, `delta_score`, `category_shift`, `resilience_assessment`. |
| `summary_narrative` | `str` | Comparative synthesis across scenarios. |

### 3.7 `historical_series`
A list of 60 chronological dictionaries designed for instant plotting in Streamlit (`st.line_chart` or `plotly.express.line`):
```json
[
  { "date": "2020-01", "score": 28.52, "risk_category": "Low" },
  ...
  { "date": "2024-12", "score": 38.64, "risk_category": "Medium" }
]
```

### 3.8 `audit_reference`
| Field | Type | Description |
| :--- | :--- | :--- |
| `assessment_id` | `str` | Traceability UUID / timestamped assessment run code. |
| `audit_logged` | `bool` | Confirmation flag indicating entry persistence in `logs/audit_log.csv`. |
| `log_path` | `str` | Absolute/relative destination path of append-only audit log. |
| `engine_version` | `str` | Software version tag (`"v1.0.0-baseline"`). |
| `source_id` | `str` | Ingestion source identifier (`"dashboard_service"`). |
| `recommendation_ids` | `list[str]` | IDs of top-3 interventions written to audit record. |
| `pii_redacted` | `bool` | Strict flag confirming zero personally identifiable farmer records. |

### 3.9 `ml_prediction` (Machine Learning Surrogate Engine)
An empirical surrogate prediction generated by the trained Random Forest model (`models/soil_risk_model.joblib`), learning to approximate the multi-factor risk categorization directly from raw atmospheric and hydrological features.

| Field | Type | Description |
| :--- | :--- | :--- |
| `status` | `str` | Model inference status (`"AVAILABLE"`, `"UNAVAILABLE"`, or `"ERROR"`). |
| `model_version` | `str` | Serialized model version tag (`"v1.0.0-rf-proxy"`). |
| `model_type` | `str` | Model algorithm (`"Random Forest Classifier"`). |
| `predicted_category` | `str` | Surrogate risk prediction: `"Low"`, `"Medium"`, or `"High"`. |
| `class_probabilities` | `dict` | Estimated class probabilities: `{"High": float, "Low": float, "Medium": float}`. |
| `target_provenance` | `str` | Provenance classification: `"SURROGATE_PROXY_LEARNING"`. |
| `top_drivers` | `list[str]` | Top 3 driving features by Gini importance (e.g. `["air_humidity_percent", ...]`). |
| `disclaimer` | `str` | Notice qualifying the prediction as a surrogate proxy rather than a physical field degradation measurement. |

### 3.10 `ml_explanation` (SHAP Local & Multiclass Explainability Engine)
An additive attribution explanation computed via `shap.TreeExplainer` operating on the Random Forest surrogate model. Explains the exact additive contributions ($\sum \phi_j$) driving the model-estimated probability for the predicted class from the baseline prior.

| Field | Type | Description |
| :--- | :--- | :--- |
| `status` | `str` | Explainer execution status (`"AVAILABLE"`, `"UNAVAILABLE"`, or `"ERROR"`). Gracefully degrades without dashboard breakage. |
| `model_version` | `str` | Model version tag (`"v1.0.0-rf-proxy"`). |
| `model_type` | `str` | Algorithm name (`"Random Forest Classifier"`). |
| `predicted_class` | `str` | Classifier predicted class (`"Low"`, `"Medium"`, or `"High"`). |
| `explained_class` | `str` | Evaluated explanation class (matches `predicted_class` unless overridden). |
| `prediction_probability` | `float` | Model-estimated class probability ($\hat{P}(c)$). Note: raw tree ensemble vote fraction, uncalibrated. |
| `base_value` | `float` | Expected value baseline prior ($\mathbb{E}[f(X)]$) from training partition background. |
| `sum_shap_values` | `float` | Total additive SHAP contribution: $\sum_{j=1}^{14} \phi_j$. |
| `reconstituted_probability` | `float` | Reconstituted model probability: $\text{base\_value} + \sum \phi_j$. |
| `additivity_discrepancy` | `float` | Absolute numerical additivity error: $\|(\text{base\_value} + \sum \phi_j) - \hat{P}(c)\|$. |
| `additivity_tolerance` | `float` | Validation tolerance threshold (`0.02`). If exceeded, `status` becomes `"ERROR"`. |
| `output_space` | `str` | Explanation output space (`"probability"`). |
| `top_features` | `list[dict]` | Ranked list of top-5 driving features. Each object contains: `rank` (int), `feature` (str), `feature_value` (float or null), `shap_value` (signed float), `absolute_impact` (float), and `direction` (`"INCREASES_CLASS_PROBABILITY"` or `"DECREASES_CLASS_PROBABILITY"`). |
| `all_feature_impacts` | `dict[str, float]` | Complete mapping of all 14 physical features to their signed SHAP impacts for the explained class. |
| `original_features` | `dict[str, float]` | Raw physical feature values evaluated before imputation or scaling. |
| `methodology` | `str` | `"TreeSHAP (interventional perturbation with training partition background)"`. |
| `causation_warning` | `str` | Explicit scientific advisory: SHAP values explain surrogate model approximations, not physical ground-truth causation. |
| `disclaimer` | `str` | Notice framing explanations as surrogate model approximations of the rule-based screening index. |

#### Streamlit UI Rendering Guidance for Smruthi:
```python
if payload.get("ml_explanation") and payload["ml_explanation"].get("status") == "AVAILABLE":
    exp = payload["ml_explanation"]
    st.subheader(f"Surrogate Model Feature Attribution ({exp['explained_class']} Risk)")
    st.caption(f"Base Prior: {exp['base_value']:.2f} ➔ Predicted Probability: {exp['prediction_probability']:.2f} (Additivity Error: {exp['additivity_discrepancy']:.4f})")
    
    # Render top features table or horizontal bar chart
    top_df = pd.DataFrame(exp["top_features"])
    st.dataframe(top_df[["rank", "feature", "feature_value", "shap_value", "direction"]], use_container_width=True)
    st.info(exp["causation_warning"])
elif payload.get("ml_explanation", {}).get("status") == "UNAVAILABLE":
    st.warning("SHAP explainability is currently unavailable for this record.")

---

### 3.9 `independent_degradation_assessment`

Explicitly separates empirical screening risk from independent physical soil degradation validation.

| Field | Type | Description |
| :--- | :--- | :--- |
| `status` | `str` | `"PENDING_INDEPENDENT_GROUND_TRUTH"` (or `"VALIDATED"` once ground truth is acquired). |
| `validation_status` | `str` | `"NOT_VALIDATED_AGAINST_PHYSICAL_GROUND_TRUTH"`. |
| `model_execution` | `str` | `"BLOCKED_PENDING_INDEPENDENT_LABELS"`. |
| `target_definition` | `dict` | Scientific specification of the required physical target (e.g. SOC depletion $> 10\%$ over 5 years via ISO 10694 dry combustion). |
| `surrogate_comparison` | `dict` | Clarifies the distinction between the operational RF surrogate (`v1.0.0-rf-proxy`) and future independent physical models. |
| `evidence` | `dict` | Provenance of meteorological observations, static soil baseline, satellite NDVI, and field cores. |
| `limitations` | `list[str]` | Transparent scientific disclosures regarding screening scope, phenological sensitivity, and sampling requirements. |

---

## 4. Interactive Scenario Slider Support

In the Streamlit sidebar, provide sliders for interactive stress-testing:

```python
st.sidebar.subheader("Interactive Scenario Stress-Test")
sim_rain = st.sidebar.slider("Hypothetical Rainfall (mm/day)", 0.0, 20.0, 0.5, step=0.5)
sim_temp = st.sidebar.slider("Hypothetical Temperature (°C)", 10.0, 45.0, 38.0, step=1.0)

scenario_res = svc.evaluate_custom_scenario(
    date=selected_date,
    custom_precipitation=sim_rain,
    custom_temperature=sim_temp,
    horizon_days=30
)

st.write(f"**Simulated Score:** {scenario_res['scenario_atmospheric_score']:.1f}")
st.write(f"**Delta from Baseline:** {scenario_res['delta_score']:+.1f} pts ({scenario_res['category_shift']})")
st.info(scenario_res['resilience_assessment'])
```

---

## 5. Agronomic & Non-ML Disclaimer Notice

Every dashboard view presenting risk scores, recommendations, or crop eligibility MUST display the following standard notice:

> **Notice:** The SoilSentinel risk index is an empirical engineering heuristic based on regional reanalysis (NASA POWER) and digital soil mapping (SoilGrids 250m). It is a deterministic rule-based screening tool, NOT a machine-learned prediction model or localized certified agricultural prescription.
