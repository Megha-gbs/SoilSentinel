"""
Integration Tests for SoilSentinel Unified Backend Service & Dashboard Handoff Engine.

Verifies:
1. End-to-end integration of data loading, scoring, recommendations, scenarios, recovery,
   crop eligibility, and audit logging.
2. Available dates discovery and latest date resolution.
3. Full dashboard payload structure and complete JSON serializability.
4. Correctness of nested section dictionaries conforming to dashboard schemas.
5. Interactive custom scenario evaluation (rainfall, temperature, SOC shifts).
6. In-memory DataFrame ingestion via load_dataframe().
7. Safe append-only audit logging integration without log truncation.
8. Module-level get_dashboard_payload() caching and retrieval.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Model.service import (
    SoilSentinelService,
    get_dashboard_payload,
)


class TestSoilSentinelServiceIntegration(unittest.TestCase):
    """Test suite for the unified service and dashboard handoff contracts."""

    @classmethod
    def setUpClass(cls):
        cls.data_path = PROJECT_ROOT / "data" / "feature_table.csv"
        cls.service = SoilSentinelService(data_path=cls.data_path)

    def test_available_dates_and_latest_date(self):
        """Service must discover and sort 60 monthly records from 2020-01 to 2024-12."""
        dates = self.service.get_available_dates()
        self.assertEqual(len(dates), 60)
        self.assertEqual(dates[0], "2020-01")
        self.assertEqual(dates[-1], "2024-12")
        self.assertEqual(self.service.get_latest_date(), "2024-12")

    def test_get_raw_and_scored_records(self):
        """Must retrieve raw and scored records matching target date."""
        raw = self.service.get_raw_record("2024-06")
        self.assertEqual(str(raw["date"]), "2024-06")
        self.assertIn("soil_temperature_layer1_c", raw)

        scored = self.service.get_scored_record("2024-06")
        self.assertEqual(str(scored["date"]), "2024-06")
        self.assertIn("score", scored)
        self.assertIn("risk_category", scored)

    def test_dashboard_payload_structure_and_json_serialization(self):
        """get_dashboard_payload() must produce a 100% JSON-serializable dictionary with all required blocks."""
        payload = self.service.get_dashboard_payload(date="2024-08")
        
        # Verify JSON serializability
        serialized = json.dumps(payload)
        self.assertIsInstance(serialized, str)

        # Verify Top-level Keys
        expected_top_keys = [
            "metadata", "risk_assessment", "recommendations",
            "recovery_tracking", "crop_eligibility", "scenario_comparison",
            "historical_series"
        ]
        for key in expected_top_keys:
            self.assertIn(key, payload)

        # Verify Metadata
        meta = payload["metadata"]
        self.assertEqual(meta["evaluation_date"], "2024-08")
        self.assertIn("engine_version", meta)
        self.assertIn("generated_at_utc", meta)

        # Verify Risk Assessment
        risk = payload["risk_assessment"]
        self.assertIn("score", risk)
        self.assertIn("risk_category", risk)
        self.assertIn("indicators", risk)
        self.assertIn("dynamic_environmental_stress", risk)
        self.assertIn("baseline_soil_vulnerability", risk)

        # Verify Recommendations
        recs = payload["recommendations"]
        self.assertIn("status", recs)
        self.assertIn("overall_risk_category", recs)
        self.assertIn("primary_stressor", recs)
        self.assertIn("recommendations", recs)
        self.assertIsInstance(recs["recommendations"], list)

        # Verify Recovery Tracking
        recov = payload["recovery_tracking"]
        self.assertIn("recovery_status", recov)
        self.assertIn("mom_delta", recov)
        self.assertIn("yoy_delta", recov)
        self.assertIn("historical_percentile", recov)

        # Verify Crop Eligibility
        crop = payload["crop_eligibility"]
        self.assertIn("is_eligible", crop)
        self.assertIn("withhold_reasons", crop)
        self.assertIn("season", crop)
        self.assertIn("recommended_crops", crop)
        self.assertIn("restricted_crops", crop)
        self.assertIn("disclaimer", crop)

        # Verify Scenario Comparison
        scenarios = payload["scenario_comparison"]
        self.assertIsNotNone(scenarios)
        self.assertEqual(scenarios["baseline_date"], "2024-08")
        self.assertIn("comparisons", scenarios)
        self.assertEqual(len(scenarios["comparisons"]), 3)
        self.assertIn("dry_spell", scenarios["comparisons"])

        # Verify Historical Series
        hist = payload["historical_series"]
        self.assertEqual(len(hist), 60)
        self.assertEqual(hist[-1]["date"], "2024-12")

        # Verify Independent Degradation Assessment Block
        self.assertIn("independent_degradation_assessment", payload)
        indep = payload["independent_degradation_assessment"]
        self.assertEqual(indep["status"], "PENDING_INDEPENDENT_GROUND_TRUTH")
        self.assertEqual(indep["validation_status"], "NOT_VALIDATED_AGAINST_PHYSICAL_GROUND_TRUTH")
        self.assertEqual(indep["model_execution"], "BLOCKED_PENDING_INDEPENDENT_LABELS")
        self.assertIn("target_definition", indep)
        self.assertIn("surrogate_comparison", indep)
        self.assertIn("evidence", indep)
        self.assertIn("limitations", indep)
        self.assertIsInstance(indep["limitations"], list)

    def test_custom_scenario_evaluation(self):
        """evaluate_custom_scenario() must simulate interactive slider values."""
        # Simulate custom acute heatwave + drought condition
        custom_res = self.service.evaluate_custom_scenario(
            date="2024-07",
            custom_precipitation=0.2,
            custom_temperature=42.0
        )
        self.assertIn("scenario_name", custom_res)
        self.assertIn("scenario_atmospheric_score", custom_res)
        self.assertIn("delta_score", custom_res)
        self.assertIn("category_shift", custom_res)
        self.assertIn("resilience_assessment", custom_res)

    def test_load_in_memory_dataframe(self):
        """Service must function correctly when fed an in-memory DataFrame directly."""
        df_sample = pd.read_csv(self.data_path).head(12)
        fresh_service = SoilSentinelService(auto_score=False)
        fresh_service.load_dataframe(df_sample)
        
        dates = fresh_service.get_available_dates()
        self.assertEqual(len(dates), 12)
        payload = fresh_service.get_dashboard_payload(date="2020-06")
        self.assertEqual(payload["metadata"]["evaluation_date"], "2020-06")

    def test_safe_audit_logging_flag(self):
        """log_audit=True must safely append to audit log without corrupting file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_audit_path = Path(tmp_dir) / "test_audit_log.csv"
            svc = SoilSentinelService(
                data_path=self.data_path,
                audit_log_path=temp_audit_path
            )
            payload = svc.get_dashboard_payload(date="2024-12", log_audit=True)
            self.assertTrue(payload["metadata"]["audit_logged"])
            self.assertTrue(temp_audit_path.exists())

            # Read back audit log
            df_log = pd.read_csv(temp_audit_path)
            self.assertEqual(len(df_log), 1)
            self.assertEqual(str(df_log.iloc[0]["input_date"]), "2024-12")
            self.assertEqual(str(df_log.iloc[0]["assessment_id"]), payload["metadata"]["assessment_id"])
            self.assertTrue(len(str(df_log.iloc[0]["recommendation_ids"])) > 0)
            self.assertEqual(df_log.iloc[0]["assessment_id"], payload["audit_reference"]["assessment_id"])

    def test_module_level_get_dashboard_payload(self):
        """Top-level get_dashboard_payload() convenience function returns valid payload."""
        payload = get_dashboard_payload(date="2024-12", data_path=self.data_path)
        self.assertEqual(payload["metadata"]["evaluation_date"], "2024-12")
        self.assertIn("risk_assessment", payload)


if __name__ == "__main__":
    unittest.main()
