"""
Soil Sentinel - Baseline versus Hypothetical Scenario Comparison Engine.

Reuses the existing scenario engine in `src.Model.outlook` to perform defensible,
transparent comparisons between a baseline observation (or historical record)
and hypothetical meteorological stress scenarios.

CRITICAL SCIENTIFIC PRINCIPLES:
1. STRICT TRANSPARENCY:
   Scenarios are labeled formally as HYPOTHETICAL_SCENARIO. They are exploratory
   stress-tests for resilience planning, NOT empirical or probabilistic forecasts.
2. DELTA QUANTIFICATION:
   Quantifies explicit stress deltas (Delta Score, Delta Recharge Deficit, Delta Thermal Load)
   relative to the baseline condition.
3. SITE RESILIENCE ATTRIBUTION:
   Attributes sensitivity to static baseline soil vulnerability: a site with low SOC (< 5 g/kg)
   exhibits lower buffering capacity and higher vulnerability under acute dry spells than
   organic-rich soils.
4. CODE REUSE:
   Directly reuses `evaluate_scenario_outlook` and `SCENARIO_PRESETS` from `src.Model.outlook`.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from src.Model.risk_scoring import (
    calculate_baseline_risk_score,
    RiskScoringResult,
)
from src.Model.outlook import (
    evaluate_scenario_outlook,
    OutlookResult,
    SCENARIO_PRESETS,
    SCENARIO_LABEL,
)


@dataclass
class ScenarioComparisonItem:
    """Detailed delta comparison between baseline and a single hypothetical scenario."""
    scenario_name: str
    scenario_description: str
    horizon_days: int
    scenario_atmospheric_score: float
    scenario_recharge_deficit: float
    scenario_thermal_load: float
    baseline_score: Optional[float]
    baseline_category: str
    delta_score: Optional[float]  # Scenario score - Baseline score
    category_shift: str           # "UNCHANGED", "INCREASED_STRESS", "DECREASED_STRESS", "INCONCLUSIVE"
    recharge_deficit_delta: Optional[float]
    thermal_load_delta: Optional[float]
    resilience_assessment: str
    assumptions: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BaselineScenarioComparisonReport:
    """Comprehensive comparison report across multiple hypothetical scenarios."""
    status: str
    baseline_date: Optional[str]
    baseline_score: Optional[float]
    baseline_category: str
    static_soil_resilience: str
    comparisons: Dict[str, ScenarioComparisonItem] = field(default_factory=dict)
    most_adverse_scenario: Optional[str] = None
    most_favorable_scenario: Optional[str] = None
    summary_narrative: str = ""
    disclaimer: str = (
        "SoilSentinel scenario comparisons evaluate exploratory, synthetic meteorological "
        "assumptions for risk stress-testing. No probability of occurrence or predictive "
        "forecast skill is claimed for 30-day projection horizons."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "baseline_date": self.baseline_date,
            "baseline_score": self.baseline_score,
            "baseline_category": self.baseline_category,
            "static_soil_resilience": self.static_soil_resilience,
            "comparisons": {k: v.to_dict() for k, v in self.comparisons.items()},
            "most_adverse_scenario": self.most_adverse_scenario,
            "most_favorable_scenario": self.most_favorable_scenario,
            "summary_narrative": self.summary_narrative,
            "disclaimer": self.disclaimer,
        }


def _classify_static_resilience(soc_val: Optional[float], ph_val: Optional[float]) -> str:
    """Classify intrinsic soil buffering capacity from static SOC and pH."""
    if soc_val is None or ph_val is None:
        return "UNKNOWN"
    if soc_val >= 20.0 and 6.5 <= ph_val <= 7.5:
        return "HIGH_RESILIENCE"
    elif soc_val < 7.0 or ph_val < 5.5 or ph_val > 8.5:
        return "LOW_RESILIENCE_VULNERABLE"
    else:
        return "MODERATE_RESILIENCE"


def compare_baseline_to_scenarios(
    baseline_record: Union[Dict[str, Any], pd.Series, RiskScoringResult],
    scenarios: Optional[List[str]] = None,
    custom_precipitation: Optional[float] = None,
    custom_temperature: Optional[float] = None,
    horizon_days: int = 30
) -> BaselineScenarioComparisonReport:
    """
    Compare a baseline evaluation record against hypothetical meteorological scenarios.

    Parameters:
        baseline_record: Raw feature record (dict/Series) or pre-calculated RiskScoringResult.
        scenarios: List of scenario preset names to evaluate. Defaults to
                   ["dry_spell", "normal_climatology", "heavy_rainfall"].
        custom_precipitation: Optional precipitation rate for 'custom' scenario (mm/day).
        custom_temperature: Optional air temperature for 'custom' scenario (C).
        horizon_days: Projection window in days (default: 30).

    Returns:
        Structured BaselineScenarioComparisonReport.
    """
    if scenarios is None:
        scenarios = ["dry_spell", "normal_climatology", "heavy_rainfall"]

    # 1. Resolve Baseline Score and Indicators
    raw_dict: Dict[str, Any] = {}
    if isinstance(baseline_record, RiskScoringResult):
        b_res = baseline_record
        b_score = b_res.score
        b_cat = b_res.risk_category
        b_status = b_res.status
        b_date = None
        soc_val = None
        ph_val = None
        baseline_recharge_deficit = b_res.indicators.get("precipitation_deficit", {}).get("raw_unbuffered_score")
        baseline_thermal_load = b_res.indicators.get("thermal_stress", {}).get("sub_score")
    else:
        raw_dict = baseline_record.to_dict() if isinstance(baseline_record, pd.Series) else dict(baseline_record)
        b_date = str(raw_dict.get("date") or "UNKNOWN")
        b_res = calculate_baseline_risk_score(raw_dict, allow_partial=True)
        b_score = b_res.score
        b_cat = b_res.risk_category
        b_status = b_res.status
        soc_val = float(raw_dict.get("topsoil_soc_g_kg", 12.95)) if raw_dict.get("topsoil_soc_g_kg") is not None else None
        ph_val = float(raw_dict.get("topsoil_ph_mean", 6.55)) if raw_dict.get("topsoil_ph_mean") is not None else None
        baseline_recharge_deficit = b_res.indicators.get("precipitation_deficit", {}).get("raw_unbuffered_score")
        baseline_thermal_load = b_res.indicators.get("thermal_stress", {}).get("sub_score")

    static_resilience = _classify_static_resilience(soc_val, ph_val)

    if b_status in ("INVALID_INPUT", "INSUFFICIENT_HISTORY"):
        return BaselineScenarioComparisonReport(
            status=b_status,
            baseline_date=b_date,
            baseline_score=None,
            baseline_category="UNKNOWN",
            static_soil_resilience=static_resilience,
            summary_narrative=f"Scenario comparison aborted: Baseline data evaluation status is '{b_status}'."
        )

    # 2. Evaluate Each Scenario and Compute Deltas
    comparisons: Dict[str, ScenarioComparisonItem] = {}
    scores_dict: Dict[str, float] = {}

    for s_name in scenarios:
        # Evaluate scenario via existing outlook engine
        if s_name == "custom":
            if custom_precipitation is None or custom_temperature is None:
                continue
            s_res: OutlookResult = evaluate_scenario_outlook(
                scenario_name="custom",
                antecedent_record=raw_dict or None,
                custom_daily_precipitation=custom_precipitation,
                custom_daily_air_temperature=custom_temperature,
                horizon_days=horizon_days
            )
            desc = f"Custom scenario: {custom_precipitation:.1f} mm/day, {custom_temperature:.1f} C"
        else:
            s_res = evaluate_scenario_outlook(
                scenario_name=s_name,
                antecedent_record=raw_dict or None,
                horizon_days=horizon_days
            )
            desc = SCENARIO_PRESETS.get(s_name, {}).get("description", s_name)

        s_atm_score = float(s_res.score or 0.0)
        s_recharge_score = float(s_res.atmospheric_recharge_deficit_score or 0.0)
        s_thermal_score = float(s_res.atmospheric_thermal_load_score or 0.0)
        scores_dict[s_name] = s_atm_score

        # Calculate deltas relative to baseline
        delta_score = round(s_atm_score - b_score, 2) if b_score is not None else None
        
        recharge_delta = None
        if baseline_recharge_deficit is not None:
            recharge_delta = round(s_recharge_score - float(baseline_recharge_deficit), 2)

        thermal_delta = None
        if baseline_thermal_load is not None:
            thermal_delta = round(s_thermal_score - float(baseline_thermal_load), 2)

        # Categorize shift
        if delta_score is None:
            shift = "INCONCLUSIVE"
        elif delta_score > 5.0:
            shift = "INCREASED_STRESS"
        elif delta_score < -5.0:
            shift = "DECREASED_STRESS"
        else:
            shift = "UNCHANGED"

        # Resilience interpretation
        if s_name == "dry_spell":
            if static_resilience == "LOW_RESILIENCE_VULNERABLE":
                resilience_note = (
                    "High vulnerability: Depleted soil baseline (low SOC/sub-optimal pH) lacks buffering capacity, "
                    "amplifying agricultural risk under prolonged dry spells."
                )
            else:
                resilience_note = (
                    "Moderate buffering: Existing soil organic matter provides temporary structural water retention, "
                    "damping initial acute desiccation."
                )
        elif s_name == "heavy_rainfall":
            resilience_note = (
                "Recharge pulse: Eliminates atmospheric recharge deficit but requires adequate surface drainage "
                "to prevent waterlogging and anaerobic root conditions."
            )
        else:
            resilience_note = "Transition season baseline: Near long-term climatological equilibrium."

        comparisons[s_name] = ScenarioComparisonItem(
            scenario_name=s_name,
            scenario_description=desc,
            horizon_days=horizon_days,
            scenario_atmospheric_score=s_atm_score,
            scenario_recharge_deficit=s_recharge_score,
            scenario_thermal_load=s_thermal_score,
            baseline_score=b_score,
            baseline_category=b_cat,
            delta_score=delta_score,
            category_shift=shift,
            recharge_deficit_delta=recharge_delta,
            thermal_load_delta=thermal_delta,
            resilience_assessment=resilience_note,
            assumptions=s_res.assumptions
        )

    # 3. Determine Extremes
    most_adverse = max(scores_dict, key=scores_dict.get) if scores_dict else None
    most_favorable = min(scores_dict, key=scores_dict.get) if scores_dict else None

    # 4. Generate Summary Narrative
    narrative = (
        f"Baseline evaluation ({b_date or 'record'}) has overall risk score {b_score:.2f} ({b_cat}). "
        f"Under hypothetical 30-day stress simulation, '{most_adverse}' induces peak atmospheric stress "
        f"({scores_dict.get(most_adverse, 0.0):.1f}/100), whereas '{most_favorable}' provides lowest stress "
        f"({scores_dict.get(most_favorable, 0.0):.1f}/100). "
        f"Regional soil buffering status: {static_resilience}."
    )

    return BaselineScenarioComparisonReport(
        status="COMPLETE",
        baseline_date=b_date,
        baseline_score=b_score,
        baseline_category=b_cat,
        static_soil_resilience=static_resilience,
        comparisons=comparisons,
        most_adverse_scenario=most_adverse,
        most_favorable_scenario=most_favorable,
        summary_narrative=narrative
    )
