"""
Unit Tests for Soil Sentinel Portable Prediction Interface.

Verifies:
1. Single-record prediction output schema and accuracy.
2. Single-record handling of missing required features and invalid bounds.
3. Batch prediction across DataFrame rows.
4. Input validation and clear ValueError when required columns are absent.
5. Missing historical context handling under both Strict and Permissive modes.
6. Score and risk category preservation relative to underlying scoring engine.
7. Deterministic reproducibility across repeated invocations.
8. CSV execution workflow (reading input, writing to output directory).
9. Guard preventing accidental overwrite of the source feature table.
"""

import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Model.predict import (
    predict_record,
    predict_dataframe,
    predict_from_csv,
    REQUIRED_FEATURE_COLUMNS,
    IDENTIFIER_COLUMNS,
)
from src.Model.risk_scoring import (
    calculate_baseline_risk_score,
    INDEX_NAME,
    ASSUMPTIONS_LABEL,
)


class TestPredictSingleRecord(unittest.TestCase):
    """Test single-record prediction interface."""

    def setUp(self):
        self.valid_record = {
            "region": "Indo-Gangetic Agricultural Plains / Punjab",
            "nominal_latitude": 30.73,
            "nominal_longitude": 76.77,
            "sampled_latitude": 30.7392,
            "sampled_longitude": 76.7764,
            "year": 2023,
            "month": 7,
            "date": "2023-07",
            "season": "Monsoon",
            "soil_moisture_rootzone_fraction": 0.60,
            "soil_temperature_layer1_c": 29.5,
            "topsoil_soc_g_kg": 12.95,
            "topsoil_ph_mean": 6.55,
            "precipitation_rolling_3m_mean_mm_day": 5.0,
            "precipitation_mm_day": 6.2,
        }

    def test_single_record_valid_prediction(self):
        pred = predict_record(self.valid_record)

        # Identifiers preserved
        self.assertEqual(pred["region"], "Indo-Gangetic Agricultural Plains / Punjab")
        self.assertEqual(pred["date"], "2023-07")
        self.assertEqual(pred["year"], 2023)
        self.assertEqual(pred["month"], 7)
        self.assertEqual(pred["season"], "Monsoon")

        # Core index outputs
        self.assertEqual(pred["index_name"], INDEX_NAME)
        self.assertIsNotNone(pred["score"])
        self.assertTrue(0.0 <= pred["score"] <= 100.0)
        self.assertIn(pred["risk_category"], ["Low", "Medium", "High"])
        self.assertEqual(pred["status"], "COMPLETE")
        self.assertIsNotNone(pred["dynamic_environmental_stress"])
        self.assertIsNotNone(pred["baseline_soil_vulnerability"])

        # Sub-scores present
        self.assertIsNotNone(pred["moisture_deficit_sub_score"])
        self.assertIsNotNone(pred["precipitation_deficit_sub_score"])
        self.assertIsNotNone(pred["thermal_stress_sub_score"])
        self.assertIsNotNone(pred["soc_vulnerability_sub_score"])
        self.assertIsNotNone(pred["ph_deviation_sub_score"])

        # Metadata
        self.assertIn("Record [2023-07] Index:", pred["explanation"])
        self.assertEqual(pred["assumptions_label"], ASSUMPTIONS_LABEL)

    def test_single_record_missing_required_column(self):
        record = self.valid_record.copy()
        del record["soil_moisture_rootzone_fraction"]

        pred = predict_record(record)
        self.assertEqual(pred["status"], "INVALID_INPUT")
        self.assertIsNone(pred["score"])
        self.assertEqual(pred["risk_category"], "UNKNOWN")
        self.assertIn("Missing essential field", pred["explanation"])

    def test_single_record_invalid_physical_bounds(self):
        record = self.valid_record.copy()
        record["soil_temperature_layer1_c"] = 120.0  # Impossible soil temp

        pred = predict_record(record)
        self.assertEqual(pred["status"], "INVALID_INPUT")
        self.assertIsNone(pred["score"])
        self.assertEqual(pred["risk_category"], "UNKNOWN")

    def test_single_record_with_pd_na_identifiers(self):
        record = self.valid_record.copy()
        record["season"] = pd.NA
        pred = predict_record(record)
        self.assertIsNone(pred["season"])
        self.assertEqual(pred["status"], "COMPLETE")

    def test_single_record_negative_rolling_precip_aborts(self):
        record = self.valid_record.copy()
        record["precipitation_rolling_3m_mean_mm_day"] = -4.0
        pred = predict_record(record)
        self.assertEqual(pred["status"], "INVALID_INPUT")
        self.assertIsNone(pred["score"])
        self.assertEqual(pred["risk_category"], "UNKNOWN")


class TestPredictDataFrame(unittest.TestCase):
    """Test batch DataFrame prediction logic."""

    def setUp(self):
        self.sample_df = pd.DataFrame([
            {
                "date": "2023-01",
                "soil_moisture_rootzone_fraction": 0.55,
                "soil_temperature_layer1_c": 16.0,
                "topsoil_soc_g_kg": 12.95,
                "topsoil_ph_mean": 6.55,
                "precipitation_rolling_3m_mean_mm_day": 1.5,
                "precipitation_mm_day": 1.0,
            },
            {
                "date": "2023-06",
                "soil_moisture_rootzone_fraction": 0.38,
                "soil_temperature_layer1_c": 36.5,
                "topsoil_soc_g_kg": 12.95,
                "topsoil_ph_mean": 6.55,
                "precipitation_rolling_3m_mean_mm_day": 1.2,
                "precipitation_mm_day": 2.0,
            },
        ])

    def test_batch_prediction_success(self):
        preds = predict_dataframe(self.sample_df)
        self.assertIsInstance(preds, pd.DataFrame)
        self.assertEqual(len(preds), 2)
        self.assertIn("score", preds.columns)
        self.assertIn("risk_category", preds.columns)
        self.assertIn("status", preds.columns)
        self.assertTrue(preds["score"].between(0.0, 100.0).all())

    def test_missing_required_column_raises_value_error(self):
        bad_df = self.sample_df.drop(columns=["topsoil_ph_mean"])
        with self.assertRaises(ValueError) as ctx:
            predict_dataframe(bad_df)
        self.assertIn("missing required feature column", str(ctx.exception))

    def test_empty_dataframe_raises_value_error(self):
        empty_df = pd.DataFrame()
        with self.assertRaises(ValueError) as ctx:
            predict_dataframe(empty_df)
        self.assertIn("empty DataFrame", str(ctx.exception))


class TestMissingHistoryModes(unittest.TestCase):
    """Test missing historical lag context under Strict vs Permissive modes."""

    def setUp(self):
        self.boundary_record = {
            "date": "2020-01",
            "soil_moisture_rootzone_fraction": 0.52,
            "soil_temperature_layer1_c": 10.37,
            "topsoil_soc_g_kg": 12.95,
            "topsoil_ph_mean": 6.55,
            "precipitation_rolling_3m_mean_mm_day": np.nan,  # Missing rolling context
            "precipitation_mm_day": 2.73,                     # Observed single-month
        }

    def test_strict_mode_yields_insufficient_history(self):
        pred = predict_record(self.boundary_record, allow_partial=False)
        self.assertEqual(pred["status"], "INSUFFICIENT_HISTORY")
        self.assertIsNone(pred["score"])
        self.assertEqual(pred["risk_category"], "UNKNOWN")

    def test_permissive_mode_yields_provisional_partial_history(self):
        pred = predict_record(self.boundary_record, allow_partial=True)
        self.assertEqual(pred["status"], "PROVISIONAL_PARTIAL_HISTORY")
        self.assertIsNotNone(pred["score"])
        self.assertTrue(0.0 <= pred["score"] <= 100.0)
        self.assertIn("provisional single-month precipitation fallback", pred["explanation"])


class TestEngineParityAndDeterminism(unittest.TestCase):
    """Verify that predict.py produces results identical to risk_scoring.py."""

    def test_engine_parity(self):
        record = {
            "date": "2024-04",
            "soil_moisture_rootzone_fraction": 0.44,
            "soil_temperature_layer1_c": 31.0,
            "topsoil_soc_g_kg": 12.95,
            "topsoil_ph_mean": 6.55,
            "precipitation_rolling_3m_mean_mm_day": 2.1,
            "precipitation_mm_day": 1.8,
        }
        res_direct = calculate_baseline_risk_score(record)
        pred_wrapped = predict_record(record)

        self.assertEqual(pred_wrapped["score"], res_direct.score)
        self.assertEqual(pred_wrapped["risk_category"], res_direct.risk_category)
        self.assertEqual(pred_wrapped["status"], res_direct.status)
        self.assertEqual(pred_wrapped["dynamic_environmental_stress"], res_direct.dynamic_environmental_stress)
        self.assertEqual(pred_wrapped["baseline_soil_vulnerability"], res_direct.baseline_soil_vulnerability)

    def test_deterministic_reproducibility(self):
        record = {
            "date": "2021-08",
            "soil_moisture_rootzone_fraction": 0.72,
            "soil_temperature_layer1_c": 28.0,
            "topsoil_soc_g_kg": 12.95,
            "topsoil_ph_mean": 6.55,
            "precipitation_rolling_3m_mean_mm_day": 8.5,
            "precipitation_mm_day": 9.2,
        }
        pred1 = predict_record(record)
        pred2 = predict_record(record)
        self.assertEqual(pred1, pred2)


class TestCSVWorkflow(unittest.TestCase):
    """Test reading input CSV and writing predictions to a destination path."""

    def test_predict_from_csv_in_tempdir(self):
        feature_csv = PROJECT_ROOT / "data" / "feature_table.csv"
        self.assertTrue(feature_csv.exists(), "data/feature_table.csv must exist")

        with tempfile.TemporaryDirectory() as tmpdir:
            out_csv = Path(tmpdir) / "outputs" / "test_predictions.csv"
            preds = predict_from_csv(
                input_path=feature_csv,
                output_path=out_csv,
                allow_partial=True,
                audit_log_path=None
            )

            # Check DataFrame shape
            self.assertEqual(len(preds), 60)
            self.assertTrue(out_csv.exists())

            # Read back from disk
            df_disk = pd.read_csv(out_csv)
            self.assertEqual(len(df_disk), 60)
            self.assertIn("score", df_disk.columns)
            self.assertIn("risk_category", df_disk.columns)
            self.assertIn("status", df_disk.columns)

    def test_prevent_source_feature_table_overwrite(self):
        feature_csv = PROJECT_ROOT / "data" / "feature_table.csv"
        with self.assertRaises(ValueError) as ctx:
            predict_from_csv(input_path=feature_csv, output_path=feature_csv)
        self.assertIn("Overwriting the source feature table is prohibited", str(ctx.exception))


class TestModelArtifactSafetyGuard(unittest.TestCase):
    """Verify safety guards and genuine ML model artifact validation."""

    def test_load_trained_model_on_zero_bytes_raises_runtime_error(self):
        """Zero-byte / unpopulated placeholders must be explicitly rejected with RuntimeError."""
        from src.Model.model import load_trained_model
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".joblib") as tmp:
            with self.assertRaises(RuntimeError) as ctx:
                load_trained_model(tmp.name)
            self.assertIn("does not load or execute unpopulated ML model binaries", str(ctx.exception))
            self.assertIn("0 bytes", str(ctx.exception))

    def test_trained_joblib_file_is_valid_and_non_zero_bytes(self):
        """The genuine trained model artifact must exist, exceed 0 bytes, and load successfully."""
        from src.Model.model import load_trained_model
        joblib_path = PROJECT_ROOT / "models" / "soil_risk_model.joblib"
        self.assertTrue(joblib_path.exists(), "models/soil_risk_model.joblib must exist")
        self.assertGreater(joblib_path.stat().st_size, 0, "Trained joblib must be non-zero bytes")

        model = load_trained_model(joblib_path)
        self.assertTrue(hasattr(model, "predict"), "Loaded model must implement predict() method")


if __name__ == "__main__":
    unittest.main()

