"""
Soil Sentinel - Transparent Ranked Prevention & Restoration Recommendation Engine.

Generates prioritized, evidence-based agronomic recommendations derived directly
from the decomposed sub-scores and weights of the Seasonal Hydro-Thermal Stress &
Baseline Vulnerability Index.

CRITICAL PRINCIPLES:
1. TRANSPARENT & TRACEABLE:
   Recommendations are mapped directly to observed physical stressors (moisture deficit,
   precipitation deficit, thermal load, SOC depletion, pH deviation). No black-box suggestions.
2. OBJECTIVE RANKING:
   Ranked strictly by the weighted risk contribution of each indicator:
   Priority Score = Indicator Sub-score [0-100] * Indicator Weight [0-1].
3. URGENCY TIERS:
   - CRITICAL: Sub-score >= 65.0 (Severe stress driving high vulnerability)
   - HIGH: Sub-score >= 50.0 (Elevated stress requiring preventive intervention)
   - MODERATE: Sub-score >= 35.0 (Moderate stress requiring monitoring/maintenance)
   - MAINTENANCE: Sub-score < 35.0 (Favorable condition; preserve existing practices)
4. REGIONAL AGRONOMIC RELEVANCE:
   Tailored to the agro-ecological reality of the Indo-Gangetic Plains (e.g. stubble retention,
   green manuring with Sesbania, gypsum amendment for alkaline soils, precision irrigation).
5. SCIENTIFIC HUMILITY & SAFETY:
   Formally disclaims clinical or guaranteed agronomic advice. Recommends local soil laboratory
   verification and extension specialist review before capital-intensive intervention.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from src.Model.risk_scoring import (
    RiskScoringResult,
    WEIGHT_MOISTURE_DEFICIT,
    WEIGHT_PRECIPITATION_DEFICIT,
    WEIGHT_THERMAL_STRESS,
    WEIGHT_SOC_DEPLETION,
    WEIGHT_PH_DEVIATION,
)

# ---------------------------------------------------------------------------
# Structured Recommendation Data Containers
# ---------------------------------------------------------------------------

@dataclass
class RecommendationItem:
    """Individual actionable agronomic recommendation."""
    indicator_key: str
    indicator_name: str
    sub_score: float
    weight: float
    weighted_score: float
    urgency: str  # "CRITICAL", "HIGH", "MODERATE", "MAINTENANCE"
    action_type: str  # "PREVENTION", "RESTORATION", "ADAPTATION", "MAINTENANCE"
    title: str
    primary_intervention: str
    actionable_steps: List[str]
    expected_benefit: str
    observed_metric: str
    recommendation_id: str = ""
    reason: str = ""
    cost_category: str = "Low Cost"
    limitations: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RankedRecommendationPlan:
    """Complete ranked set of recommendations for a given evaluation record."""
    status: str  # "COMPLETE", "PROVISIONAL_PARTIAL_HISTORY", "INSUFFICIENT_HISTORY", "INVALID_INPUT"
    overall_risk_score: Optional[float]
    overall_risk_category: str
    primary_stressor: Optional[str]
    recommendations: List[RecommendationItem] = field(default_factory=list)
    critical_actions: List[str] = field(default_factory=list)
    disclaimer: str = (
        "SoilSentinel recommendations are heuristic screening guidelines derived from "
        "regional reanalysis and digital mapping. They do NOT replace localized laboratory "
        "soil testing, on-farm moisture probe measurements, or certified agronomic consultation."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "overall_risk_score": self.overall_risk_score,
            "overall_risk_category": self.overall_risk_category,
            "primary_stressor": self.primary_stressor,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "top_three_recommendations": [r.to_dict() for r in self.recommendations[:3]],
            "critical_actions": self.critical_actions,
            "disclaimer": self.disclaimer,
        }


# ---------------------------------------------------------------------------
# Recommendation Logic Generators per Indicator
# ---------------------------------------------------------------------------

def _classify_urgency(sub_score: float) -> str:
    if sub_score >= 65.0:
        return "CRITICAL"
    elif sub_score >= 50.0:
        return "HIGH"
    elif sub_score >= 35.0:
        return "MODERATE"
    else:
        return "MAINTENANCE"


def _recommend_moisture_deficit(
    sub_score: float,
    raw_val: Optional[float]
) -> RecommendationItem:
    urgency = _classify_urgency(sub_score)
    val_str = f"{raw_val:.3f}" if raw_val is not None else "unobserved"

    if urgency == "CRITICAL":
        title = "Emergency Root-Zone Moisture Conservation & Deficit Irrigation"
        action_type = "PREVENTION"
        primary = "Deploy immediate surface mulching and schedule urgent deficit irrigation."
        steps = [
            "Apply 5-8 cm organic mulch layer (paddy straw / crop residue) to suppress soil evaporation.",
            "Schedule deficit irrigation during evening or night hours to minimize evaporative loss.",
            "Avoid deep soil inversion or mechanical tillage which exposes moist subsoil to ambient air.",
            "Inspect root-zone depth with an auger to verify infiltration depth.",
        ]
        benefit = "Prevents permanent crop wilting, preserves root-zone microbial habitat, and halts soil crusting."
    elif urgency == "HIGH":
        title = "Deficit Irrigation Scheduling & Surface Cover Maintenance"
        action_type = "PREVENTION"
        primary = "Transition to high-efficiency moisture conservation irrigation."
        steps = [
            "Maintain continuous crop residue cover across at least 30% of soil surface.",
            "Prioritize drip irrigation or alternate-furrow irrigation over broad flood inundation.",
            "Monitor weekly root-zone moisture depletion curves.",
        ]
        benefit = "Maintains root-zone hydraulic conductivity and dampens agricultural drought vulnerability."
    elif urgency == "MODERATE":
        title = "Routine Soil Moisture Monitoring & Evaporative Protection"
        action_type = "ADAPTATION"
        primary = "Sustain standard conservation tillage and schedule replenishment as required."
        steps = [
            "Preserve surface vegetative cover or intercropped canopies.",
            "Align irrigation scheduling with short-range weather forecasts.",
        ]
        benefit = "Stabilizes moisture buffer without excessive groundwater extraction."
    else:
        title = "Preserve Optimal Root-Zone Hydrological Balance"
        action_type = "MAINTENANCE"
        primary = "Maintain existing moisture management practices."
        steps = [
            "Continue conservation tillage and periodic soil structure inspections.",
            "Avoid over-irrigation to prevent shallow perched water tables.",
        ]
        benefit = "Maintains optimal soil aeration, biological activity, and nutrient mobility."

    return RecommendationItem(
        indicator_key="moisture_deficit",
        indicator_name="Root-Zone Soil Moisture Deficit",
        sub_score=round(sub_score, 2),
        weight=WEIGHT_MOISTURE_DEFICIT,
        weighted_score=round(sub_score * WEIGHT_MOISTURE_DEFICIT, 2),
        urgency=urgency,
        action_type=action_type,
        title=title,
        primary_intervention=primary,
        actionable_steps=steps,
        expected_benefit=benefit,
        observed_metric=f"Root-zone wetness fraction = {val_str} (Sub-score: {sub_score:.1f}/100)",
        recommendation_id=f"REC-MOISTURE-{urgency[:3]}",
        reason=f"Root-zone moisture deficit is {sub_score:.1f}/100, constraining plant available water.",
        cost_category="Low Cost (Mulch) / Moderate (Micro-irrigation)",
        limitations="Requires localized crop residue mulch availability; pressurized micro-irrigation requires capital equipment."
    )


def _recommend_precipitation_deficit(
    sub_score: float,
    raw_val: Optional[float],
    buffering_factor: Optional[float]
) -> RecommendationItem:
    urgency = _classify_urgency(sub_score)
    val_str = f"{raw_val:.2f} mm/day" if raw_val is not None else "unobserved"
    buf_str = f"{buffering_factor:.2f}" if buffering_factor is not None else "1.00"

    if urgency in ("CRITICAL", "HIGH"):
        title = "Meteorological Recharge Deficit Mitigation & Rainwater Retention"
        action_type = "ADAPTATION"
        primary = "Implement localized water retention to compensate for deficient precipitation recharge."
        steps = [
            "Maintain in-field bunds and field boundaries to prevent surface runoff during sudden rain events.",
            "Utilize farm pond or community rainwater catchment structures to supplement soil profiles.",
            "Utilize moisture buffering from existing root-zone storage to stagger irrigation cycles.",
        ]
        benefit = "Buffers against extended regional dry spells and protects groundwater tables."
    elif urgency == "MODERATE":
        title = "In-Field Runoff Reduction & Seasonal Water Management"
        action_type = "PREVENTION"
        primary = "Maintain bunding and in-situ rainwater harvesting readiness."
        steps = [
            "Ensure field boundaries are reinforced to capture upcoming seasonal rainfall.",
            "Coordinate water allocation based on 3-month regional meteorological trends.",
        ]
        benefit = "Maximizes infiltration of natural rainfall and minimizes erosion risk."
    else:
        title = "Recharge Utilization & Drainage Monitoring"
        action_type = "MAINTENANCE"
        primary = "Sufficient precipitation replenishment; ensure adequate surface drainage."
        steps = [
            "Inspect field drainage pathways to prevent localized waterlogging.",
            "Capitalize on natural recharge to build subsoil moisture reserves.",
        ]
        benefit = "Optimizes natural rainfall infiltration while preventing anaerobic soil conditions."

    return RecommendationItem(
        indicator_key="precipitation_deficit",
        indicator_name="Meteorological Recharge Deficit (Moisture-Buffered)",
        sub_score=round(sub_score, 2),
        weight=WEIGHT_PRECIPITATION_DEFICIT,
        weighted_score=round(sub_score * WEIGHT_PRECIPITATION_DEFICIT, 2),
        urgency=urgency,
        action_type=action_type,
        title=title,
        primary_intervention=primary,
        actionable_steps=steps,
        expected_benefit=benefit,
        observed_metric=f"Precipitation = {val_str}, Moisture Buffering Factor = {buf_str} (Sub-score: {sub_score:.1f}/100)",
        recommendation_id=f"REC-PRECIP-{urgency[:3]}",
        reason=f"Precipitation recharge deficit is {sub_score:.1f}/100 based on 3-month rolling rainfall trends.",
        cost_category="Moderate Investment (Water Harvesting) / Low Cost (Furrow Diking)",
        limitations="Rainwater retention structures require farm land allocation and earth-moving machinery."
    )


def _recommend_thermal_stress(
    sub_score: float,
    raw_val: Optional[float]
) -> RecommendationItem:
    urgency = _classify_urgency(sub_score)
    val_str = f"{raw_val:.1f} °C" if raw_val is not None else "unobserved"

    if urgency == "CRITICAL":
        title = "Topsoil Extreme Heat Protection & Canopy Cooling"
        action_type = "PREVENTION"
        primary = "Establish protective surface groundcover immediately to avoid extreme soil overheating."
        steps = [
            "Retain dense stubble or apply straw mulch to block direct solar radiation from heating the topsoil.",
            "Implement intercropping or agroforestry border strips to provide vegetative micro-climate shading.",
            "Apply brief, light sprinkler or misting irrigation during peak afternoon heat to induce evaporative cooling.",
        ]
        benefit = "Prevents soil temperature exceeding 38°C, arresting heat-induced organic matter oxidation and root desiccation."
    elif urgency == "HIGH":
        title = "Surface Thermal Load Reduction"
        action_type = "PREVENTION"
        primary = "Deploy mulch cover and optimize canopy architecture to lower surface soil temperatures."
        steps = [
            "Maintain surface residue cover to insulate topsoil from extreme temperature swings.",
            "Avoid bare fallow periods during hot summer months.",
        ]
        benefit = "Dampens daytime peak soil temperatures and preserves beneficial rhizosphere soil microbiology."
    elif urgency == "MODERATE":
        title = "Thermal Fluctuation Monitoring"
        action_type = "ADAPTATION"
        primary = "Monitor soil temperature trends and prepare seasonal mulch cover."
        steps = [
            "Plan crop planting dates to avoid juvenile crop exposure to high heat stress periods.",
            "Maintain vegetative groundcover between cropping seasons.",
        ]
        benefit = "Maintains optimal soil temperature for root nutrient uptake and microbial decomposition."
    else:
        title = "Favorable Thermal Regime Maintenance"
        action_type = "MAINTENANCE"
        primary = "Topsoil temperatures are within optimal biological ranges."
        steps = [
            "Continue normal seasonal cultivation practices.",
        ]
        benefit = "Sustains optimal conditions for biological nitrogen fixation and root respiration."

    return RecommendationItem(
        indicator_key="thermal_stress",
        indicator_name="Topsoil Thermal Stress",
        sub_score=round(sub_score, 2),
        weight=WEIGHT_THERMAL_STRESS,
        weighted_score=round(sub_score * WEIGHT_THERMAL_STRESS, 2),
        urgency=urgency,
        action_type=action_type,
        title=title,
        primary_intervention=primary,
        actionable_steps=steps,
        expected_benefit=benefit,
        observed_metric=f"Soil layer 1 temperature = {val_str} (Sub-score: {sub_score:.1f}/100)",
        recommendation_id=f"REC-THERMAL-{urgency[:3]}",
        reason=f"Topsoil thermal stress is {sub_score:.1f}/100, which accelerates evaporative loss and microbial heat stress.",
        cost_category="Low Cost (Surface Stubble / Intercropping)",
        limitations="Surface shading provides 2-5°C canopy cooling but does not counteract regional macroclimate heatwaves alone."
    )


def _recommend_soc_vulnerability(
    sub_score: float,
    raw_val: Optional[float]
) -> RecommendationItem:
    urgency = _classify_urgency(sub_score)
    val_str = f"{raw_val:.2f} g/kg" if raw_val is not None else "unobserved"

    if urgency == "CRITICAL":
        title = "Critical Soil Organic Carbon Regeneration & Structural Rebuilding"
        action_type = "RESTORATION"
        primary = "Implement aggressive organic matter replenishment and cease residue burning."
        steps = [
            "Incorporate 10-15 tonnes/ha of well-rotted Farmyard Manure (FYM) or enriched compost prior to sowing.",
            "Strictly avoid crop residue burning; employ in-situ residue incorporation (e.g. Super Seeder / Happy Seeder).",
            "Introduce green manuring crops (e.g. Sesbania aculeata / Dhaincha or Crotalaria juncea) in summer fallow.",
            "Incorporate biochar or humic amendments to rebuild long-term recalcitrant carbon fractions.",
        ]
        benefit = "Rebuilds depleted topsoil SOC (< 5.0 g/kg), restores aggregate stability, improves water-holding capacity, and stops erosive slaking."
    elif urgency == "HIGH":
        title = "Organic Matter Augmentation & Residue Retention"
        action_type = "RESTORATION"
        primary = "Increase organic inputs and adopt non-inversion conservation agriculture."
        steps = [
            "Apply 5-8 tonnes/ha compost or vermicompost annually.",
            "Rotate cereal crops with nodulating grain legumes (e.g. chickpea, moong) to enhance biological soil inputs.",
            "Adopt reduced tillage to minimize organic carbon oxidation.",
        ]
        benefit = "Progressively elevates topsoil SOC toward regional target (> 15.0 g/kg) and strengthens soil buffering."
    elif urgency == "MODERATE":
        title = "Soil Organic Carbon Maintenance & Green Cover"
        action_type = "MAINTENANCE"
        primary = "Sustain organic matter additions to prevent progressive carbon depletion."
        steps = [
            "Maintain regular crop residue recycling and balanced organic-inorganic fertilization.",
            "Test soil organic carbon every 2-3 years to verify carbon balance.",
        ]
        benefit = "Maintains adequate biological soil structure and nutrient exchange capacity."
    else:
        title = "High Organic Carbon Resilience Preservation"
        action_type = "MAINTENANCE"
        primary = "Soil organic carbon baseline is healthy; maintain balanced conservation practices."
        steps = [
            "Continue diversified crop rotations and sustainable organic matter recycling.",
        ]
        benefit = "Ensures persistent high aggregate stability, disease suppression, and water retention."

    return RecommendationItem(
        indicator_key="soc_vulnerability",
        indicator_name="Soil Organic Carbon (SOC) Vulnerability",
        sub_score=round(sub_score, 2),
        weight=WEIGHT_SOC_DEPLETION,
        weighted_score=round(sub_score * WEIGHT_SOC_DEPLETION, 2),
        urgency=urgency,
        action_type=action_type,
        title=title,
        primary_intervention=primary,
        actionable_steps=steps,
        expected_benefit=benefit,
        observed_metric=f"Topsoil SOC = {val_str} (Sub-score: {sub_score:.1f}/100)",
        recommendation_id=f"REC-SOC-{urgency[:3]}",
        reason=f"Topsoil organic carbon vulnerability is {sub_score:.1f}/100, indicating low organic carbon buffering.",
        cost_category="Moderate Investment (FYM / Green Manure)",
        limitations="Soil organic carbon elevation requires multi-season residue retention; not an immediate single-season fix."
    )


def _recommend_ph_deviation(
    sub_score: float,
    raw_val: Optional[float]
) -> RecommendationItem:
    urgency = _classify_urgency(sub_score)
    val_str = f"{raw_val:.2f}" if raw_val is not None else "unobserved"

    # Determine whether deviation is acidic or alkaline
    is_alkaline = raw_val is not None and raw_val > 7.5
    is_acidic = raw_val is not None and raw_val < 6.5

    if urgency == "CRITICAL":
        if is_alkaline:
            title = "Soil Sodic / Alkaline Remediation & Reclamation"
            action_type = "RESTORATION"
            primary = "Apply chemical amendments (gypsum) and acidifying organic inputs to lower high soil pH."
            steps = [
                "Conduct laboratory soil test to determine Exchangeable Sodium Percentage (ESP) and Gypsum Requirement (GR).",
                "Apply agricultural grade gypsum (CaSO4·2H2O) at recommended rates followed by light leaching.",
                "Incorporate green manure (Dhaincha) during pre-monsoon to release organic acids and mobilize calcium.",
                "Use acid-forming nitrogen fertilizers (e.g. Ammonium Sulfate) in place of alkaline-inducing sources.",
            ]
            benefit = "Lowers elevated soil pH (> 8.5), displaces toxic exchangeable sodium, remedies micronutrient (Zn, Fe) immobilization, and restores infiltration."
        else:
            title = "Acid Soil Remediation & Liming Intervention"
            action_type = "RESTORATION"
            primary = "Apply agricultural lime to neutralize soil acidity and alleviate aluminum toxicity."
            steps = [
                "Conduct laboratory titration to determine exact Lime Requirement (LR).",
                "Apply finely ground agricultural limestone (CaCO3) or dolomite to raise soil pH toward 6.5.",
                "Incorporate well-rotted organic manure to buffer soil against rapid pH swings.",
            ]
            benefit = "Neutralizes acute acidity (pH < 5.0), mitigates aluminum/manganese phytotoxicity, and unlocks phosphorus availability."
    elif urgency == "HIGH":
        if is_alkaline:
            title = "Alkalinity Management & Micronutrient Chelation"
            action_type = "RESTORATION"
            primary = "Mitigate sub-optimal alkaline soil reaction and safeguard micronutrient availability."
            steps = [
                "Apply regular compost and press mud to gradually neutralize free carbonates.",
                "Apply zinc sulfate (ZnSO4) and iron chelates (Fe-EDTA) to counteract micronutrient fixation.",
                "Avoid using sodium-rich or high-RSC (Residual Sodium Carbonate) tube-well irrigation water.",
            ]
            benefit = "Counteracts nutrient lock-up and prevents structural clay dispersion."
        else:
            title = "Mild Acidity Buffering & Dolomite Addition"
            action_type = "RESTORATION"
            primary = "Apply modest liming and organic amendments to stabilize pH."
            steps = [
                "Apply light agricultural lime or wood ash as recommended by local soil testing.",
                "Incorporate compost to build biological buffering capacity.",
            ]
            benefit = "Restores balanced cation exchange and prevents further progressive soil acidification."
    elif urgency == "MODERATE":
        title = "Soil Reaction Monitoring & Balanced Fertilization"
        action_type = "ADAPTATION"
        primary = "pH shows minor deviation from optimal neutral band; monitor and balance fertilizer use."
        steps = [
            "Use balanced N-P-K fertilizer formulations with sulfur to stabilize rhizosphere pH.",
            "Test irrigation water quality for bicarbonates and electrical conductivity.",
        ]
        benefit = "Maintains optimal rhizosphere chemistry and prevents progressive deviation."
    else:
        title = "Optimal Soil pH Neutral Band Preservation"
        action_type = "MAINTENANCE"
        primary = "Soil reaction is within ideal agronomic neutral range (6.5 - 7.5)."
        steps = [
            "Continue standard balanced fertilizer management.",
            "Conduct routine biennial soil pH testing to verify long-term stability.",
        ]
        benefit = "Ensures maximum bioavailability of all essential macro- and micronutrients."

    reason = (
        f"Soil pH deviation score is {sub_score:.1f}/100 (observed pH: {val_str}), indicating "
        f"{'alkaline sodicity stress' if is_alkaline else 'acid soil stress' if is_acidic else 'mild chemical reaction deviation'}."
    )
    cost_category = "Moderate to High Investment (Chemical Amendments / Liming)" if urgency in ("CRITICAL", "HIGH") else "Low Investment (Balanced Fertilizers)"
    limitations = "Chemical amendments require precise dosage titration based on laboratory soil testing to prevent overcorrection."

    return RecommendationItem(
        indicator_key="ph_deviation",
        indicator_name="Soil pH Deviation from Optimal Neutral Band",
        sub_score=round(sub_score, 2),
        weight=WEIGHT_PH_DEVIATION,
        weighted_score=round(sub_score * WEIGHT_PH_DEVIATION, 2),
        urgency=urgency,
        action_type=action_type,
        title=title,
        primary_intervention=primary,
        actionable_steps=steps,
        expected_benefit=benefit,
        observed_metric=f"Topsoil pH = {val_str} (Sub-score: {sub_score:.1f}/100)",
        recommendation_id=f"REC-PH-{urgency[:3]}",
        reason=reason,
        cost_category=cost_category,
        limitations=limitations
    )


# ---------------------------------------------------------------------------
# Main Public Interface
# ---------------------------------------------------------------------------

def generate_ranked_recommendations(
    scoring_result: Union[RiskScoringResult, Dict[str, Any]],
    record: Optional[Union[Dict[str, Any], pd.Series]] = None
) -> RankedRecommendationPlan:
    """
    Generate ranked agronomic recommendations from a RiskScoringResult or prediction dictionary.

    Parameters:
        scoring_result: RiskScoringResult instance or prediction dictionary containing
                        status, score, risk_category, and indicators.
        record: Optional raw feature record providing physical context.

    Returns:
        Structured RankedRecommendationPlan.
    """
    # 1. Handle error or non-computable status
    if isinstance(scoring_result, RiskScoringResult):
        status = scoring_result.status
        score = scoring_result.score
        category = scoring_result.risk_category
        indicators = scoring_result.indicators
    else:
        status = str(scoring_result.get("status") or "UNKNOWN")
        score = scoring_result.get("score")
        if score is not None:
            try:
                score = float(score)
                if np.isnan(score):
                    score = None
            except (ValueError, TypeError):
                score = None
        category = str(scoring_result.get("risk_category") or "UNKNOWN")
        indicators = scoring_result.get("indicators") or {}

    if status in ("INVALID_INPUT", "INSUFFICIENT_HISTORY"):
        return RankedRecommendationPlan(
            status=status,
            overall_risk_score=None,
            overall_risk_category="UNKNOWN",
            primary_stressor=None,
            recommendations=[],
            critical_actions=[
                f"Action withheld: Scoring status is '{status}'. "
                "Ensure valid physical data inputs and complete observation history before evaluating interventions."
            ]
        )

    # 2. Extract Sub-scores and Raw Context
    rec_dict = {}
    if record is not None:
        rec_dict = record.to_dict() if isinstance(record, pd.Series) else dict(record)

    def _get_val(key: str, sub_key: str = "raw_value") -> Optional[float]:
        if key in indicators and isinstance(indicators[key], dict):
            val = indicators[key].get(sub_key)
            if val is not None:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    pass
        if key in rec_dict and rec_dict[key] is not None:
            try:
                return float(rec_dict[key])
            except (ValueError, TypeError):
                pass
        return None

    # Moisture Deficit
    m_score = float(indicators.get("moisture_deficit", {}).get("sub_score", 0.0))
    m_raw = _get_val("soil_moisture_rootzone_fraction")
    rec_m = _recommend_moisture_deficit(m_score, m_raw)

    # Precip Deficit
    p_info = indicators.get("precipitation_deficit", {})
    p_score = float(p_info.get("sub_score", 0.0))
    p_raw = _get_val("precipitation_rolling_3m_mean_mm_day") or _get_val("precipitation_mm_day")
    p_buf = p_info.get("moisture_buffering_factor")
    rec_p = _recommend_precipitation_deficit(p_score, p_raw, p_buf)

    # Thermal Stress
    t_score = float(indicators.get("thermal_stress", {}).get("sub_score", 0.0))
    t_raw = _get_val("soil_temperature_layer1_c")
    rec_t = _recommend_thermal_stress(t_score, t_raw)

    # SOC Vulnerability
    s_score = float(indicators.get("soc_vulnerability", {}).get("sub_score", 0.0))
    s_raw = _get_val("topsoil_soc_g_kg")
    rec_s = _recommend_soc_vulnerability(s_score, s_raw)

    # pH Deviation
    ph_score = float(indicators.get("ph_deviation", {}).get("sub_score", 0.0))
    ph_raw = _get_val("topsoil_ph_mean")
    rec_ph = _recommend_ph_deviation(ph_score, ph_raw)

    # 3. Compile and Rank Recommendations by Weighted Score (Priority Descending)
    all_recs = [rec_m, rec_p, rec_t, rec_s, rec_ph]
    all_recs.sort(key=lambda r: (r.weighted_score, r.sub_score), reverse=True)

    # Primary stressor is the highest weighted contributor
    primary_stressor = all_recs[0].indicator_name if all_recs else None

    # Critical actions extracted from any recommendations with CRITICAL or HIGH urgency
    critical_actions = [
        f"[{r.urgency}] {r.indicator_name}: {r.primary_intervention}"
        for r in all_recs
        if r.urgency in ("CRITICAL", "HIGH")
    ]
    if not critical_actions:
        critical_actions = [
            "All evaluated stressors are in moderate or favorable ranges. Maintain standard conservation soil management."
        ]

    return RankedRecommendationPlan(
        status=status,
        overall_risk_score=score,
        overall_risk_category=category,
        primary_stressor=primary_stressor,
        recommendations=all_recs,
        critical_actions=critical_actions
    )
