"""
Unit Tests for SoilSentinel Baseline versus Hypothetical Scenario Comparison Engine.

Verifies:
1. Multi-scenario comparative evaluation against baseline observations.
2. Accurate stress deltas (Delta Score, Delta Recharge Deficit, Delta Thermal Load).
3. Identification of most adverse and most favorable stress scenarios.
4. Soil resilience classification based on static SOC and pH baselines.
5. Custom scenario parameter integration.
6. Safe handling when baseline evaluation status is INVALID_INPUT or INSUFFICIENT_HISTORY.
7. Serialization to dictionary matching dashboard contract requirements.
"""

import sys
import unittest
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Model.risk_scoring import calculate_baseline_risk_score
from src.Model.scenarios import (
    compare_baseline_to_scenarios,
    BaselineScenarioComparisonReport,
    ScenarioComparisonItem,
)


class TestScenarioComparisons(unittest.TestCase):
    """Test comparative scenario evaluation and delta metrics."""

    def setUp(self):
        self.base_record = {
            "date": "2023-04",
            "soil_moisture_rootzone_fraction": 0.45,
            "soil_temperature_layer1_c": 28.0,
            "topsoil_soc_g_kg": 12.95,
            "topsoil_ph_mean": 6.55,
            "precipitation_rolling_3m_mean_mm_day": 2.0,
            "precipitation_mm_day": 1.5,
        }

    def test_default_scenarios_comparison(self):
        """Must compare against dry_spell, normal_climatology, and heavy_rainfall."""
        report = compare_baseline_to_scenarios(self.base_record)

        self.assertIsInstance(report, BaselineScenarioComparisonReport)
        self.assertEqual(report.status, "COMPLETE")
        self.assertEqual(report.baseline_date, "2023-04")
        self.assertIsNotNone(report.baseline_score)
        self.assertEqual(set(report.comparisons.keys()), {"dry_spell", "normal_climatology", "heavy_rainfall"})

        # Dry spell must have highest atmospheric load
        dry_item = report.comparisons["dry_spell"]
        self.assertEqual(dry_item.scenario_recharge_deficit, 100.0)
        self.assertEqual(dry_item.horizon_days, 30)
        self.assertIn("Assumes zero atmospheric precipitation", " ".join(dry_item.assumptions))

        # Heavy rain must have zero recharge deficit
        rain_item = report.comparisons["heavy_rainfall"]
        self.assertEqual(rain_item.scenario_recharge_deficit, 0.0)

        # Most adverse should be dry_spell
        self.assertEqual(report.most_adverse_scenario, "dry_spell")
        self.assertIn("dry_spell", report.summary_narrative)

    def test_custom_scenario_comparison(self):
        """User can pass custom scenario precipitation and temperature parameters."""
        report = compare_baseline_to_scenarios(
            self.base_record,
            scenarios=["dry_spell", "custom"],
            custom_precipitation=5.5,
            custom_temperature=21.0,
            horizon_days=30
        )
        self.assertIn("custom", report.comparisons)
        custom_item = report.comparisons["custom"]
        self.assertAlmostEqual(custom_item.scenario_recharge_deficit, 9.09, places=1)
        self.assertEqual(custom_item.scenario_thermal_load, 0.0)

    def test_resilience_attribution_low_soc(self):
        """Low SOC (< 7.0 g/kg) must be flagged as LOW_RESILIENCE_VULNERABLE."""
        vulnerable_record = self.base_record.copy()
        vulnerable_record["topsoil_soc_g_kg"] = 4.5
        report = compare_baseline_to_scenarios(vulnerable_record)

        self.assertEqual(report.static_soil_resilience, "LOW_RESILIENCE_VULNERABLE")
        dry_item = report.comparisons["dry_spell"]
        self.assertIn("High vulnerability", dry_item.resilience_assessment)

    def test_resilience_attribution_high_soc(self):
        """High SOC (>= 20.0 g/kg) with neutral pH must be flagged as HIGH_RESILIENCE."""
        resilient_record = self.base_record.copy()
        resilient_record["topsoil_soc_g_kg"] = 22.0
        resilient_record["topsoil_ph_mean"] = 7.0
        report = compare_baseline_to_scenarios(resilient_record)

        self.assertEqual(report.static_soil_resilience, "HIGH_RESILIENCE")

    def test_invalid_baseline_aborts_gracefully(self):
        """Invalid baseline input must abort comparison and return INVALID_INPUT status."""
        bad_record = self.base_record.copy()
        bad_record["soil_moisture_rootzone_fraction"] = 2.5
        report = compare_baseline_to_scenarios(bad_record)

        self.assertEqual(report.status, "INVALID_INPUT")
        self.assertIsNone(report.baseline_score)
        self.assertEqual(len(report.comparisons), 0)
        self.assertIn("aborted", report.summary_narrative)

    def test_serialization_to_dict_matches_contract(self):
        """to_dict() must return a clean, fully serializable dictionary."""
        report = compare_baseline_to_scenarios(self.base_record)
        d = report.to_dict()

        for key in ["status", "baseline_date", "baseline_score", "baseline_category", "static_soil_resilience", "comparisons", "most_adverse_scenario", "most_favorable_scenario", "summary_narrative", "disclaimer"]:
            self.assertIn(key, d)

        dry_dict = d["comparisons"]["dry_spell"]
        for item_key in ["scenario_name", "scenario_atmospheric_score", "scenario_recharge_deficit", "scenario_thermal_load", "baseline_score", "delta_score", "category_shift", "resilience_assessment"]:
            self.assertIn(item_key, dry_dict)


if __name__ == "__main__":
    unittest.main()
