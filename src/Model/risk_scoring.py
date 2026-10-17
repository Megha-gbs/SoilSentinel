"""
Soil Sentinel - Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index.

Implements a transparent, rule-based baseline scoring model that maps monthly
environmental climate indicators and static soil baseline properties into a
standardized [0, 100] index.

CRITICAL DISCLAIMER & ARCHITECTURAL PRINCIPLES:
1. PROVISIONAL RULE-BASED INDICATOR (NOT PREDICTIVE OF DEGRADATION):
   This scoring system calculates a "Seasonal Hydro-Thermal Stress & Baseline
   Vulnerability Index". It is a provisional rule-based heuristic designed for
   monitoring environmental pressure. It is NOT a validated prediction of actual
   soil degradation, soil erosion, or crop yield loss.
2. METEOROLOGICAL RECHARGE DEFICIT vs. ROOT-ZONE DROUGHT:
   Low rainfall alone represents an atmospheric moisture recharge deficit, not
   proof of active root-zone water stress. When root-zone soil moisture is adequate
   (e.g., supported by irrigation, capillary storage, or antecedent rainfall),
   the precipitation-deficit penalty is mitigated via a transparent, bounded
   moisture-buffering adjustment.
3. PROVISIONAL ENGINEERING HEURISTICS:
   All scoring weights, normalization thresholds, moisture-buffering parameters,
   and piecewise boundaries are provisional engineering assumptions calibrated
   to typical agronomic ranges in the Indo-Gangetic Plains. They do NOT claim
   agronomic certification or clinical validation.
4. SEPARATION OF TEMPORAL SCALES:
   - Dynamic Environmental Stressors (Climate & Hydrology: Soil Moisture,
     Precipitation, Temperature) vary monthly.
   - Soil Inherent Baseline Vulnerability (pH, SOC) are static regional reference
     values from ISRIC SoilGrids v2.0. A single regional baseline DOES NOT measure
     monthly soil degradation; it measures static buffering capacity.
5. EXPLICIT HANDLING OF TEMPORAL GAPS:
   Missing lag/rolling features (such as 3-month rolling precipitation at
   sequence start) are NOT silently imputed with zero. When rolling context is
   unobserved, the system either aborts with INSUFFICIENT_HISTORY (strict mode)
   or uses an explicit single-month fallback with PROVISIONAL_PARTIAL_HISTORY status.
6. ZERO TO 100 SCALE CONVENTION:
   - 0: Lowest estimated hydro-thermal stress and vulnerability.
   - 100: Highest estimated hydro-thermal stress and vulnerability.
   - Low Risk: [0.0, 35.0)
   - Medium Risk: [35.0, 65.0)
   - High Risk: [65.0, 100.0]
7. HARDWARE COMPATIBILITY:
   Pure Python 3, NumPy, and Pandas. Fully compatible with IBM LinuxONE s390x.
"""

import sys
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger("risk_scoring")

# ---------------------------------------------------------------------------
# Documented Constants and Heuristic Assumptions
# ---------------------------------------------------------------------------

INDEX_NAME = "Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index"
ASSUMPTIONS_LABEL = "PROVISIONAL_ENGINEERING_HEURISTIC"

# Weights assigned to contributing indicators (Sum = 1.00)
# Dynamic Environmental Stressors = 0.70 total
WEIGHT_MOISTURE_DEFICIT = 0.30
WEIGHT_PRECIPITATION_DEFICIT = 0.25
WEIGHT_THERMAL_STRESS = 0.15

# Static Baseline Soil Vulnerability = 0.30 total
WEIGHT_SOC_DEPLETION = 0.15
WEIGHT_PH_DEVIATION = 0.15

WEIGHT_SUM = (
    WEIGHT_MOISTURE_DEFICIT
    + WEIGHT_PRECIPITATION_DEFICIT
    + WEIGHT_THERMAL_STRESS
    + WEIGHT_SOC_DEPLETION
    + WEIGHT_PH_DEVIATION
)
assert abs(WEIGHT_SUM - 1.00) < 1e-6, "Weights must sum to 1.00"

# Category threshold boundaries on [0, 100] scale
THRESHOLD_LOW_UPPER = 35.0
THRESHOLD_MEDIUM_UPPER = 65.0

# Moisture-Buffering Adjustment Parameters (Provisional Engineering Assumptions)
# Below BUFFERING_MOISTURE_LOW_THRESHOLD, soil lacks water storage; 100% of precip penalty is retained.
BUFFERING_MOISTURE_LOW_THRESHOLD = 0.35
# Above BUFFERING_MOISTURE_ADEQUATE_THRESHOLD, root-zone storage is ample; maximum relief is applied.
BUFFERING_MOISTURE_ADEQUATE_THRESHOLD = 0.65
# Minimum penalty factor retained (50%). Even with moist soil, zero rainfall represents
# an atmospheric recharge deficit that draws down regional hydrology over time.
BUFFERING_MIN_PENALTY_FACTOR = 0.50

# ---------------------------------------------------------------------------
# Individual Indicator Scoring Functions (Normalized [0, 100])
# ---------------------------------------------------------------------------

def calculate_moisture_deficit_score(rootzone_moisture: float) -> Tuple[float, str]:
    """
    Compute root-zone soil moisture deficit sub-score [0, 100].
    
    Indicator: Root-zone Soil Wetness Fraction (0.0 to 1.0 fraction of saturation).
    Direction: Inverted (Lower moisture -> Higher risk of drought stress & desiccation).
    
    Provisional Thresholds:
    - Rootzone moisture <= 0.25: Score = 100.0 (Severe moisture deficit / plant wilting regime)
    - Rootzone moisture >= 0.75: Score = 0.0 (Adequate moisture buffer / near field capacity)
    - Intermediate (0.25 to 0.75): Linear interpolation
    """
    if rootzone_moisture <= 0.25:
        score = 100.0
    elif rootzone_moisture >= 0.75:
        score = 0.0
    else:
        score = 100.0 * (0.75 - rootzone_moisture) / (0.75 - 0.25)
    
    note = (
        f"Root-zone wetness fraction = {rootzone_moisture:.3f}. "
        f"Deficit mapped from 0.75 (no stress) to 0.25 (acute stress)."
    )
    return round(float(score), 2), note


def calculate_buffering_factor(rootzone_moisture: Optional[float]) -> Tuple[float, str]:
    """
    Calculate the moisture-buffering factor beta in [BUFFERING_MIN_PENALTY_FACTOR, 1.0].
    
    Rationale:
    Low precipitation is a meteorological recharge deficit. If root-zone moisture
    is high (e.g. from irrigation, capillary rise, or prior rain), the soil profile
    is not in active desiccation; thus the precipitation penalty is mitigated.
    If root-zone moisture is depleted, meteorological drought translates directly into
    soil water stress, retaining full penalty.
    """
    if rootzone_moisture is None or np.isnan(rootzone_moisture):
        return 1.0, "Root-zone moisture unobserved; retaining 100% of precipitation penalty."

    if rootzone_moisture <= BUFFERING_MOISTURE_LOW_THRESHOLD:
        factor = 1.0
        note = (
            f"Root-zone moisture ({rootzone_moisture:.3f}) <= {BUFFERING_MOISTURE_LOW_THRESHOLD}; "
            "retaining 100% of meteorological recharge deficit penalty."
        )
    elif rootzone_moisture >= BUFFERING_MOISTURE_ADEQUATE_THRESHOLD:
        factor = BUFFERING_MIN_PENALTY_FACTOR
        note = (
            f"Root-zone moisture ({rootzone_moisture:.3f}) >= {BUFFERING_MOISTURE_ADEQUATE_THRESHOLD}; "
            f"moisture-buffering relief applied (penalty reduced to {int(BUFFERING_MIN_PENALTY_FACTOR * 100)}%)."
        )
    else:
        frac = (rootzone_moisture - BUFFERING_MOISTURE_LOW_THRESHOLD) / (
            BUFFERING_MOISTURE_ADEQUATE_THRESHOLD - BUFFERING_MOISTURE_LOW_THRESHOLD
        )
        factor = 1.0 - (1.0 - BUFFERING_MIN_PENALTY_FACTOR) * frac
        note = (
            f"Root-zone moisture ({rootzone_moisture:.3f}) provides intermediate buffering "
            f"(penalty multiplier: {factor:.2f})."
        )

    return round(float(factor), 4), note


def calculate_precipitation_deficit_score(
    precip_3m_mean: Optional[float],
    current_precip: Optional[float],
    rootzone_moisture: Optional[float] = None,
    allow_partial: bool = True
) -> Tuple[Optional[float], Optional[float], float, str, bool]:
    """
    Compute moisture-buffered meteorological recharge deficit sub-score [0, 100].
    
    Indicator: 3-month rolling mean precipitation (mm/day) with root-zone moisture buffering.
    Direction: Inverted (Lower precipitation -> Higher recharge deficit; mitigated when root-zone is wet).
    
    Provisional Thresholds:
    - Mean precip <= 0.5 mm/day (~15 mm/month): Raw Score = 100.0 (Acute dry quarter)
    - Mean precip >= 6.0 mm/day (~180 mm/month): Raw Score = 0.0 (Abundant monsoon replenishment)
    - Intermediate (0.5 to 6.0 mm/day): Linear interpolation
    
    Moisture Buffering:
    Adjusted Score = Raw Score * Buffering Factor
    Where Buffering Factor is in [0.50, 1.00] based on rootzone_moisture.
    
    Returns:
        (adjusted_score, raw_unbuffered_score, buffering_factor, explanation_note, is_fallback_used)
    """
    rate: Optional[float] = None
    is_fallback = False
    
    def _is_nan(val: Any) -> bool:
        if val is None:
            return True
        if isinstance(val, (float, np.floating)):
            return bool(np.isnan(val))
        return False

    if precip_3m_mean is not None and not _is_nan(precip_3m_mean):
        try:
            rate = float(precip_3m_mean)
            prefix = f"3-month rolling mean precip = {rate:.2f} mm/day."
        except (ValueError, TypeError):
            rate = None
    if rate is None and allow_partial and current_precip is not None and not _is_nan(current_precip):
        try:
            rate = float(current_precip)
            is_fallback = True
            prefix = f"Single-month precip fallback = {rate:.2f} mm/day (3-month rolling history unobserved at boundary)."
        except (ValueError, TypeError):
            rate = None

    if rate is None:
        return None, None, 1.0, "3-month rolling precipitation unobserved and fallback unavailable.", False

    # Guard: Rate must be a finite, non-negative number within terrestrial bounds [0, 500] mm/day
    if np.isinf(rate) or rate < 0.0 or rate > 500.0:
        return None, None, 1.0, f"Invalid precipitation rate: {rate} (must be finite in [0.0, 500.0] mm/day).", False

    # Unbuffered raw score
    if rate <= 0.5:
        raw_score = 100.0
    elif rate >= 6.0:
        raw_score = 0.0
    else:
        raw_score = 100.0 * (6.0 - rate) / (6.0 - 0.5)

    # Apply moisture buffering
    buffering_factor, buffer_note = calculate_buffering_factor(rootzone_moisture)
    adjusted_score = round(float(raw_score * buffering_factor), 2)
    raw_score = round(float(raw_score), 2)

    note = (
        f"{prefix} Raw meteorological deficit = {raw_score}/100. "
        f"{buffer_note} Final buffered score = {adjusted_score}/100."
    )
    return adjusted_score, raw_score, buffering_factor, note, is_fallback


def calculate_thermal_stress_score(soil_temp_c: float) -> Tuple[float, str]:
    """
    Compute topsoil thermal stress sub-score [0, 100].
    
    Indicator: Topsoil Layer 1 (0-10cm) Temperature in degrees Celsius.
    Direction: Direct (Higher temperature -> Higher thermal stress, evaporation & biological strain).
    
    Provisional Thresholds:
    - Soil temp <= 24.0 C: Score = 0.0 (Moderate to cool, minimal thermal stress)
    - Soil temp >= 38.0 C: Score = 100.0 (Extreme heat stress, rapid organic matter breakdown)
    - Intermediate (24.0 to 38.0 C): Linear interpolation
    """
    if soil_temp_c <= 24.0:
        score = 0.0
    elif soil_temp_c >= 38.0:
        score = 100.0
    else:
        score = 100.0 * (soil_temp_c - 24.0) / (38.0 - 24.0)

    note = (
        f"Topsoil temperature = {soil_temp_c:.2f} C. "
        f"Stress mapped from 24.0 C (favorable) to 38.0 C (extreme thermal load)."
    )
    return round(float(score), 2), note


def calculate_soc_vulnerability_score(topsoil_soc_g_kg: float) -> Tuple[float, str]:
    """
    Compute static soil organic carbon vulnerability sub-score [0, 100].
    
    Indicator: Topsoil SOC concentration in g/kg (depth-weighted 0-30cm baseline).
    Direction: Inverted (Lower SOC -> Lower structural resilience, higher vulnerability).
    
    Provisional Thresholds:
    - SOC <= 5.0 g/kg (0.5%): Score = 100.0 (Severely depleted organic buffer, high erosion risk)
    - SOC >= 25.0 g/kg (2.5%): Score = 0.0 (Rich organic matter, optimal soil aggregation)
    - Intermediate (5.0 to 25.0 g/kg): Linear interpolation
    """
    if topsoil_soc_g_kg <= 5.0:
        score = 100.0
    elif topsoil_soc_g_kg >= 25.0:
        score = 0.0
    else:
        score = 100.0 * (25.0 - topsoil_soc_g_kg) / (25.0 - 5.0)

    note = (
        f"Static topsoil SOC baseline = {topsoil_soc_g_kg:.2f} g/kg. "
        f"Vulnerability scaled from 25.0 g/kg (high resilience) to 5.0 g/kg (depleted)."
    )
    return round(float(score), 2), note


def calculate_ph_deviation_score(topsoil_ph: float) -> Tuple[float, str]:
    """
    Compute soil pH deviation sub-score [0, 100].
    
    Indicator: Soil pH in H2O solution (depth-weighted 0-30cm baseline).
    Direction: Non-linear deviation from optimal neutral agronomic band [6.5, 7.5].
    
    Provisional Thresholds:
    - 6.5 <= pH <= 7.5: Score = 0.0 (Optimal nutrient availability and biological buffering)
    - Distance d = max(0, 6.5 - pH) if acidic, max(0, pH - 7.5) if alkaline.
    - Deviation of >= 2.0 pH units (e.g., pH <= 4.5 or pH >= 9.5) -> Score = 100.0
    """
    if 6.5 <= topsoil_ph <= 7.5:
        dev = 0.0
    elif topsoil_ph < 6.5:
        dev = 6.5 - topsoil_ph
    else:
        dev = topsoil_ph - 7.5

    score = min(100.0, 100.0 * (dev / 2.0))
    note = (
        f"Static topsoil pH baseline = {topsoil_ph:.2f}. "
        f"Deviation from [6.5, 7.5] neutral window = {dev:.2f} pH units."
    )
    return round(float(score), 2), note


# ---------------------------------------------------------------------------
# Structured Result Containers
# ---------------------------------------------------------------------------

@dataclass
class RiskScoringResult:
    score: Optional[float]
    risk_category: str
    status: str
    dynamic_environmental_stress: Optional[float]
    baseline_soil_vulnerability: Optional[float]
    indicators: Dict[str, Dict[str, Any]]
    explanation: str
    index_name: str = INDEX_NAME
    assumptions_label: str = ASSUMPTIONS_LABEL

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to standard dictionary for serialization."""
        return {
            "score": self.score,
            "risk_category": self.risk_category,
            "status": self.status,
            "index_name": self.index_name,
            "dynamic_environmental_stress": self.dynamic_environmental_stress,
            "baseline_soil_vulnerability": self.baseline_soil_vulnerability,
            "indicators": self.indicators,
            "explanation": self.explanation,
            "assumptions_label": self.assumptions_label,
        }


# ---------------------------------------------------------------------------
# Main Reusable Scoring Logic
# ---------------------------------------------------------------------------

def classify_risk_category(score: Optional[float]) -> str:
    """
    Map numerical score [0, 100] to explicit risk categories.
    
    Thresholds:
    - Low Risk:    0.0 <= score < 35.0
    - Medium Risk: 35.0 <= score < 65.0
    - High Risk:   65.0 <= score <= 100.0
    """
    if score is None or np.isnan(score):
        return "UNKNOWN"
    if score < THRESHOLD_LOW_UPPER:
        return "Low"
    elif score < THRESHOLD_MEDIUM_UPPER:
        return "Medium"
    else:
        return "High"


def validate_input_record(record: Union[Dict[str, Any], pd.Series]) -> Tuple[bool, str]:
    """
    Validate that mandatory raw features are present and within physical bounds.
    """
    essential_fields = [
        ("soil_moisture_rootzone_fraction", 0.0, 1.0, "Root-zone soil wetness fraction"),
        ("soil_temperature_layer1_c", -50.0, 60.0, "Soil temperature layer 1"),
        ("topsoil_soc_g_kg", 0.0, 500.0, "Topsoil organic carbon"),
        ("topsoil_ph_mean", 2.0, 12.0, "Topsoil pH"),
    ]

    for field_name, min_val, max_val, desc in essential_fields:
        if field_name not in record:
            return False, f"Missing essential field: '{field_name}'"
        val = record[field_name]
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return False, f"Null or NaN in essential field: '{field_name}'"
        try:
            float_val = float(val)
        except (ValueError, TypeError):
            return False, f"Non-numeric value in field '{field_name}': {val}"
        if not (min_val <= float_val <= max_val):
            return False, f"Field '{field_name}' value {float_val} out of physical bounds [{min_val}, {max_val}]"

    precip = record.get("precipitation_mm_day")
    if precip is not None and not (isinstance(precip, float) and np.isnan(precip)):
        try:
            f_precip = float(precip)
            if np.isinf(f_precip):
                return False, f"Infinite precipitation detected: {precip}"
            if f_precip < 0.0:
                return False, f"Negative precipitation detected: {precip}"
            if f_precip > 500.0:
                return False, f"Precipitation out of physical bounds [0, 500] mm/day: {precip}"
        except (ValueError, TypeError):
            return False, f"Non-numeric precipitation: {precip}"

    precip_3m = record.get("precipitation_rolling_3m_mean_mm_day")
    if precip_3m is not None and not (isinstance(precip_3m, float) and np.isnan(precip_3m)):
        try:
            f_precip_3m = float(precip_3m)
            if np.isinf(f_precip_3m):
                return False, f"Infinite rolling precipitation detected: {precip_3m}"
            if f_precip_3m < 0.0:
                return False, f"Negative rolling precipitation detected: {precip_3m}"
            if f_precip_3m > 500.0:
                return False, f"Rolling precipitation out of physical bounds [0, 500] mm/day: {precip_3m}"
        except (ValueError, TypeError):
            return False, f"Non-numeric rolling precipitation: {precip_3m}"

    return True, "Valid record"


def calculate_baseline_risk_score(
    record: Union[Dict[str, Any], pd.Series],
    allow_partial: bool = True
) -> RiskScoringResult:
    """
    Compute the Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index for a record.

    Parameters:
        record: Mapping or pd.Series containing feature values (from feature_table.csv).
        allow_partial: If True, allows a single-month precipitation fallback when
                       the 3-month rolling mean precipitation is unobserved (e.g. at
                       sequence start). If False, returns INSUFFICIENT_HISTORY with score=None.

    Returns:
        RiskScoringResult with score, category, status, sub-scores, and explanation.
    """
    # 1. Input Validation
    is_valid, validation_msg = validate_input_record(record)
    if not is_valid:
        return RiskScoringResult(
            score=None,
            risk_category="UNKNOWN",
            status="INVALID_INPUT",
            dynamic_environmental_stress=None,
            baseline_soil_vulnerability=None,
            indicators={},
            explanation=f"Cannot compute index: {validation_msg}."
        )

    # 2. Extract feature values safely
    rootzone_moisture = float(record["soil_moisture_rootzone_fraction"])
    soil_temp_c = float(record["soil_temperature_layer1_c"])
    topsoil_soc = float(record["topsoil_soc_g_kg"])
    topsoil_ph = float(record["topsoil_ph_mean"])

    precip_3m = record.get("precipitation_rolling_3m_mean_mm_day")
    precip_current = record.get("precipitation_mm_day")

    # 3. Compute Sub-scores (with moisture buffering on precipitation)
    score_moisture, note_moisture = calculate_moisture_deficit_score(rootzone_moisture)
    score_precip, raw_precip_score, buffering_factor, note_precip, is_precip_fallback = calculate_precipitation_deficit_score(
        precip_3m,
        precip_current,
        rootzone_moisture=rootzone_moisture,
        allow_partial=allow_partial
    )
    score_thermal, note_thermal = calculate_thermal_stress_score(soil_temp_c)
    score_soc, note_soc = calculate_soc_vulnerability_score(topsoil_soc)
    score_ph, note_ph = calculate_ph_deviation_score(topsoil_ph)

    # 4. Handle Missing Rolling Precipitation
    if score_precip is None:
        return RiskScoringResult(
            score=None,
            risk_category="UNKNOWN",
            status="INSUFFICIENT_HISTORY",
            dynamic_environmental_stress=None,
            baseline_soil_vulnerability=None,
            indicators={},
            explanation=(
                "Calculation halted: 3-month rolling precipitation is unobserved at this record boundary. "
                "Per project constraints, missing historical lag features are not silently zero-imputed. "
                "Set allow_partial=True to evaluate using provisional single-month precipitation fallback."
            )
        )

    # 5. Aggregate Sub-scores
    # Dynamic Environmental Stressors (0.70 weight total)
    dynamic_weights = WEIGHT_MOISTURE_DEFICIT + WEIGHT_PRECIPITATION_DEFICIT + WEIGHT_THERMAL_STRESS
    weighted_dynamic = (
        (score_moisture * WEIGHT_MOISTURE_DEFICIT)
        + (score_precip * WEIGHT_PRECIPITATION_DEFICIT)
        + (score_thermal * WEIGHT_THERMAL_STRESS)
    )
    # Normalized dynamic sub-index [0, 100]
    dynamic_index = weighted_dynamic / dynamic_weights

    # Static Baseline Soil Vulnerability (0.30 weight total)
    baseline_weights = WEIGHT_SOC_DEPLETION + WEIGHT_PH_DEVIATION
    weighted_baseline = (
        (score_soc * WEIGHT_SOC_DEPLETION)
        + (score_ph * WEIGHT_PH_DEVIATION)
    )
    # Normalized baseline sub-index [0, 100]
    baseline_index = weighted_baseline / baseline_weights

    # Total composite index score [0, 100]
    composite_score = round(weighted_dynamic + weighted_baseline, 2)
    composite_score = max(0.0, min(100.0, composite_score))

    risk_category = classify_risk_category(composite_score)
    status = "PROVISIONAL_PARTIAL_HISTORY" if is_precip_fallback else "COMPLETE"

    # 6. Build Indicator Detailed Mapping
    indicators_dict: Dict[str, Dict[str, Any]] = {
        "moisture_deficit": {
            "name": "Root-zone Soil Moisture Deficit",
            "sub_score": score_moisture,
            "weight": WEIGHT_MOISTURE_DEFICIT,
            "weighted_score": round(score_moisture * WEIGHT_MOISTURE_DEFICIT, 2),
            "direction": "Lower moisture -> Higher risk",
            "raw_value": rootzone_moisture,
            "unit": "fraction (0-1)",
            "scientific_rationale": "Direct measure of water availability for crops; desiccation degrades microbial habitats and structure.",
            "notes": note_moisture,
        },
        "precipitation_deficit": {
            "name": "Meteorological Recharge Deficit (Moisture-Buffered)",
            "sub_score": score_precip,
            "raw_unbuffered_score": raw_precip_score,
            "moisture_buffering_factor": buffering_factor,
            "weight": WEIGHT_PRECIPITATION_DEFICIT,
            "weighted_score": round(score_precip * WEIGHT_PRECIPITATION_DEFICIT, 2),
            "direction": "Lower precipitation -> Higher recharge deficit; mitigated when root-zone moisture is adequate.",
            "raw_value": precip_3m if not is_precip_fallback else precip_current,
            "unit": "mm/day",
            "scientific_rationale": "Atmospheric recharge deficit. Buffered by root-zone soil water to prevent false drought alerts during irrigation.",
            "notes": note_precip,
        },
        "thermal_stress": {
            "name": "Topsoil Thermal Stress",
            "sub_score": score_thermal,
            "weight": WEIGHT_THERMAL_STRESS,
            "weighted_score": round(score_thermal * WEIGHT_THERMAL_STRESS, 2),
            "direction": "Higher temperature -> Higher stress",
            "raw_value": soil_temp_c,
            "unit": "degrees Celsius",
            "scientific_rationale": "High topsoil temperatures accelerate organic oxidation and elevate evaporative demand.",
            "notes": note_thermal,
        },
        "soc_vulnerability": {
            "name": "Static SOC Depletion Vulnerability",
            "sub_score": score_soc,
            "weight": WEIGHT_SOC_DEPLETION,
            "weighted_score": round(score_soc * WEIGHT_SOC_DEPLETION, 2),
            "direction": "Lower SOC -> Higher vulnerability",
            "raw_value": topsoil_soc,
            "unit": "g/kg",
            "scientific_rationale": "Depleted organic carbon reduces aggregate stability, cation retention, and water holding capacity.",
            "notes": note_soc,
        },
        "ph_deviation": {
            "name": "Static pH Neutrality Deviation",
            "sub_score": score_ph,
            "weight": WEIGHT_PH_DEVIATION,
            "weighted_score": round(score_ph * WEIGHT_PH_DEVIATION, 2),
            "direction": "Greater distance from [6.5, 7.5] -> Higher vulnerability",
            "raw_value": topsoil_ph,
            "unit": "pH units",
            "scientific_rationale": "Deviations from neutrality trigger nutrient precipitation and micronutrient imbalances.",
            "notes": note_ph,
        },
    }

    # 7. Formulate Human-Readable Explanation
    top_driver = max(
        indicators_dict.items(),
        key=lambda item: item[1]["weighted_score"]
    )
    driver_name = top_driver[1]["name"]
    driver_score = top_driver[1]["sub_score"]

    date_str = str(record.get("date", "Unknown date"))
    explanation = (
        f"Record [{date_str}] Index: {composite_score}/100 ({risk_category} Risk). "
        f"Dynamic Environmental Stress: {dynamic_index:.1f}/100; "
        f"Static Baseline Soil Vulnerability: {baseline_index:.1f}/100. "
        f"Primary risk driver is '{driver_name}' (sub-score: {driver_score:.1f}/100). "
    )
    if is_precip_fallback:
        explanation += (
            "(Notice: Evaluated with provisional single-month precipitation fallback "
            "because 3-month rolling history is unobserved at dataset boundary)."
        )

    return RiskScoringResult(
        score=composite_score,
        risk_category=risk_category,
        status=status,
        dynamic_environmental_stress=round(float(dynamic_index), 2),
        baseline_soil_vulnerability=round(float(baseline_index), 2),
        indicators=indicators_dict,
        explanation=explanation,
        index_name=INDEX_NAME,
        assumptions_label=ASSUMPTIONS_LABEL,
    )


def score_feature_dataframe(
    df: pd.DataFrame,
    allow_partial: bool = True
) -> pd.DataFrame:
    """
    Apply the Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index
    across a pandas DataFrame of feature records.
    
    Returns a copy of the DataFrame with added index columns, preserving
    the original input table unchanged.
    """
    df_scored = df.copy()
    
    scores: List[Optional[float]] = []
    categories: List[str] = []
    statuses: List[str] = []
    dynamic_stresses: List[Optional[float]] = []
    baseline_vulns: List[Optional[float]] = []
    explanations: List[str] = []

    for _, row in df_scored.iterrows():
        res = calculate_baseline_risk_score(row, allow_partial=allow_partial)
        scores.append(res.score)
        categories.append(res.risk_category)
        statuses.append(res.status)
        dynamic_stresses.append(res.dynamic_environmental_stress)
        baseline_vulns.append(res.baseline_soil_vulnerability)
        explanations.append(res.explanation)

    df_scored["baseline_risk_score"] = scores
    df_scored["risk_category"] = categories
    df_scored["risk_status"] = statuses
    df_scored["dynamic_environmental_stress"] = dynamic_stresses
    df_scored["baseline_soil_vulnerability"] = baseline_vulns
    df_scored["risk_explanation"] = explanations

    return df_scored


# ---------------------------------------------------------------------------
# Self-Inspection and Demonstration CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent.parent
    feature_table_path = project_root / "data" / "feature_table.csv"

    print("=====================================================================")
    print("Soil Sentinel - Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index")
    print("Provisional Rule-Based Indicator (Not a Validated Degradation Model)")
    print("=====================================================================")

    if not feature_table_path.exists():
        print(f"Error: {feature_table_path} not found.")
        sys.exit(1)

    df_features = pd.read_csv(feature_table_path)
    print(f"Loaded feature table: {df_features.shape[0]} records from {df_features['date'].min()} to {df_features['date'].max()}.\n")

    # Evaluate with allow_partial=True
    df_evaluated = score_feature_dataframe(df_features, allow_partial=True)

    print("--- Historical Index Distribution Summary (5 Years, 60 Months) ---")
    score_series = df_evaluated["baseline_risk_score"].dropna()
    print(f"Score Range:    {score_series.min():.2f} to {score_series.max():.2f}")
    print(f"Mean Score:     {score_series.mean():.2f}")
    print(f"Median Score:   {score_series.median():.2f}")
    print("\nCategory Breakdown:")
    print(df_evaluated["risk_category"].value_counts())
    print("\nCalculation Status Breakdown:")
    print(df_evaluated["risk_status"].value_counts())

    print("\n--- First 3 Boundary Months (Handling of Missing Rolling Features) ---")
    for idx in range(3):
        row = df_evaluated.iloc[idx]
        print(f"Month {row['date']}: Score = {row['baseline_risk_score']}, Status = {row['risk_status']}")
        print(f"  Explanation: {row['risk_explanation']}\n")

    print("--- Peak Stress Month ---")
    highest_idx = df_evaluated["baseline_risk_score"].idxmax()
    peak_row = df_evaluated.loc[highest_idx]
    print(f"Date: {peak_row['date']} (Season: {peak_row['season']})")
    print(f"Score: {peak_row['baseline_risk_score']} | Category: {peak_row['risk_category']}")
    print(f"Explanation: {peak_row['risk_explanation']}\n")

    print("--- Minimum Stress Month ---")
    lowest_idx = df_evaluated["baseline_risk_score"].idxmin()
    min_row = df_evaluated.loc[lowest_idx]
    print(f"Date: {min_row['date']} (Season: {min_row['season']})")
    print(f"Score: {min_row['baseline_risk_score']} | Category: {min_row['risk_category']}")
    print(f"Explanation: {min_row['risk_explanation']}\n")

    print("Baseline scoring module ready.")
