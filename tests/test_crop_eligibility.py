"""
Unit Tests for SoilSentinel Crop Recommendation Eligibility Engine.

Verifies:
1. Strict withholding under critical high risk (score >= 75.0).
2. Strict withholding under acute root-zone desiccation (moisture deficit >= 80.0).
3. Strict withholding under extreme thermal heat stress (thermal stress >= 80.0).
4. Strict withholding under severely depleted SOC (soc depletion >= 85.0).
5. Strict withholding under extreme pH deviation (pH deviation >= 80.0).
6. Withholding under missing/invalid input data.
7. Season determination (Kharif, Rabi, Zaid) from calendar months.
8. Functional crop screening for eligible states (Kharif vs Rabi vs Zaid).
9. Water-intensive crop restrictions under dry regimes.
10. Evaluation on actual rows from feature_table.csv.
11. Serialization to dictionary conforming to dashboard contract.
"""

import sys
import unittest
from pathlib import Path
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Model.crop_eligibility import (
    evaluate_crop_eligibility,
    determine_cropping_season,
    CropEligibilityResult,
    WITHHELD_CRITICAL_HIGH_RISK,
    WITHHELD_ACUTE_DESICCATION,
    WITHHELD_THERMAL_EXTREME,
    WITHHELD_DEGRADED_SOC,
    WITHHELD_ACIDIC_SODIC_PH,
    WITHHELD_MISSING_DATA,
)
from src.Model.risk_scoring import RiskScoringResult


def _make_scoring_result(
    score: float,
    risk_category: str = "Medium",
    m_score: float = 30.0,
    p_score: float = 30.0,
    t_score: float = 30.0,
    s_score: float = 30.0,
    ph_score: float = 30.0,
    status: str = "CALCULATED"
) -> RiskScoringResult:
    return RiskScoringResult(
        score=score,
        risk_category=risk_category,
        status=status,
        dynamic_environmental_stress=round((m_score + p_score + t_score) / 3.0, 2),
        baseline_soil_vulnerability=round((s_score + ph_score) / 2.0, 2),
        indicators={
            "moisture_deficit": {"sub_score": m_score},
            "precipitation_deficit": {"sub_score": p_score},
            "thermal_stress": {"sub_score": t_score},
            "soc_vulnerability": {"sub_score": s_score},
            "ph_deviation": {"sub_score": ph_score},
        },
        explanation="Test risk scoring result fixture."
    )


class TestCropRecommendationEligibility(unittest.TestCase):
    """Test suite for deterministic crop eligibility screening."""

    def test_determine_cropping_season(self):
        """Verify season mapping according to Indian agricultural calendar."""
        self.assertEqual(determine_cropping_season(7), "Kharif")  # July
        self.assertEqual(determine_cropping_season(9), "Kharif")  # Sept
        self.assertEqual(determine_cropping_season(11), "Rabi")   # Nov
        self.assertEqual(determine_cropping_season(1), "Rabi")    # Jan
        self.assertEqual(determine_cropping_season(4), "Zaid")    # April
        self.assertEqual(determine_cropping_season(5), "Zaid")    # May

    def test_withhold_on_critical_high_risk(self):
        """Score >= 75.0 must trigger WITHHELD_CRITICAL_HIGH_RISK."""
        scoring_res = _make_scoring_result(
            score=78.5,
            risk_category="High",
            m_score=70.0,
            p_score=70.0,
            t_score=60.0
        )
        res = evaluate_crop_eligibility(scoring_res, date="2024-06")
        self.assertFalse(res.is_eligible)
        self.assertIn(WITHHELD_CRITICAL_HIGH_RISK, res.withhold_reasons)
        self.assertEqual(len(res.recommended_crops), 0)
        self.assertGreater(len(res.restricted_crops), 0)
        self.assertIn("WITHHELD", res.management_advisory)

    def test_withhold_on_acute_desiccation(self):
        """Moisture deficit >= 80.0 must trigger WITHHELD_ACUTE_DESICCATION."""
        scoring_res = _make_scoring_result(
            score=62.0,
            risk_category="Medium",
            m_score=85.0
        )
        res = evaluate_crop_eligibility(scoring_res, date="2024-05")
        self.assertFalse(res.is_eligible)
        self.assertIn(WITHHELD_ACUTE_DESICCATION, res.withhold_reasons)
        self.assertEqual(len(res.recommended_crops), 0)

    def test_withhold_on_thermal_extreme(self):
        """Thermal stress sub-score >= 80.0 must trigger WITHHELD_THERMAL_EXTREME."""
        scoring_res = _make_scoring_result(
            score=60.0,
            risk_category="Medium",
            t_score=88.0
        )
        res = evaluate_crop_eligibility(scoring_res, date="2024-06")
        self.assertFalse(res.is_eligible)
        self.assertIn(WITHHELD_THERMAL_EXTREME, res.withhold_reasons)
        self.assertEqual(len(res.recommended_crops), 0)

    def test_withhold_on_degraded_soc(self):
        """SOC depletion sub-score >= 85.0 must trigger WITHHELD_DEGRADED_SOC."""
        scoring_res = _make_scoring_result(
            score=55.0,
            risk_category="Medium",
            s_score=90.0
        )
        res = evaluate_crop_eligibility(scoring_res, date="2024-07")
        self.assertFalse(res.is_eligible)
        self.assertIn(WITHHELD_DEGRADED_SOC, res.withhold_reasons)

    def test_withhold_on_extreme_ph_deviation(self):
        """pH deviation sub-score >= 80.0 must trigger WITHHELD_ACIDIC_SODIC_PH."""
        scoring_res = _make_scoring_result(
            score=58.0,
            risk_category="Medium",
            ph_score=85.0
        )
        res = evaluate_crop_eligibility(scoring_res, date="2024-11")
        self.assertFalse(res.is_eligible)
        self.assertIn(WITHHELD_ACIDIC_SODIC_PH, res.withhold_reasons)

    def test_withhold_on_missing_data(self):
        """Incomplete / invalid raw dictionary must withhold with WITHHELD_MISSING_DATA."""
        res = evaluate_crop_eligibility({"incomplete_col": 123}, date="2024-01")
        self.assertFalse(res.is_eligible)
        self.assertIn(WITHHELD_MISSING_DATA, res.withhold_reasons)

    def test_eligible_rabi_season_crops(self):
        """Eligible winter conditions in Rabi season must recommend cool-season crops."""
        scoring_res = _make_scoring_result(
            score=32.0,
            risk_category="Low",
            m_score=35.0,
            p_score=30.0,
            t_score=20.0,
            s_score=40.0,
            ph_score=25.0
        )
        res = evaluate_crop_eligibility(scoring_res, date="2024-12")
        self.assertTrue(res.is_eligible)
        self.assertEqual(res.season, "Rabi")
        self.assertEqual(len(res.withhold_reasons), 0)
        self.assertGreater(len(res.recommended_crops), 0)

        # Check crops included
        crop_names = [c["crop_name"] for c in res.recommended_crops]
        self.assertTrue(any("Wheat" in name for name in crop_names))

    def test_eligible_kharif_dry_season_restricts_paddy(self):
        """Kharif season with elevated moisture deficit must recommend pulses/millets and restrict paddy."""
        scoring_res = _make_scoring_result(
            score=48.0,
            risk_category="Medium",
            m_score=60.0,  # Dry but < 80 threshold
            p_score=55.0,
            t_score=40.0
        )
        res = evaluate_crop_eligibility(scoring_res, date="2024-07")
        self.assertTrue(res.is_eligible)
        self.assertEqual(res.season, "Kharif")

        crop_names = [c["crop_name"] for c in res.recommended_crops]
        self.assertTrue(any("Bajra" in name or "Millet" in name for name in crop_names))

        restricted_names = [c["crop_name"] for c in res.restricted_crops]
        self.assertTrue(any("Rice" in name or "Paddy" in name for name in restricted_names))

    def test_evaluation_on_real_feature_table_row(self):
        """Evaluate crop eligibility on real rows from feature_table.csv."""
        csv_path = PROJECT_ROOT / "data" / "feature_table.csv"
        df = pd.read_csv(csv_path)
        
        # Test row for July (Monsoon)
        row_monsoon = df[df["date"] == "2024-07"].iloc[0]
        res = evaluate_crop_eligibility(row_monsoon)
        self.assertIsInstance(res, CropEligibilityResult)
        self.assertIn(res.season, ["Kharif", "Rabi", "Zaid"])
        self.assertIn("DISCLAIMER", res.disclaimer)

    def test_serialization_to_dict(self):
        """to_dict() must return serializable dictionary with all contract fields."""
        scoring_res = _make_scoring_result(
            score=30.0,
            risk_category="Low",
            m_score=25.0,
            p_score=20.0,
            t_score=20.0,
            s_score=35.0,
            ph_score=20.0
        )
        res = evaluate_crop_eligibility(scoring_res, date="2024-02")
        d = res.to_dict()
        expected_keys = [
            "evaluation_date", "is_eligible", "risk_score", "risk_category",
            "withhold_reasons", "withhold_explanations", "season",
            "recommended_crops", "restricted_crops", "management_advisory", "disclaimer"
        ]
        for k in expected_keys:
            self.assertIn(k, d)


if __name__ == "__main__":
    unittest.main()
