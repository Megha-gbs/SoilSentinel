"""
Soil Sentinel - Crop Recommendation Eligibility & Agro-Climatic Screening Engine.

Evaluates deterministic agro-climatic eligibility rules to decide whether crop
recommendations can be responsibly issued for a given soil/climate record, or must
be WITHHELD due to acute stress or land degradation.

CRITICAL PRINCIPLES:
1. ETHICAL & AGRONOMIC RESPONSIBILITY:
   Under severe hydro-thermal stress or extreme degradation, issuing planting advice
   invites catastrophic crop failure. The engine strictly withholds crop recommendations
   when defined biophysical safety thresholds are breached.
2. STANDARDIZED WITHHOLD REASONS:
   - WITHHELD_CRITICAL_HIGH_RISK: Overall index score >= 75.0 (compounding multi-hazard stress).
   - WITHHELD_ACUTE_DESICCATION: Moisture deficit sub-score >= 80.0 (root-zone soil water exhaustion).
   - WITHHELD_THERMAL_EXTREME: Thermal stress sub-score >= 80.0 (scorching temperatures / thermal abortion).
   - WITHHELD_DEGRADED_SOC: SOC depletion sub-score >= 85.0 (severely exhausted organic carbon < 5 g/kg).
   - WITHHELD_ACIDIC_SODIC_PH: pH deviation sub-score >= 80.0 (severe aluminum toxicity or sodic dispersion).
   - WITHHELD_MISSING_DATA: Missing or invalid environmental inputs preventing reliable evaluation.
3. COARSE FUNCTIONAL SCREENING:
   When eligible, provides functional agronomic suitability categories (drought-hardy pulses,
   coarse cereals, winter oilseeds) tailored to seasonal context (Kharif, Rabi, Zaid).
4. TRANSPARENT NON-ML DISCLAIMER:
   Explicitly notes that suitability screening is a deterministic rule-based agro-climatic filter,
   not an empirical yield model or commercial agronomic prescription.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from src.Model.risk_scoring import (
    calculate_baseline_risk_score,
    classify_risk_category,
    RiskScoringResult,
)

# Standard Withhold Reason Codes
WITHHELD_CRITICAL_HIGH_RISK = "WITHHELD_CRITICAL_HIGH_RISK"
WITHHELD_ACUTE_DESICCATION = "WITHHELD_ACUTE_DESICCATION"
WITHHELD_THERMAL_EXTREME = "WITHHELD_THERMAL_EXTREME"
WITHHELD_DEGRADED_SOC = "WITHHELD_DEGRADED_SOC"
WITHHELD_ACIDIC_SODIC_PH = "WITHHELD_ACIDIC_SODIC_PH"
WITHHELD_MISSING_DATA = "WITHHELD_MISSING_DATA"

AGRONOMIC_DISCLAIMER = (
    "DISCLAIMER: This crop recommendation eligibility screening is a deterministic, "
    "rule-based agro-climatic filter driven by satellite/reanalysis estimates (SoilGrids & "
    "NASA POWER). It does NOT constitute a localized commercial yield forecast or individual "
    "certified agricultural advisory. Prior to planting, always conduct on-site soil testing "
    "and consult local Krishi Vigyan Kendra (KVK) extension agronomists."
)


@dataclass
class CropOption:
    """Individual crop suitability recommendation entry."""
    crop_name: str
    category: str              # e.g. "Pulse", "Coarse Cereal", "Oilseed"
    water_requirement: str     # "Low", "Moderate", "High"
    growth_duration_days: str  # e.g. "60-75 days"
    agronomic_rationale: str
    suitable_soils: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CropEligibilityResult:
    """Standardized output of the crop recommendation eligibility engine."""
    evaluation_date: str
    is_eligible: bool
    risk_score: Optional[float]
    risk_category: str
    withhold_reasons: List[str]
    withhold_explanations: List[str]
    season: str                                # "Kharif", "Rabi", "Zaid", or "Unknown"
    recommended_crops: List[Dict[str, Any]]
    restricted_crops: List[Dict[str, Any]]
    management_advisory: str
    disclaimer: str = AGRONOMIC_DISCLAIMER

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def determine_cropping_season(month: int) -> str:
    """
    Determine Indian cropping season from calendar month integer (1-12).
    - Kharif (Monsoon/Autumn): June to October (Months 6-10)
    - Rabi (Winter/Spring): November to March (Months 11, 12, 1, 2, 3)
    - Zaid (Summer): April to May (Months 4-5)
    """
    if month in (6, 7, 8, 9, 10):
        return "Kharif"
    elif month in (11, 12, 1, 2, 3):
        return "Rabi"
    elif month in (4, 5):
        return "Zaid"
    return "Unknown"


def _extract_month_from_date(date_str: Optional[str]) -> Optional[int]:
    """Extract month integer from 'YYYY-MM' or 'YYYY-MM-DD' string."""
    if not date_str:
        return None
    try:
        parts = str(date_str).split("-")
        if len(parts) >= 2:
            return int(parts[1])
    except (ValueError, IndexError):
        pass
    return None


def evaluate_crop_eligibility(
    data: Union[Dict[str, Any], RiskScoringResult, pd.Series],
    date: Optional[str] = None
) -> CropEligibilityResult:
    """
    Evaluate crop recommendation eligibility and generate functional crop suitability.

    Parameters:
        data: Either a dictionary of raw features, a scored RiskScoringResult, or a pandas Series.
        date: Optional evaluation date string 'YYYY-MM'. If not provided, attempted to read from data.

    Returns:
        Structured CropEligibilityResult with eligibility status, withhold reasons, and crop screening.
    """
    # 1. Resolve date
    eval_date = "UNKNOWN"
    if date is not None:
        eval_date = str(date)
    elif isinstance(data, dict) and "date" in data:
        eval_date = str(data["date"])
    elif isinstance(data, pd.Series) and "date" in data:
        eval_date = str(data["date"])

    # 2. Extract Sub-scores and Status
    score: Optional[float] = None
    category: str = "UNKNOWN"
    m_score: float = 0.0
    p_score: float = 0.0
    t_score: float = 0.0
    s_score: float = 0.0
    ph_score: float = 0.0

    if isinstance(data, RiskScoringResult):
        if data.score is None or data.status in ("INVALID_INPUT", "INSUFFICIENT_HISTORY"):
            return CropEligibilityResult(
                evaluation_date=eval_date,
                is_eligible=False,
                risk_score=None,
                risk_category=data.risk_category or "UNKNOWN",
                withhold_reasons=[WITHHELD_MISSING_DATA],
                withhold_explanations=[f"Scoring status is '{data.status}': incomplete environmental inputs."],
                season=determine_cropping_season(_extract_month_from_date(eval_date)) if _extract_month_from_date(eval_date) else "Unknown",
                recommended_crops=[],
                restricted_crops=[],
                management_advisory="Provide complete soil and climate data before requesting crop advisory."
            )
        score = data.score
        category = data.risk_category
        ind = data.indicators or {}
        m_score = float(ind.get("moisture_deficit", {}).get("sub_score", 0.0) or 0.0)
        p_score = float(ind.get("precipitation_deficit", {}).get("sub_score", 0.0) or 0.0)
        t_score = float(ind.get("thermal_stress", {}).get("sub_score", 0.0) or 0.0)
        s_score = float((ind.get("soc_vulnerability") or ind.get("soc_depletion") or {}).get("sub_score", 0.0) or 0.0)
        ph_score = float(ind.get("ph_deviation", {}).get("sub_score", 0.0) or 0.0)

    elif isinstance(data, (dict, pd.Series)):
        d_dict = data.to_dict() if isinstance(data, pd.Series) else dict(data)
        
        # Check if pre-computed sub-scores already exist in dictionary/series
        if "moisture_deficit_sub_score" in d_dict and ("score" in d_dict or "baseline_risk_score" in d_dict):
            raw_s = d_dict.get("score") if d_dict.get("score") is not None else d_dict.get("baseline_risk_score")
            if raw_s is None or (isinstance(raw_s, float) and np.isnan(raw_s)):
                score = None
            else:
                score = float(raw_s)
            category = str(d_dict.get("risk_category") or classify_risk_category(score))
            m_score = float(d_dict.get("moisture_deficit_sub_score") or 0.0)
            p_score = float(d_dict.get("precipitation_deficit_sub_score") or 0.0)
            t_score = float(d_dict.get("thermal_stress_sub_score") or 0.0)
            s_score = float(d_dict.get("soc_vulnerability_sub_score") or d_dict.get("soc_depletion_sub_score") or 0.0)
            ph_score = float(d_dict.get("ph_deviation_sub_score") or 0.0)
        else:
            # Need to compute risk score
            scoring_res = calculate_baseline_risk_score(d_dict, allow_partial=True)
            if scoring_res.score is None or scoring_res.status in ("INVALID_INPUT", "INSUFFICIENT_HISTORY"):
                return CropEligibilityResult(
                    evaluation_date=eval_date,
                    is_eligible=False,
                    risk_score=None,
                    risk_category=scoring_res.risk_category or "UNKNOWN",
                    withhold_reasons=[WITHHELD_MISSING_DATA],
                    withhold_explanations=[f"Missing or invalid biophysical inputs prevented scoring ({scoring_res.status})."],
                    season=determine_cropping_season(_extract_month_from_date(eval_date)) if _extract_month_from_date(eval_date) else "Unknown",
                    recommended_crops=[],
                    restricted_crops=[],
                    management_advisory="Provide complete soil and climate data before requesting crop advisory."
                )
            score = scoring_res.score
            category = scoring_res.risk_category
            ind = scoring_res.indicators or {}
            m_score = float(ind.get("moisture_deficit", {}).get("sub_score", 0.0) or 0.0)
            p_score = float(ind.get("precipitation_deficit", {}).get("sub_score", 0.0) or 0.0)
            t_score = float(ind.get("thermal_stress", {}).get("sub_score", 0.0) or 0.0)
            s_score = float((ind.get("soc_vulnerability") or ind.get("soc_depletion") or {}).get("sub_score", 0.0) or 0.0)
            ph_score = float(ind.get("ph_deviation", {}).get("sub_score", 0.0) or 0.0)

    else:
        raise TypeError(f"Unsupported data type for crop eligibility evaluation: {type(data)}")

    # 3. Determine Cropping Season
    month = _extract_month_from_date(eval_date)
    season = determine_cropping_season(month) if month else "Unknown"

    # 4. Check for unobserved score
    if score is None:
        return CropEligibilityResult(
            evaluation_date=eval_date,
            is_eligible=False,
            risk_score=None,
            risk_category="UNKNOWN",
            withhold_reasons=[WITHHELD_MISSING_DATA],
            withhold_explanations=["Risk score is null or unobserved; cannot safely issue crop advisory."],
            season=season,
            recommended_crops=[],
            restricted_crops=[],
            management_advisory="Provide complete soil and climate data before requesting crop advisory."
        )

    # 5. Evaluate Withhold Rules
    withhold_reasons: List[str] = []
    withhold_explanations: List[str] = []

    # Rule A: Critical compounding risk (Score >= 75.0)
    if score >= 75.0:
        withhold_reasons.append(WITHHELD_CRITICAL_HIGH_RISK)
        withhold_explanations.append(
            f"Overall Hydro-Thermal Risk Score is critical ({score:.2f} / 100). "
            f"Severe multi-hazard stress indicates land degradation emergency; "
            f"immediate soil conservation and moisture conservation must take priority over cropping."
        )

    # Rule B: Acute moisture deficit (Sub-score >= 80.0)
    if m_score >= 80.0:
        withhold_reasons.append(WITHHELD_ACUTE_DESICCATION)
        withhold_explanations.append(
            f"Acute Root-Zone Desiccation: Moisture deficit sub-score is {m_score:.1f} / 100. "
            f"Soil profile moisture is near or below permanent wilting point; standard sowing is unviable."
        )

    # Rule C: Thermal extreme (Sub-score >= 80.0)
    if t_score >= 80.0:
        withhold_reasons.append(WITHHELD_THERMAL_EXTREME)
        withhold_explanations.append(
            f"Extreme Thermal Heat Stress: Thermal sub-score is {t_score:.1f} / 100. "
            f"Scorching temperatures cause severe seedling mortality and thermal pollen abortion."
        )

    # Rule D: Severely degraded organic carbon (Sub-score >= 85.0)
    if s_score >= 85.0:
        withhold_reasons.append(WITHHELD_DEGRADED_SOC)
        withhold_explanations.append(
            f"Severely Depleted Soil Organic Carbon: SOC depletion sub-score is {s_score:.1f} / 100. "
            f"Soil biological life and nutrient buffering are too degraded to support commercial crops."
        )

    # Rule E: Extreme pH toxicity / salinity (Sub-score >= 80.0)
    if ph_score >= 80.0:
        withhold_reasons.append(WITHHELD_ACIDIC_SODIC_PH)
        withhold_explanations.append(
            f"Extreme Soil Reaction Deviation: pH deviation sub-score is {ph_score:.1f} / 100. "
            f"Severe acidity (Al toxicity) or sodicity prevents nutrient uptake and roots establishment."
        )

    is_eligible = (len(withhold_reasons) == 0)

    # 6. Crop Screening Logic
    recommended_crops: List[Dict[str, Any]] = []
    restricted_crops: List[Dict[str, Any]] = []

    if not is_eligible:
        # Mandatory restriction: all intensive crops restricted
        restricted_crops.append({
            "crop_name": "All Commercial / Grain Crops",
            "reason": f"Withheld due to safety violations: {', '.join(withhold_reasons)}."
        })
        management_advisory = (
            "CROPPING ADVISORY WITHHELD. Priority action: Implement emergency soil stabilization, "
            "surface mulching, deep organic manuring (FYM/compost), and rainwater harvesting before sowing."
        )
    else:
        # Condition is ELIGIBLE: screen suitable functional crops based on season and moisture regime
        is_dry = (m_score >= 50.0 or p_score >= 50.0)
        
        if season == "Kharif":
            if is_dry:
                recommended_crops.extend([
                    CropOption(
                        crop_name="Pearl Millet (Bajra)",
                        category="Coarse Cereal",
                        water_requirement="Low",
                        growth_duration_days="75-85 days",
                        agronomic_rationale="Highly drought-tolerant C4 cereal with deep root penetration and excellent water-use efficiency.",
                        suitable_soils="Sandy loam to loamy soils."
                    ).to_dict(),
                    CropOption(
                        crop_name="Moong Bean (Green Gram)",
                        category="Short-duration Pulse",
                        water_requirement="Low",
                        growth_duration_days="60-65 days",
                        agronomic_rationale="Fast-maturing legume that fixes atmospheric nitrogen and acts as living cover against soil erosion.",
                        suitable_soils="Well-drained loam and sandy loam."
                    ).to_dict(),
                    CropOption(
                        crop_name="Cluster Bean (Guar)",
                        category="Legume / Arid Crop",
                        water_requirement="Very Low",
                        growth_duration_days="90-100 days",
                        agronomic_rationale="Extreme drought hardiness; minimal moisture demand with restorative nitrogen enrichment.",
                        suitable_soils="Sandy to sandy-loam soils."
                    ).to_dict(),
                ])
                restricted_crops.append({
                    "crop_name": "Paddy (Rice)",
                    "reason": "Excessive ponding water requirement (>1200 mm); unviable under elevated moisture deficit."
                })
            else:
                recommended_crops.extend([
                    CropOption(
                        crop_name="Maize (Corn)",
                        category="Cereal",
                        water_requirement="Moderate",
                        growth_duration_days="90-110 days",
                        agronomic_rationale="High biomass yield with moderate moisture buffer; responsive to soil organic matter.",
                        suitable_soils="Deep, fertile, well-drained loams."
                    ).to_dict(),
                    CropOption(
                        crop_name="Soybean / Pigeonpea (Arhar)",
                        category="Legume",
                        water_requirement="Moderate",
                        growth_duration_days="100-140 days",
                        agronomic_rationale="Deep-rooting taproot opens compact soil layers; atmospheric N-fixation improves fertility.",
                        suitable_soils="Loam to clay loam soils."
                    ).to_dict(),
                ])
        elif season == "Rabi":
            if is_dry:
                recommended_crops.extend([
                    CropOption(
                        crop_name="Chickpea (Gram)",
                        category="Cool-season Pulse",
                        water_requirement="Low",
                        growth_duration_days="95-110 days",
                        agronomic_rationale="Deep rooting system utilizes residual sub-surface moisture with minimal supplementary irrigation.",
                        suitable_soils="Loam to clay-loam with good moisture retention."
                    ).to_dict(),
                    CropOption(
                        crop_name="Mustard / Toria (Brassica)",
                        category="Oilseed",
                        water_requirement="Low to Moderate",
                        growth_duration_days="100-120 days",
                        agronomic_rationale="Thrives under cool conditions with low water footprint (2-3 light irrigations).",
                        suitable_soils="Sandy loam to light clay."
                    ).to_dict(),
                    CropOption(
                        crop_name="Barley (Jau)",
                        category="Coarse Cereal",
                        water_requirement="Low",
                        growth_duration_days="110-125 days",
                        agronomic_rationale="Tolerant to mild moisture stress and slightly alkaline or saline soil conditions.",
                        suitable_soils="Sandy loam to loam."
                    ).to_dict(),
                ])
                restricted_crops.append({
                    "crop_name": "Continuous Flood Wheat",
                    "reason": "Restricted if irrigation water is constrained; shift to limited-irrigation chickpea/mustard."
                })
            else:
                recommended_crops.extend([
                    CropOption(
                        crop_name="Wheat (Semi-dwarf)",
                        category="Cereal",
                        water_requirement="Moderate",
                        growth_duration_days="120-135 days",
                        agronomic_rationale="Standard winter staple; highly productive under adequate soil moisture reserve.",
                        suitable_soils="Fertile, moisture-retentive loams."
                    ).to_dict(),
                    CropOption(
                        crop_name="Chickpea / Lentil (Masoor)",
                        category="Pulse",
                        water_requirement="Low to Moderate",
                        growth_duration_days="105-120 days",
                        agronomic_rationale="Improves soil health, provides high protein yield, and maintains ground cover.",
                        suitable_soils="Well-drained loams."
                    ).to_dict(),
                ])
        elif season == "Zaid":
            recommended_crops.extend([
                CropOption(
                    crop_name="Green Manure (Sesbania / Dhaincha)",
                    category="Soil Restorative Green Manure",
                    water_requirement="Low to Moderate",
                    growth_duration_days="45-55 days",
                    agronomic_rationale="Ploughed into soil before flowering to add 15-20 t/ha fresh green biomass, buffering SOC.",
                    suitable_soils="All soils including light and alkaline."
                ).to_dict(),
                CropOption(
                    crop_name="Summer Moong (Green Gram)",
                    category="Short-duration Pulse",
                    water_requirement="Low",
                    growth_duration_days="60 days",
                    agronomic_rationale="Captures summer heat window with minimal irrigation while fixing nitrogen.",
                    suitable_soils="Well-drained fertile loam."
                ).to_dict(),
            ])
            restricted_crops.append({
                "crop_name": "Summer Paddy / Sugarcane",
                "reason": "Extreme summer evaporation leads to massive water deficit and secondary salinization."
            })
        else:
            # General / Unknown season fallback
            recommended_crops.append(
                CropOption(
                    crop_name="Drought-hardy Pulses / Cover Crop",
                    category="Legume",
                    water_requirement="Low",
                    growth_duration_days="60-90 days",
                    agronomic_rationale="Protects soil surface and enriches nitrogen regardless of specific calendar timing.",
                    suitable_soils="Loam to sandy loam."
                ).to_dict()
            )

        management_advisory = (
            f"Land condition is ELIGIBLE for {season} season planting. "
            f"Risk category: {category} ({score:.2f} pts). "
            f"Recommended strategy: Prioritize low-water restorative crops and maintain crop residue mulching."
        )

    return CropEligibilityResult(
        evaluation_date=eval_date,
        is_eligible=is_eligible,
        risk_score=score,
        risk_category=category,
        withhold_reasons=withhold_reasons,
        withhold_explanations=withhold_explanations,
        season=season,
        recommended_crops=recommended_crops,
        restricted_crops=restricted_crops,
        management_advisory=management_advisory,
        disclaimer=AGRONOMIC_DISCLAIMER
    )
