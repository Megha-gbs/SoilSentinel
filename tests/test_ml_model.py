"""
Unit and Integration Tests for SoilSentinel Machine Learning Pipeline & Model Inference.

Tests:
1. Feature schema integrity and target leakage prevention.
2. Model artifact serialization and metadata manifest completeness.
3. Model loading safety guards (rejection of 0-byte, corrupt, or missing files).
4. Predict interface (predict_ml) for single records and DataFrames.
5. Probability distribution validity (probabilities non-negative, summing to 1.0).
6. Graceful imputation of missing boundary lag/rolling values.
7. Non-breaking integration into SoilSentinelService.get_dashboard_payload().
8. End-to-end JSON serializability of dashboard payloads containing ml_prediction.
"""

import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Model.model import (
    load_trained_model,
    load_model_metadata,
    load_explainer,
    load_preprocessor,
    predict_ml,
    explain_prediction,
    FEATURE_COLUMNS,
    DEFAULT_MODEL_PATH,
    DEFAULT_PREPROCESSOR_PATH,
    DEFAULT_EXPLAINER_PATH,
    DEFAULT_METADATA_PATH,
)
from src.Model.service import SoilSentinelService


class TestSoilSentinelMLModel(unittest.TestCase):
    """Test suite for machine learning model loading, validation, and inference."""

    @classmethod
    def setUpClass(cls):
        cls.data_path = PROJECT_ROOT / "data" / "feature_table.csv"
        cls.df_features = pd.read_csv(cls.data_path)
        cls.service = SoilSentinelService(data_path=cls.data_path)

    def test_feature_schema_columns_zero_leakage(self):
        """Feature schema must contain only physical/temporal features and zero rule outputs."""
        self.assertEqual(len(FEATURE_COLUMNS), 14)

        prohibited_leakage_columns = [
            "score",
            "risk_category",
            "status",
            "dynamic_environmental_stress",
            "baseline_soil_vulnerability",
            "moisture_deficit_sub_score",
            "precipitation_deficit_sub_score",
            "precipitation_deficit_raw_unbuffered",
            "moisture_buffering_factor",
            "thermal_stress_sub_score",
            "soc_vulnerability_sub_score",
            "ph_deviation_sub_score",
            "explanation",
        ]
        for col in prohibited_leakage_columns:
            self.assertNotIn(col, FEATURE_COLUMNS, f"Target leakage column '{col}' found in FEATURE_COLUMNS")

        # Verify all 14 features are present in the feature table
        for col in FEATURE_COLUMNS:
            self.assertIn(col, self.df_features.columns, f"Feature column '{col}' missing from feature_table.csv")

    def test_model_artifact_exists_and_valid(self):
        """The trained model artifact must exist, exceed 10 KB, and implement predict."""
        self.assertTrue(DEFAULT_MODEL_PATH.exists(), f"Model artifact not found at {DEFAULT_MODEL_PATH}")
        file_size = DEFAULT_MODEL_PATH.stat().st_size
        self.assertGreater(file_size, 10000, f"Model artifact is unexpectedly small ({file_size} bytes)")

        model = load_trained_model(DEFAULT_MODEL_PATH)
        self.assertTrue(hasattr(model, "predict"), "Model must implement predict() method")
        self.assertTrue(hasattr(model, "predict_proba"), "Model must implement predict_proba() method")

    def test_metadata_manifest_contents(self):
        """Metadata manifest must document algorithm, metrics, provenance, and split strategy."""
        self.assertTrue(DEFAULT_METADATA_PATH.exists(), f"Metadata not found at {DEFAULT_METADATA_PATH}")
        metadata = load_model_metadata(DEFAULT_METADATA_PATH)

        self.assertIn("algorithm", metadata)
        self.assertEqual(metadata["algorithm"], "Random Forest Classifier")
        self.assertIn("target_provenance", metadata)
        self.assertEqual(metadata["target_provenance"], "SURROGATE_PROXY_LEARNING")

        self.assertIn("evaluation_metrics", metadata)
        metrics = metadata["evaluation_metrics"]
        self.assertIn("test", metrics)
        self.assertGreaterEqual(metrics["test"]["accuracy"], 0.85)
        self.assertGreaterEqual(metrics["test"]["macro_f1"], 0.85)

        self.assertIn("split_methodology", metadata)
        self.assertEqual(metadata["split_methodology"]["strategy"], "Chronological Split")

    def test_predict_ml_single_record(self):
        """predict_ml must return valid status, class, and probabilities on a real row."""
        sample_record = self.df_features.iloc[10].to_dict()
        res = predict_ml(sample_record)

        self.assertEqual(res["status"], "AVAILABLE")
        self.assertIn(res["predicted_category"], ["Low", "Medium", "High"])
        self.assertIsInstance(res["class_probabilities"], dict)

        # Probabilities must sum to approximately 1.0
        prob_sum = sum(res["class_probabilities"].values())
        self.assertAlmostEqual(prob_sum, 1.0, places=2)

        # Keys must include Low, Medium, High
        for cat in ["High", "Low", "Medium"]:
            self.assertIn(cat, res["class_probabilities"])

    def test_predict_ml_with_missing_boundary_values(self):
        """predict_ml must smoothly impute missing boundary lag/rolling values."""
        # Row 0 has NaN in lag features
        row_0 = self.df_features.iloc[0].to_dict()
        res = predict_ml(row_0)

        self.assertEqual(res["status"], "AVAILABLE")
        self.assertIn(res["predicted_category"], ["Low", "Medium", "High"])
        self.assertIsNotNone(res["class_probabilities"])

    def test_safety_guard_rejects_empty_file(self):
        """load_trained_model must raise RuntimeError when attempting to load a 0-byte file."""
        with tempfile.NamedTemporaryFile(suffix=".joblib") as tmp:
            with self.assertRaises(RuntimeError) as ctx:
                load_trained_model(tmp.name)
            self.assertIn("unpopulated placeholder", str(ctx.exception))
            self.assertIn("0 bytes", str(ctx.exception))

    def test_safety_guard_rejects_nonexistent_file(self):
        """load_trained_model must raise FileNotFoundError for missing path."""
        bogus_path = PROJECT_ROOT / "models" / "non_existent_model_12345.joblib"
        with self.assertRaises(FileNotFoundError):
            load_trained_model(bogus_path)

    def test_safety_guard_rejects_corrupted_file(self):
        """load_trained_model must raise RuntimeError for corrupted binary."""
        with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as tmp:
            tmp.write(b"NOT_A_VALID_JOBLIB_BINARY_HEADER_DATA")
            tmp_path = Path(tmp.name)

        try:
            with self.assertRaises(RuntimeError) as ctx:
                load_trained_model(tmp_path)
            self.assertIn("Failed to deserialize", str(ctx.exception))
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_service_payload_includes_ml_prediction(self):
        """SoilSentinelService.get_dashboard_payload() must include ml_prediction object."""
        payload = self.service.get_dashboard_payload(date="2024-06")

        self.assertIn("ml_prediction", payload)
        ml = payload["ml_prediction"]
        self.assertIsNotNone(ml)
        self.assertEqual(ml["status"], "AVAILABLE")
        self.assertIn(ml["predicted_category"], ["Low", "Medium", "High"])
        self.assertIsInstance(ml["class_probabilities"], dict)
        self.assertEqual(ml["target_provenance"], "SURROGATE_PROXY_LEARNING")
        self.assertIn("disclaimer", ml)

        # Entire payload must remain 100% JSON-serializable
        serialized = json.dumps(payload)
        self.assertIsInstance(serialized, str)

    def test_explainer_artifact_exists_and_loads(self):
        """The SHAP TreeExplainer artifact must exist, exceed 50 KB, and load safely."""
        self.assertTrue(DEFAULT_EXPLAINER_PATH.exists(), f"SHAP explainer not found at {DEFAULT_EXPLAINER_PATH}")
        file_size = DEFAULT_EXPLAINER_PATH.stat().st_size
        self.assertGreater(file_size, 50000, f"Explainer artifact unexpectedly small ({file_size} bytes)")

        explainer = load_explainer(DEFAULT_EXPLAINER_PATH)
        self.assertTrue(hasattr(explainer, "shap_values"), "Explainer must implement shap_values() method")
        self.assertTrue(hasattr(explainer, "expected_value"), "Explainer must provide expected_value baseline")

    def test_explainer_safety_guards_rejection(self):
        """load_explainer must reject 0-byte placeholders, missing paths, and corrupted files."""
        # 1. Reject 0-byte file
        with tempfile.NamedTemporaryFile(suffix=".joblib") as tmp:
            with self.assertRaises(RuntimeError) as ctx:
                load_explainer(tmp.name)
            self.assertIn("unpopulated placeholder", str(ctx.exception))

        # 2. Reject missing file
        bogus_path = PROJECT_ROOT / "models" / "non_existent_explainer_99999.joblib"
        with self.assertRaises(FileNotFoundError):
            load_explainer(bogus_path)

        # 3. Reject corrupted file
        with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as tmp:
            tmp.write(b"CORRUPT_NOT_A_VALID_JOBLIB_BINARY")
            tmp_path = Path(tmp.name)

        try:
            with self.assertRaises(RuntimeError) as ctx:
                load_explainer(tmp_path)
            self.assertIn("Failed to deserialize", str(ctx.exception))
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_explain_prediction_structure_and_direction(self):
        """explain_prediction must return valid JSON-native values, signed impacts, and physical values."""
        sample_record = self.df_features.iloc[10].to_dict()
        res = explain_prediction(sample_record)

        self.assertEqual(res["status"], "AVAILABLE")
        self.assertIn(res["predicted_class"], ["High", "Low", "Medium"])
        self.assertEqual(res["explained_class"], res["predicted_class"])
        self.assertIsInstance(res["prediction_probability"], float)
        self.assertIsInstance(res["base_value"], float)
        self.assertIsInstance(res["sum_shap_values"], float)
        self.assertIsInstance(res["reconstituted_probability"], float)
        self.assertIsInstance(res["additivity_discrepancy"], float)
        self.assertLessEqual(res["additivity_discrepancy"], res["additivity_tolerance"])

        # Check top features
        self.assertEqual(len(res["top_features"]), 5)
        for tf in res["top_features"]:
            self.assertIn("rank", tf)
            self.assertIn("feature", tf)
            self.assertIn(tf["feature"], FEATURE_COLUMNS)
            self.assertIn("feature_value", tf)
            self.assertIn("shap_value", tf)
            self.assertIn("absolute_impact", tf)
            self.assertIn("direction", tf)
            if tf["shap_value"] > 0:
                self.assertEqual(tf["direction"], "INCREASES_CLASS_PROBABILITY")
            elif tf["shap_value"] < 0:
                self.assertEqual(tf["direction"], "DECREASES_CLASS_PROBABILITY")

        # Check original features and signed impacts
        self.assertEqual(len(res["all_feature_impacts"]), 14)
        self.assertEqual(len(res["original_features"]), 14)
        for col in FEATURE_COLUMNS:
            self.assertIn(col, res["all_feature_impacts"])
            self.assertIn(col, res["original_features"])
            self.assertIsInstance(res["all_feature_impacts"][col], float)

        # Explicit non-causation warning must be present
        self.assertIn("causation_warning", res)
        self.assertIn("surrogate model", res["causation_warning"].lower())
        self.assertIn("not represent physical causation", res["causation_warning"].lower())

    def test_explain_prediction_multiclass_explicit_mapping(self):
        """explain_prediction must support explaining specific target classes explicitly."""
        sample_record = self.df_features.iloc[20].to_dict()

        for target_cls in ["High", "Low", "Medium"]:
            res = explain_prediction(sample_record, target_class=target_cls)
            self.assertEqual(res["status"], "AVAILABLE")
            self.assertEqual(res["explained_class"], target_cls)
            self.assertIsInstance(res["prediction_probability"], float)
            self.assertIsInstance(res["base_value"], float)
            self.assertLessEqual(res["additivity_discrepancy"], 0.02)

        # Invalid target class must return explicit error
        err_res = explain_prediction(sample_record, target_class="NonExistentClass")
        self.assertEqual(err_res["status"], "ERROR")
        self.assertIn("Target class 'NonExistentClass' not found", err_res["error"])

    def test_explain_prediction_additivity_and_tolerance_error(self):
        """explain_prediction must return explicit ERROR if additivity check fails, never fabricated values."""
        sample_record = self.df_features.iloc[5].to_dict()

        # Normal tolerance (0.02) passes
        res_ok = explain_prediction(sample_record, tolerance=0.02)
        self.assertEqual(res_ok["status"], "AVAILABLE")

        # Impossibly strict tolerance (1e-9) must fail additivity and return explicit ERROR
        res_fail = explain_prediction(sample_record, tolerance=1e-9)
        self.assertEqual(res_fail["status"], "ERROR")
        self.assertIn("SHAP additivity verification failed", res_fail["error"])
        self.assertEqual(res_fail["top_features"], [])

    def test_explain_prediction_graceful_degradation_missing_artifacts(self):
        """explain_prediction must gracefully degrade to UNAVAILABLE when artifacts are missing."""
        sample_record = self.df_features.iloc[0].to_dict()
        bogus_path = PROJECT_ROOT / "models" / "missing_explainer_xyz.joblib"

        res = explain_prediction(sample_record, explainer_path=bogus_path)
        self.assertEqual(res["status"], "UNAVAILABLE")
        self.assertIn("SHAP explainer artifact unavailable", res["error"])
        self.assertIsNone(res["predicted_class"])
        self.assertEqual(res["top_features"], [])

    def test_service_payload_includes_ml_explanation(self):
        """SoilSentinelService.get_dashboard_payload() must include ml_explanation object."""
        payload = self.service.get_dashboard_payload(date="2024-06")

        self.assertIn("ml_explanation", payload)
        exp = payload["ml_explanation"]
        self.assertIsNotNone(exp)
        self.assertEqual(exp["status"], "AVAILABLE")
        self.assertIn(exp["predicted_class"], ["Low", "Medium", "High"])
        self.assertIsInstance(exp["top_features"], list)
        self.assertGreaterEqual(len(exp["top_features"]), 3)
        self.assertIn("causation_warning", exp)

        # Entire payload must remain 100% JSON-serializable
        serialized = json.dumps(payload)
        self.assertIsInstance(serialized, str)

    def test_global_shap_importance_csv_structure(self):
        """outputs/shap_global_importance.csv must exist, rank 14 features, and contrast with Gini."""
        csv_path = PROJECT_ROOT / "outputs" / "shap_global_importance.csv"
        self.assertTrue(csv_path.exists(), f"Global SHAP CSV missing at {csv_path}")

        df_shap = pd.read_csv(csv_path)
        self.assertEqual(len(df_shap), 14)

        expected_cols = [
            "rank",
            "feature",
            "mean_abs_shap_overall",
            "mean_abs_shap_high",
            "mean_abs_shap_low",
            "mean_abs_shap_medium",
            "rf_gini_importance",
            "indicator_weight_mapping",
        ]
        for col in expected_cols:
            self.assertIn(col, df_shap.columns)

        # Verify sorted by mean_abs_shap_overall descending
        mean_abs_values = df_shap["mean_abs_shap_overall"].tolist()
        self.assertEqual(mean_abs_values, sorted(mean_abs_values, reverse=True))

        # Verify features match FEATURE_COLUMNS
        self.assertEqual(set(df_shap["feature"]), set(FEATURE_COLUMNS))


if __name__ == "__main__":
    unittest.main()
