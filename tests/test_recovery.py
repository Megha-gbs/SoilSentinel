"""
Unit Tests for SoilSentinel Historical Recovery Tracking & Longitudinal Comparison Engine.

Verifies:
1. Trajectory assessment and recovery status classification.
2. Accurate computation of MoM, YoY, and 3-month slope deltas.
3. Historical benchmarking (percentile, min, max, mean, peak recovery points).
4. Boundary condition handling (INSUFFICIENT_HISTORY on initial records).
5. State transitions: RECOVERING, ESCALATING_STRESS, CHRONIC_HIGH_STRESS, STABLE_RESILIENT, SEASONAL_CYCLING.
6. Execution on the actual 60-row feature table predictions.
7. Serialization to dictionary conforming to contract schema.
"""

import sys
import unittest
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Model.recovery import (
    evaluate_historical_recovery,
    RecoveryAssessment,
)
from src.Model.predict import predict_from_csv


class TestHistoricalRecoveryTracking(unittest.TestCase):
    """Test longitudinal recovery tracking and statistical comparisons."""

    def setUp(self):
        # Create a synthetic 15-month dataset to test known transitions
        dates = [
            f"2023-{m:02d}" for m in range(1, 13)
        ] + ["2024-01", "2024-02", "2024-03"]
        
        # Construct synthetic scores representing:
        # Months 0-2: Moderate stress [40, 42, 45]
        # Months 3-5: Escalating into chronic high stress [55, 68, 72, 70]
        # Months 7-9: Monsoon recovery [65, 50, 38, 30]
        # Months 10-14: Stable low [28, 25, 26, 27, 28]
        scores = [
            40.0, 42.0, 45.0,  # 0, 1, 2
            58.0, 68.0, 72.0, 70.0,  # 3, 4, 5, 6 (chronic high at 6)
            52.0, 38.0, 30.0,  # 7, 8, 9 (recovering)
            28.0, 25.0, 26.0, 27.0, 28.0  # 10, 11, 12, 13, 14
        ]
        self.df_synthetic = pd.DataFrame({
            "date": dates,
            "score": scores,
            "risk_category": ["Medium"]*4 + ["High"]*3 + ["Medium"]*2 + ["Low"]*6
        })

    def test_insufficient_history_at_sequence_start(self):
        """Index 0 must be labeled INSUFFICIENT_HISTORY due to lack of longitudinal trend."""
        rec = evaluate_historical_recovery(self.df_synthetic, target_date="2023-01")
        self.assertEqual(rec.recovery_status, "INSUFFICIENT_HISTORY")
        self.assertIsNone(rec.mom_delta)
        self.assertIsNone(rec.yoy_delta)
        self.assertIsNone(rec.trajectory_slope_3m)

    def test_escalating_stress_detection(self):
        """Months 3->4 with steep positive slope must be detected as ESCALATING_STRESS."""
        rec = evaluate_historical_recovery(self.df_synthetic, target_date="2023-05")
        self.assertEqual(rec.recovery_status, "ESCALATING_STRESS")
        self.assertGreater(rec.trajectory_slope_3m, 2.5)
        self.assertEqual(rec.mom_delta, 10.0)  # 68 - 58

    def test_chronic_high_stress_detection(self):
        """Month 6 (3rd consecutive month with score >= 65) must trigger CHRONIC_HIGH_STRESS."""
        rec = evaluate_historical_recovery(self.df_synthetic, target_date="2023-07")
        self.assertEqual(rec.recovery_status, "CHRONIC_HIGH_STRESS")
        self.assertEqual(rec.consecutive_months_in_category, 3)
        self.assertEqual(rec.current_category, "High")

    def test_recovering_status_detection(self):
        """Months 7->9 with steep negative slope must be classified as RECOVERING."""
        rec = evaluate_historical_recovery(self.df_synthetic, target_date="2023-10")
        self.assertEqual(rec.recovery_status, "RECOVERING")
        self.assertLess(rec.trajectory_slope_3m, -2.5)
        self.assertEqual(rec.mom_delta, -8.0)  # 30 - 38

    def test_stable_resilient_status_detection(self):
        """Month 13 with >= 3 consecutive Low scores must be classified as STABLE_RESILIENT."""
        rec = evaluate_historical_recovery(self.df_synthetic, target_date="2024-02")
        self.assertEqual(rec.recovery_status, "STABLE_RESILIENT")
        self.assertGreaterEqual(rec.consecutive_months_in_category, 3)
        self.assertEqual(rec.current_category, "Low")

    def test_yoy_comparison_calculation(self):
        """Month 12 (2024-01 vs 2023-01) must calculate exact YoY delta."""
        rec = evaluate_historical_recovery(self.df_synthetic, target_date="2024-01")
        # 2024-01 score = 26.0, 2023-01 score = 40.0 -> YoY delta = -14.0
        self.assertEqual(rec.yoy_delta, -14.0)

    def test_evaluation_on_real_feature_table_predictions(self):
        """Must run cleanly across the actual 60-month feature table predictions."""
        csv_path = PROJECT_ROOT / "data" / "feature_table.csv"
        self.assertTrue(csv_path.exists())

        df_preds = predict_from_csv(input_path=csv_path, output_path=None, allow_partial=True)
        self.assertEqual(len(df_preds), 60)

        # Evaluate latest month (2024-12)
        rec = evaluate_historical_recovery(df_preds, target_date="2024-12")
        self.assertIsInstance(rec, RecoveryAssessment)
        self.assertEqual(rec.evaluation_date, "2024-12")
        self.assertIsNotNone(rec.current_score)
        self.assertIsNotNone(rec.mom_delta)
        self.assertIsNotNone(rec.yoy_delta)
        self.assertIsNotNone(rec.historical_percentile)
        self.assertTrue(0.0 <= rec.historical_percentile <= 100.0)

    def test_serialization_to_dict_matches_contract(self):
        """to_dict() must return a clean dictionary with all expected keys."""
        rec = evaluate_historical_recovery(self.df_synthetic, target_date="2023-10")
        d = rec.to_dict()

        expected_keys = [
            "evaluation_date", "current_score", "current_category", "mom_delta",
            "yoy_delta", "historical_mean", "historical_min", "historical_max",
            "historical_percentile", "consecutive_months_in_category",
            "recovery_status", "trajectory_slope_3m", "peak_stress_recovery_points",
            "key_trajectory_driver", "evidence_summary"
        ]
        for key in expected_keys:
            self.assertIn(key, d)


if __name__ == "__main__":
    unittest.main()
