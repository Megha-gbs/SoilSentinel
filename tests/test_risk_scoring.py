"""
Unit Tests for Soil Sentinel Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index.

Verifies:
1. Low rainfall with adequate root-zone moisture (moisture-buffering relief applied).
2. Low rainfall with low root-zone moisture (full recharge penalty retained).
3. Higher rainfall with otherwise identical conditions (monotonic rainfall benefit).
4. Score boundaries and risk categories (0-100 bounds, Low/Medium/High transitions).
5. Missing values and provisional-history status (strict abort vs provisional fallback).
6. Deterministic results, repeat execution stability, and valid score ranges.
7. Separation of dynamic climate stressors from static soil baseline buffering.
8. Batch scoring across the 60-month real feature table.
"""

import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Model.risk_scoring import (
    calculate_baseline_risk_score,
    score_feature_dataframe,
    classify_risk_category,
    calculate_buffering_factor,
    calculate_moisture_deficit_score,
    calculate_precipitation_deficit_score,
    calculate_thermal_stress_score,
    calculate_soc_vulnerability_score,
    calculate_ph_deviation_score,
    BUFFERING_MOISTURE_LOW_THRESHOLD,
    BUFFERING_MOISTURE_ADEQUATE_THRESHOLD,
    BUFFERING_MIN_PENALTY_FACTOR,
    THRESHOLD_LOW_UPPER,
    THRESHOLD_MEDIUM_UPPER,
    WEIGHT_MOISTURE_DEFICIT,
    WEIGHT_PRECIPITATION_DEFICIT,
    WEIGHT_THERMAL_STRESS,
    WEIGHT_SOC_DEPLETION,
    WEIGHT_PH_DEVIATION,
)


class TestMoistureBufferingAdjustment(unittest.TestCase):
    """
    Test moisture-buffering adjustment to meteorological recharge deficit.
    Low rainfall should not automatically imply acute soil-water stress when
    root-zone moisture is adequate.
    """

    def setUp(self):
        self.base_record = {
            "date": "2023-01",
            "soil_temperature_layer1_c": 18.0,
            "topsoil_soc_g_kg": 12.95,
            "topsoil_ph_mean": 6.55,
            "precipitation_rolling_3m_mean_mm_day": 0.2,  # Severe meteorological deficit (<= 0.5)
            "precipitation_mm_day": 0.2,
        }

    def test_low_rainfall_with_adequate_rootzone_moisture(self):
        """When root-zone moisture is adequate (e.g. 0.70), precip penalty is mitigated."""
        record = self.base_record.copy()
        record["soil_moisture_rootzone_fraction"] = 0.70  # Adequate moisture >= 0.65
        res = calculate_baseline_risk_score(record)

        precip_info = res.indicators["precipitation_deficit"]
        self.assertEqual(precip_info["raw_unbuffered_score"], 100.0)
        self.assertEqual(precip_info["moisture_buffering_factor"], BUFFERING_MIN_PENALTY_FACTOR)
        # 100.0 * 0.50 = 50.0
        self.assertEqual(precip_info["sub_score"], 50.0)
        self.assertIn("moisture-buffering relief applied", precip_info["notes"])

    def test_low_rainfall_with_low_rootzone_moisture(self):
        """When root-zone moisture is depleted (e.g. 0.30), full precip penalty is retained."""
        record = self.base_record.copy()
        record["soil_moisture_rootzone_fraction"] = 0.30  # Low moisture <= 0.35
        res = calculate_baseline_risk_score(record)

        precip_info = res.indicators["precipitation_deficit"]
        self.assertEqual(precip_info["raw_unbuffered_score"], 100.0)
        self.assertEqual(precip_info["moisture_buffering_factor"], 1.0)
        # 100.0 * 1.00 = 100.0
        self.assertEqual(precip_info["sub_score"], 100.0)
        self.assertIn("retaining 100% of meteorological recharge deficit penalty", precip_info["notes"])

    def test_adequate_moisture_yields_lower_score_than_low_moisture(self):
        """Compare identical low-rainfall conditions with adequate vs low root-zone moisture."""
        rec_wet = self.base_record.copy()
        rec_wet["soil_moisture_rootzone_fraction"] = 0.70

        rec_dry = self.base_record.copy()
        rec_dry["soil_moisture_rootzone_fraction"] = 0.30

        res_wet = calculate_baseline_risk_score(rec_wet)
        res_dry = calculate_baseline_risk_score(rec_dry)

        # Both the precipitation sub-score and the overall composite index must be lower when wet
        self.assertLess(
            res_wet.indicators["precipitation_deficit"]["sub_score"],
            res_dry.indicators["precipitation_deficit"]["sub_score"]
        )
        self.assertLess(res_wet.score, res_dry.score)

    def test_higher_rainfall_with_otherwise_identical_conditions(self):
        """Compare low rainfall vs abundant rainfall under identical root-zone moisture."""
        rec_dry_sky = self.base_record.copy()
        rec_dry_sky["soil_moisture_rootzone_fraction"] = 0.50
        rec_dry_sky["precipitation_rolling_3m_mean_mm_day"] = 0.3

        rec_wet_sky = self.base_record.copy()
        rec_wet_sky["soil_moisture_rootzone_fraction"] = 0.50
        rec_wet_sky["precipitation_rolling_3m_mean_mm_day"] = 7.0

        res_dry_sky = calculate_baseline_risk_score(rec_dry_sky)
        res_wet_sky = calculate_baseline_risk_score(rec_wet_sky)

        # Higher rainfall must strictly reduce the precipitation subscore and composite index
        self.assertEqual(res_wet_sky.indicators["precipitation_deficit"]["sub_score"], 0.0)
        self.assertGreater(res_dry_sky.indicators["precipitation_deficit"]["sub_score"], 0.0)
        self.assertLess(res_wet_sky.score, res_dry_sky.score)


    def test_buffering_factor_bounds_and_continuity(self):
        """Verify buffering factor is bounded in [0.50, 1.00] and monotonic."""
        f_low, _ = calculate_buffering_factor(0.20)
        f_thresh_low, _ = calculate_buffering_factor(0.35)
        f_mid, _ = calculate_buffering_factor(0.50)
        f_thresh_high, _ = calculate_buffering_factor(0.65)
        f_high, _ = calculate_buffering_factor(0.85)

        self.assertEqual(f_low, 1.0)
        self.assertEqual(f_thresh_low, 1.0)
        self.assertEqual(f_mid, 0.75)
        self.assertEqual(f_thresh_high, 0.50)
        self.assertEqual(f_high, 0.50)
        self.assertTrue(1.0 >= f_mid >= 0.50)


class TestRiskScoringInputValidation(unittest.TestCase):
    """Test defensive validation against invalid, missing, or corrupted inputs."""

    def setUp(self):
        self.valid_record = {
            "date": "2023-07",
            "soil_moisture_rootzone_fraction": 0.55,
            "soil_temperature_layer1_c": 28.5,
            "topsoil_soc_g_kg": 12.95,
            "topsoil_ph_mean": 6.55,
            "precipitation_rolling_3m_mean_mm_day": 4.5,
            "precipitation_mm_day": 5.2,
        }

    def test_valid_record_passes(self):
        result = calculate_baseline_risk_score(self.valid_record)
        self.assertEqual(result.status, "COMPLETE")
        self.assertIsNotNone(result.score)
        self.assertTrue(0.0 <= result.score <= 100.0)
        self.assertIn(result.risk_category, ["Low", "Medium", "High"])

    def test_missing_essential_field_aborts(self):
        record = self.valid_record.copy()
        del record["soil_moisture_rootzone_fraction"]
        result = calculate_baseline_risk_score(record)
        self.assertEqual(result.status, "INVALID_INPUT")
        self.assertIsNone(result.score)
        self.assertEqual(result.risk_category, "UNKNOWN")
        self.assertIn("Missing essential field", result.explanation)

    def test_nan_in_essential_field_aborts(self):
        record = self.valid_record.copy()
        record["topsoil_soc_g_kg"] = np.nan
        result = calculate_baseline_risk_score(record)
        self.assertEqual(result.status, "INVALID_INPUT")
        self.assertIsNone(result.score)
        self.assertEqual(result.risk_category, "UNKNOWN")

    def test_out_of_bounds_moisture_aborts(self):
        record = self.valid_record.copy()
        record["soil_moisture_rootzone_fraction"] = 1.35
        result = calculate_baseline_risk_score(record)
        self.assertEqual(result.status, "INVALID_INPUT")
        self.assertIsNone(result.score)

    def test_negative_precipitation_aborts(self):
        record = self.valid_record.copy()
        record["precipitation_mm_day"] = -5.0
        result = calculate_baseline_risk_score(record)
        self.assertEqual(result.status, "INVALID_INPUT")
        self.assertIsNone(result.score)

    def test_negative_rolling_precipitation_aborts(self):
        record = self.valid_record.copy()
        record["precipitation_rolling_3m_mean_mm_day"] = -3.2
        result = calculate_baseline_risk_score(record)
        self.assertEqual(result.status, "INVALID_INPUT")
        self.assertIsNone(result.score)
        self.assertIn("Negative rolling precipitation", result.explanation)

    def test_non_numeric_rolling_precipitation_aborts(self):
        record = self.valid_record.copy()
        record["precipitation_rolling_3m_mean_mm_day"] = "invalid_number"
        result = calculate_baseline_risk_score(record)
        self.assertEqual(result.status, "INVALID_INPUT")
        self.assertIsNone(result.score)
        self.assertIn("Non-numeric rolling precipitation", result.explanation)

    def test_infinite_rolling_precipitation_aborts(self):
        for inf_val in [float("inf"), float("-inf"), np.inf, -np.inf]:
            with self.subTest(val=inf_val):
                record = self.valid_record.copy()
                record["precipitation_rolling_3m_mean_mm_day"] = inf_val
                result = calculate_baseline_risk_score(record)
                self.assertEqual(result.status, "INVALID_INPUT")
                self.assertIsNone(result.score)
                self.assertIn("rolling precipitation detected", result.explanation)

    def test_infinite_precipitation_aborts(self):
        for inf_val in [float("inf"), float("-inf"), np.inf, -np.inf]:
            with self.subTest(val=inf_val):
                record = self.valid_record.copy()
                record["precipitation_mm_day"] = inf_val
                result = calculate_baseline_risk_score(record)
                self.assertEqual(result.status, "INVALID_INPUT")
                self.assertIsNone(result.score)
                self.assertIn("precipitation detected", result.explanation)

    def test_out_of_bounds_precipitation_aborts(self):
        record = self.valid_record.copy()
        record["precipitation_mm_day"] = 999.0
        result = calculate_baseline_risk_score(record)
        self.assertEqual(result.status, "INVALID_INPUT")
        self.assertIsNone(result.score)
        self.assertIn("out of physical bounds", result.explanation)

    def test_out_of_bounds_rolling_precipitation_aborts(self):
        record = self.valid_record.copy()
        record["precipitation_rolling_3m_mean_mm_day"] = 999.0
        result = calculate_baseline_risk_score(record)
        self.assertEqual(result.status, "INVALID_INPUT")
        self.assertIsNone(result.score)
        self.assertIn("out of physical bounds", result.explanation)

    def test_direct_calculate_precipitation_deficit_score_guard(self):
        """Direct call to calculate_precipitation_deficit_score must reject inf and negative rates."""
        for bad_rate in [float("inf"), float("-inf"), np.inf, -np.inf, -5.0, 999.0]:
            with self.subTest(rate=bad_rate):
                adj_score, raw_score, buf_factor, note, is_fb = calculate_precipitation_deficit_score(
                    precip_3m_mean=bad_rate,
                    current_precip=bad_rate,
                    allow_partial=False
                )
                self.assertIsNone(adj_score)
                self.assertIsNone(raw_score)
                self.assertIn("Invalid precipitation rate", note)


class TestScoreBoundariesAndExtremes(unittest.TestCase):
    """Test theoretical boundary behavior at extreme limits."""

    def test_theoretical_ideal_conditions_yield_minimum_score(self):
        ideal_record = {
            "date": "2023-01",
            "soil_moisture_rootzone_fraction": 0.85,
            "soil_temperature_layer1_c": 18.0,
            "topsoil_soc_g_kg": 30.0,
            "topsoil_ph_mean": 7.0,
            "precipitation_rolling_3m_mean_mm_day": 8.0,
            "precipitation_mm_day": 8.0,
        }
        res = calculate_baseline_risk_score(ideal_record)
        self.assertEqual(res.status, "COMPLETE")
        self.assertEqual(res.score, 0.0)
        self.assertEqual(res.risk_category, "Low")
        self.assertEqual(res.dynamic_environmental_stress, 0.0)
        self.assertEqual(res.baseline_soil_vulnerability, 0.0)

    def test_theoretical_worst_conditions_yield_maximum_score(self):
        worst_record = {
            "date": "2023-06",
            "soil_moisture_rootzone_fraction": 0.15,
            "soil_temperature_layer1_c": 42.0,
            "topsoil_soc_g_kg": 3.0,
            "topsoil_ph_mean": 4.0,
            "precipitation_rolling_3m_mean_mm_day": 0.1,
            "precipitation_mm_day": 0.0,
        }
        res = calculate_baseline_risk_score(worst_record)
        self.assertEqual(res.status, "COMPLETE")
        self.assertEqual(res.score, 100.0)
        self.assertEqual(res.risk_category, "High")
        self.assertEqual(res.dynamic_environmental_stress, 100.0)
        self.assertEqual(res.baseline_soil_vulnerability, 100.0)


class TestMissingLagAndRollingFeatures(unittest.TestCase):
    """Test policy for missing temporal context at sequence boundaries."""

    def setUp(self):
        self.boundary_record = {
            "date": "2020-01",
            "soil_moisture_rootzone_fraction": 0.52,
            "soil_temperature_layer1_c": 10.37,
            "topsoil_soc_g_kg": 12.95,
            "topsoil_ph_mean": 6.55,
            "precipitation_rolling_3m_mean_mm_day": np.nan,
            "precipitation_mm_day": 2.73,
        }

    def test_strict_mode_rejects_missing_rolling_history(self):
        res = calculate_baseline_risk_score(self.boundary_record, allow_partial=False)
        self.assertEqual(res.status, "INSUFFICIENT_HISTORY")
        self.assertIsNone(res.score)
        self.assertEqual(res.risk_category, "UNKNOWN")
        self.assertIn("3-month rolling precipitation is unobserved", res.explanation)

    def test_provisional_fallback_mode_computes_with_clear_flag(self):
        res = calculate_baseline_risk_score(self.boundary_record, allow_partial=True)
        self.assertEqual(res.status, "PROVISIONAL_PARTIAL_HISTORY")
        self.assertIsNotNone(res.score)
        self.assertTrue(0.0 <= res.score <= 100.0)
        self.assertIn("provisional single-month precipitation fallback", res.explanation)

    def test_both_rolling_and_current_missing_aborts_even_with_allow_partial(self):
        record = self.boundary_record.copy()
        record["precipitation_mm_day"] = np.nan
        res = calculate_baseline_risk_score(record, allow_partial=True)
        self.assertEqual(res.status, "INSUFFICIENT_HISTORY")
        self.assertIsNone(res.score)


class TestCategoryThresholds(unittest.TestCase):
    """Test exact threshold boundaries between Low, Medium, and High categories."""

    def test_threshold_transitions(self):
        # Low: [0.0, 35.0)
        self.assertEqual(classify_risk_category(0.0), "Low")
        self.assertEqual(classify_risk_category(34.99), "Low")

        # Medium: [35.0, 65.0)
        self.assertEqual(classify_risk_category(35.0), "Medium")
        self.assertEqual(classify_risk_category(50.0), "Medium")
        self.assertEqual(classify_risk_category(64.99), "Medium")

        # High: [65.0, 100.0]
        self.assertEqual(classify_risk_category(65.0), "High")
        self.assertEqual(classify_risk_category(85.5), "High")
        self.assertEqual(classify_risk_category(100.0), "High")

        # Unknown / None
        self.assertEqual(classify_risk_category(None), "UNKNOWN")
        self.assertEqual(classify_risk_category(np.nan), "UNKNOWN")


class TestDeterministicExecution(unittest.TestCase):
    """Verify that calculations are strictly deterministic and invariant across repeated runs."""

    def test_repeat_execution_consistency(self):
        record = {
            "date": "2022-05",
            "soil_moisture_rootzone_fraction": 0.42,
            "soil_temperature_layer1_c": 31.5,
            "topsoil_soc_g_kg": 12.95,
            "topsoil_ph_mean": 6.55,
            "precipitation_rolling_3m_mean_mm_day": 1.2,
            "precipitation_mm_day": 0.8,
        }
        res1 = calculate_baseline_risk_score(record)
        res2 = calculate_baseline_risk_score(record)
        self.assertEqual(res1.score, res2.score)
        self.assertEqual(res1.risk_category, res2.risk_category)
        self.assertEqual(res1.dynamic_environmental_stress, res2.dynamic_environmental_stress)
        self.assertEqual(res1.baseline_soil_vulnerability, res2.baseline_soil_vulnerability)


class TestSeparationOfDynamicAndStaticScales(unittest.TestCase):
    """Verify that dynamic environmental stressors and static soil baselines are kept distinct."""

    def test_varying_climate_leaves_soil_baseline_invariant(self):
        base_record = {
            "topsoil_soc_g_kg": 12.95,
            "topsoil_ph_mean": 6.55,
        }
        rec1 = {
            **base_record,
            "soil_moisture_rootzone_fraction": 0.40,
            "soil_temperature_layer1_c": 35.0,
            "precipitation_rolling_3m_mean_mm_day": 0.5,
        }
        rec2 = {
            **base_record,
            "soil_moisture_rootzone_fraction": 0.70,
            "soil_temperature_layer1_c": 22.0,
            "precipitation_rolling_3m_mean_mm_day": 6.0,
        }
        res1 = calculate_baseline_risk_score(rec1)
        res2 = calculate_baseline_risk_score(rec2)

        self.assertEqual(res1.baseline_soil_vulnerability, res2.baseline_soil_vulnerability)
        self.assertNotEqual(res1.dynamic_environmental_stress, res2.dynamic_environmental_stress)
        self.assertGreater(res1.dynamic_environmental_stress, res2.dynamic_environmental_stress)


class TestRealDatasetScoring(unittest.TestCase):
    """Test execution on the actual 60-row data/feature_table.csv without mutating it."""

    def test_feature_table_evaluation(self):
        csv_path = PROJECT_ROOT / "data" / "feature_table.csv"
        self.assertTrue(csv_path.exists(), "data/feature_table.csv must exist")

        df = pd.read_csv(csv_path)
        self.assertEqual(len(df), 60, "Must contain exactly 60 monthly records")

        # Run scoring with updated moisture buffering logic
        df_scored = score_feature_dataframe(df, allow_partial=True)

        for col in [
            "baseline_risk_score", "risk_category", "risk_status",
            "dynamic_environmental_stress", "baseline_soil_vulnerability", "risk_explanation"
        ]:
            self.assertIn(col, df_scored.columns)

        # All scores strictly within [0, 100]
        self.assertTrue(df_scored["baseline_risk_score"].between(0.0, 100.0).all())

        # Exact status distribution
        self.assertEqual((df_scored["risk_status"] == "COMPLETE").sum(), 58)
        self.assertEqual((df_scored["risk_status"] == "PROVISIONAL_PARTIAL_HISTORY").sum(), 2)

        # Verify month 0 and 1 were provisional
        self.assertEqual(df_scored.loc[0, "risk_status"], "PROVISIONAL_PARTIAL_HISTORY")
        self.assertEqual(df_scored.loc[1, "risk_status"], "PROVISIONAL_PARTIAL_HISTORY")
        self.assertEqual(df_scored.loc[2, "risk_status"], "COMPLETE")


class TestFormulaWeightsAndExactCalculation(unittest.TestCase):
    """Verify that scoring weights, grouping sums, and mathematical calculations match specification."""

    def test_formula_weights_exact_constants(self):
        """Verify the exact component weights and group totals."""
        self.assertEqual(WEIGHT_MOISTURE_DEFICIT, 0.30)
        self.assertEqual(WEIGHT_PRECIPITATION_DEFICIT, 0.25)
        self.assertEqual(WEIGHT_THERMAL_STRESS, 0.15)
        self.assertEqual(WEIGHT_SOC_DEPLETION, 0.15)
        self.assertEqual(WEIGHT_PH_DEVIATION, 0.15)

        # Dynamic Environmental Stress total = 0.70
        dynamic_sum = round(WEIGHT_MOISTURE_DEFICIT + WEIGHT_PRECIPITATION_DEFICIT + WEIGHT_THERMAL_STRESS, 6)
        self.assertEqual(dynamic_sum, 0.70)

        # Static Baseline Soil Vulnerability total = 0.30
        baseline_sum = round(WEIGHT_SOC_DEPLETION + WEIGHT_PH_DEVIATION, 6)
        self.assertEqual(baseline_sum, 0.30)

        # Overall sum = 1.00
        total_sum = round(dynamic_sum + baseline_sum, 6)
        self.assertEqual(total_sum, 1.00)

    def test_hand_calculated_composite_score(self):
        """
        Hand-calculate every component for a known synthetic record:
        - rootzone moisture = 0.50 (midpoint [0.25, 0.75] -> score = 50.0)
        - rolling precip = 3.25 mm/day (midpoint [0.5, 6.0] -> raw = 50.0)
          rootzone moisture 0.50 is midpoint of [0.35, 0.65] -> buffering factor = 0.75
          buffered precip score = round(50.0 * 0.75, 2) = 37.50
        - soil temp = 31.0 C (midpoint [24.0, 38.0] -> score = 50.0)
        - SOC = 15.0 g/kg (midpoint [5.0, 25.0] -> score = 50.0)
        - pH = 5.5 (dev = 1.0 unit from 6.5 -> 50.0% of 2.0 max dev -> score = 50.0)
        
        Dynamic weighted = 50.0*0.30 + 37.50*0.25 + 50.0*0.15 = 15.0 + 9.375 + 7.5 = 31.875
        Baseline weighted = 50.0*0.15 + 50.0*0.15 = 7.5 + 7.5 = 15.0
        Total composite = round(31.875 + 15.0, 2) = 46.88
        Category = 'Medium' (since 35.0 <= 46.88 < 65.0)
        """
        record = {
            "date": "2023-08",
            "soil_moisture_rootzone_fraction": 0.50,
            "soil_temperature_layer1_c": 31.0,
            "topsoil_soc_g_kg": 15.0,
            "topsoil_ph_mean": 5.5,
            "precipitation_rolling_3m_mean_mm_day": 3.25,
            "precipitation_mm_day": 3.25,
        }

        res = calculate_baseline_risk_score(record)
        self.assertEqual(res.status, "COMPLETE")
        self.assertEqual(res.indicators["moisture_deficit"]["sub_score"], 50.0)
        self.assertEqual(res.indicators["precipitation_deficit"]["raw_unbuffered_score"], 50.0)
        self.assertEqual(res.indicators["precipitation_deficit"]["moisture_buffering_factor"], 0.75)
        self.assertEqual(res.indicators["precipitation_deficit"]["sub_score"], 37.50)
        self.assertEqual(res.indicators["thermal_stress"]["sub_score"], 50.0)
        self.assertEqual(res.indicators["soc_vulnerability"]["sub_score"], 50.0)
        self.assertEqual(res.indicators["ph_deviation"]["sub_score"], 50.0)

        # Dynamic Stress Index normalized [0, 100] = 31.875 / 0.70 = 45.54
        self.assertAlmostEqual(res.dynamic_environmental_stress, round(31.875 / 0.70, 2), places=2)
        # Baseline Vulnerability Index normalized [0, 100] = 15.0 / 0.30 = 50.00
        self.assertEqual(res.baseline_soil_vulnerability, 50.0)

        # Final composite score
        self.assertEqual(res.score, 46.88)
        self.assertEqual(res.risk_category, "Medium")


if __name__ == "__main__":
    unittest.main()
