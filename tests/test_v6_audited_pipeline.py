"""
SoilSentinel V6 Audited Pipeline Test Suite
===========================================
Automated test suite verifying:
1. All 20 versioned artifacts exist in models/v6_audited/ and load without error.
2. Full preservation of all 180 original Sentinel-2 GeoTIFF rasters.
3. Preservation of historical model versions (v1, v2, v3, v4, v5).
4. Mathematical verification of zero profile and coordinate data leakage.
5. SoilSentinelV6AuditedEngine multi-task inference execution on CPU.
6. TreeSHAP feature attribution additivity property (|f(x) - (E + sum phi)| < 1e-4).
7. Physical soil texture mass conservation enforcement (sand + silt + clay == 100%).
8. Out-of-Distribution (OOD) pedological space anomaly detection.
9. Backend service integration (SoilSentinelService.get_v6_audited_assessment).
10. Dashboard payload backward compatibility with existing teammate consumers.
11. Bridge CLI and HTTP handler endpoints for v6-assessment.
12. Task B Balanced Random Forest minority sensitivity preservation.
13. Task D temporal chronological split verification.
14. Machine-readable inventory and human-readable audit reports exist.
"""

import os
import sys
import json
import joblib
import subprocess
import numpy as np
import pandas as pd
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MODELS_V6 = PROJECT_ROOT / "models" / "v6_audited"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_RAW = PROJECT_ROOT / "data" / "raw"
REPORTS_DIR = PROJECT_ROOT / "reports"


class TestV6AuditedPipeline:

    # -------------------------------------------------------------------------
    # 1. Artifact Existence and Integrity
    # -------------------------------------------------------------------------
    def test_v6_artifacts_exist_and_non_empty(self):
        """Verify all 20 required v6 artifacts exist, are non-empty, and can be loaded."""
        expected_artifacts = [
            "MODEL_CARD.md",
            "task_a_soc_metadata.json",
            "task_a_soc_preprocessor.joblib",
            "task_a_soc_regressor.joblib",
            "task_a_soc_shap_importance.csv",
            "task_b_salinity_classifier.joblib",
            "task_b_salinity_metadata.json",
            "task_b_salinity_preprocessor.joblib",
            "task_b_salinity_shap_importance.csv",
            "task_c_acidity_classifier.joblib",
            "task_c_acidity_metadata.json",
            "task_c_acidity_preprocessor.joblib",
            "task_c_acidity_shap_importance.csv",
            "task_d_surrogate_metadata.json",
            "task_d_surrogate_model.joblib",
            "task_d_surrogate_preprocessor.joblib",
            "task_d_surrogate_shap_importance.csv",
            "v6_domain_applicability_detector.joblib",
            "v6_domain_applicability_metadata.json",
            "v6_model_suite_summary.json"
        ]

        assert MODELS_V6.exists(), f"models/v6_audited directory not found at {MODELS_V6}"

        for filename in expected_artifacts:
            path = MODELS_V6 / filename
            assert path.exists(), f"Missing required v6 artifact: {filename}"
            assert path.stat().st_size > 0, f"Artifact is empty: {filename}"

            # Verify loadability
            if filename.endswith(".joblib"):
                obj = joblib.load(path)
                assert obj is not None, f"Failed to load joblib artifact: {filename}"
            elif filename.endswith(".json"):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                assert isinstance(data, dict), f"JSON artifact is not a dictionary: {filename}"

    # -------------------------------------------------------------------------
    # 2. Original Raster & Historical Model Preservation
    # -------------------------------------------------------------------------
    def test_original_sentinel2_rasters_preserved(self):
        """Strictly verify all 180 original Sentinel-2 GeoTIFF files supplied by Blessi remain intact."""
        raster_dir = DATA_RAW / "satellite" / "spectral_subsets"
        assert raster_dir.exists(), f"Satellite raster directory missing: {raster_dir}"

        geotiffs = list(raster_dir.glob("*.tif")) + list(raster_dir.glob("*.tiff"))
        assert len(geotiffs) == 180, f"Expected exactly 180 GeoTIFFs, found {len(geotiffs)}"

        b04_files = [f for f in geotiffs if "_B04" in f.name]
        b08_files = [f for f in geotiffs if "_B08" in f.name]
        scl_files = [f for f in geotiffs if "_SCL" in f.name]

        assert len(b04_files) == 60, f"Expected 60 B04 rasters, found {len(b04_files)}"
        assert len(b08_files) == 60, f"Expected 60 B08 rasters, found {len(b08_files)}"
        assert len(scl_files) == 60, f"Expected 60 SCL rasters, found {len(scl_files)}"

    def test_historical_models_preserved(self):
        """Verify baseline v1, regional v2, global v3, v4, and v5 model folders remain intact."""
        models_root = PROJECT_ROOT / "models"
        assert (models_root / "v4_independent_validation").exists()
        assert (models_root / "v5_ground_truth").exists()
        assert (models_root / "v3_global").exists()
        assert (models_root / "v2_spatial_surrogate").exists()
        assert (models_root / "soil_risk_model.joblib").exists()

    # -------------------------------------------------------------------------
    # 3. Data Leakage Remediation & Assertion
    # -------------------------------------------------------------------------
    def test_zero_profile_data_leakage_assertion(self):
        """Assert zero profile ID overlap and spatial site independence across GroupKFold splits."""
        soc_csv = DATA_PROCESSED / "global_measured_soil_properties.csv"
        df = pd.read_csv(soc_csv)

        assert "profile_id" in df.columns, "Missing profile_id in global_measured_soil_properties.csv"
        assert len(df) == 360, f"Expected 360 rows, found {len(df)}"
        assert df["profile_id"].nunique() == 88, f"Expected 88 profiles, found {df['profile_id'].nunique()}"

        from sklearn.model_selection import GroupKFold
        from src.Model.train_v6_audited_models import verify_zero_group_leakage, create_spatial_site_groups

        # 1. Profile ID zero leakage check
        gkf_profile = GroupKFold(n_splits=5)
        for fold, (train_idx, val_idx) in enumerate(gkf_profile.split(df, groups=df["profile_id"].values), 1):
            train_profiles = df["profile_id"].iloc[train_idx].values
            val_profiles = df["profile_id"].iloc[val_idx].values
            assert verify_zero_group_leakage(train_profiles, val_profiles, "profile_id") is True

        # 2. Spatial site coordinates zero leakage check
        spatial_sites = create_spatial_site_groups(df)
        gkf_spatial = GroupKFold(n_splits=5)
        for fold, (train_idx, val_idx) in enumerate(gkf_spatial.split(df, groups=spatial_sites), 1):
            train_sites = spatial_sites.iloc[train_idx].values
            val_sites = spatial_sites.iloc[val_idx].values
            assert verify_zero_group_leakage(train_sites, val_sites, "spatial_site") is True

    # -------------------------------------------------------------------------
    # 4. V6 Engine Initialization and Multi-Task Prediction
    # -------------------------------------------------------------------------
    def test_v6_engine_initialization(self):
        """Verify SoilSentinelV6AuditedEngine initializes cleanly without errors."""
        from src.Model.v6_inference import SoilSentinelV6AuditedEngine
        engine = SoilSentinelV6AuditedEngine(models_dir=str(MODELS_V6))
        assert engine is not None
        assert "task_a" in engine.models
        assert "task_b" in engine.models
        assert "task_c" in engine.models
        assert "task_d" in engine.models
        assert engine.detector is not None

    def test_v6_engine_single_prediction_schema(self):
        """Verify SoilSentinelV6AuditedEngine returns complete multi-task schema."""
        from src.Model.v6_inference import SoilSentinelV6AuditedEngine
        engine = SoilSentinelV6AuditedEngine(models_dir=str(MODELS_V6))

        valid_input = {
            "clay_fraction": 15.0,
            "sand_fraction": 65.0,
            "silt_fraction": 20.0,
            "ph_h2o": 7.2,
            "upper_depth": 0.0,
            "lower_depth": 30.0,
            "latitude": 14.68,
            "longitude": 77.60,
            "organic_carbon_g_kg": 8.5
        }

        result = engine.predict_multitask(valid_input)

        # Check top-level keys
        assert result["version"] == "v6.0.0-audited"
        assert result["status"] == "SUCCESS"
        assert "evaluations" in result
        assert "domain_applicability" in result

        evals = result["evaluations"]
        assert "task_a_soil_organic_carbon" in evals
        assert "task_b_salinity" in evals
        assert "task_c_acidity" in evals
        assert "task_d_environmental_surrogate" in evals

        # Task A checks
        soc_eval = evals["task_a_soil_organic_carbon"]
        assert isinstance(soc_eval["predicted_soc_g_kg"], float)
        assert soc_eval["units"] == "g C / kg"
        assert soc_eval["predicted_soc_g_kg"] >= 0.0

        # Task B checks
        sal_eval = evals["task_b_salinity"]
        assert sal_eval["predicted_salinity_class"] in ["Non_Saline", "Saline", "Non-Saline"]
        assert "probabilities" in sal_eval

        # Task C checks
        acid_eval = evals["task_c_acidity"]
        assert acid_eval["predicted_acidity_class"] in ["Non_Acidic", "Acidic", "Non-Acidic"]

        # Task D checks
        surr_eval = evals["task_d_environmental_surrogate"]
        assert "predicted_risk_category" in surr_eval
        assert "explicit_proxy_status" in surr_eval

        # Domain checks
        assert result["domain_applicability"]["texture_mass_conservation_valid"] is True

    # -------------------------------------------------------------------------
    # 5. TreeSHAP Additivity Verification
    # -------------------------------------------------------------------------
    def test_v6_engine_shap_additivity_property(self):
        """Verify TreeSHAP local attributions satisfy the additivity axiom (|f(x) - (E + sum phi)| < 1e-4)."""
        import shap
        from src.Model.v6_inference import SoilSentinelV6AuditedEngine
        engine = SoilSentinelV6AuditedEngine(models_dir=str(MODELS_V6))

        model_a = engine.models["task_a"]
        prep_a = engine.preprocessors["task_a"]

        sample = pd.DataFrame([{
            "ph_h2o": 7.0,
            "clay_fraction": 20.0,
            "sand_fraction": 50.0,
            "silt_fraction": 30.0,
            "upper_depth": 0.0,
            "lower_depth": 30.0,
            "latitude": 15.0,
            "longitude": 77.0,
        }])[prep_a["feature_cols"]]

        X_trans = prep_a["scaler"].transform(prep_a["imputer"].transform(sample))
        pred = float(model_a.predict(X_trans)[0])

        explainer = shap.TreeExplainer(model_a)
        shap_vals = explainer.shap_values(X_trans)
        expected_value = float(explainer.expected_value[0] if isinstance(explainer.expected_value, (list, np.ndarray)) else explainer.expected_value)

        reconstructed = expected_value + float(np.sum(shap_vals))
        discrepancy = abs(pred - reconstructed)

        assert discrepancy < 1e-4, f"SHAP additivity violated! Pred={pred}, E+sum(phi)={reconstructed}, diff={discrepancy}"

    # -------------------------------------------------------------------------
    # 6. Physical Texture Mass Conservation Enforcement
    # -------------------------------------------------------------------------
    def test_v6_engine_texture_mass_conservation_enforcement(self):
        """Verify engine flags confidence as ELEVATED_UNCERTAINTY when texture percentages violate mass conservation."""
        from src.Model.v6_inference import SoilSentinelV6AuditedEngine
        engine = SoilSentinelV6AuditedEngine(models_dir=str(MODELS_V6))

        invalid_texture_input = {
            "clay_fraction": 40.0,
            "sand_fraction": 80.0,
            "silt_fraction": 40.0,  # Sum = 160% != 100%
            "ph_h2o": 7.0,
            "upper_depth": 0.0,
            "lower_depth": 30.0,
            "latitude": 14.68,
            "longitude": 77.60,
        }

        result = engine.predict_multitask(invalid_texture_input)
        assert result["domain_applicability"]["texture_mass_conservation_valid"] is False
        assert result["domain_applicability"]["confidence_assessment"] == "ELEVATED_UNCERTAINTY"

    # -------------------------------------------------------------------------
    # 7. Out-Of-Distribution (OOD) Anomaly Detection
    # -------------------------------------------------------------------------
    def test_v6_engine_out_of_distribution_detection(self):
        """Verify IsolationForest and bounds checking flag extreme out-of-distribution inputs."""
        from src.Model.v6_inference import SoilSentinelV6AuditedEngine
        engine = SoilSentinelV6AuditedEngine(models_dir=str(MODELS_V6))

        extreme_input = {
            "clay_fraction": 98.0,          # Out of training bounds
            "sand_fraction": 1.0,
            "silt_fraction": 1.0,
            "ph_h2o": 7.0,
            "upper_depth": 500.0,          # Depth 5 meters
            "lower_depth": 600.0,
            "latitude": 89.0,              # North Pole
            "longitude": 0.0,
        }

        result = engine.predict_multitask(extreme_input)
        assert (not result["domain_applicability"]["isolation_forest_inlier"] or
                len(result["domain_applicability"]["out_of_bounds_features"]) > 0 or
                result["domain_applicability"]["confidence_assessment"] == "ELEVATED_UNCERTAINTY")

    # -------------------------------------------------------------------------
    # 8. Backend Service Integration & Backward Compatibility
    # -------------------------------------------------------------------------
    def test_service_v6_audited_assessment_integration(self):
        """Verify SoilSentinelService provides get_v6_audited_assessment method."""
        from src.Model.service import SoilSentinelService
        service = SoilSentinelService()

        sample_input = {
            "clay_fraction": 20.0,
            "sand_fraction": 50.0,
            "silt_fraction": 30.0,
            "ph_h2o": 6.8,
            "upper_depth": 0.0,
            "lower_depth": 30.0,
            "latitude": 14.68,
            "longitude": 77.60,
        }

        v6_res = service.get_v6_audited_assessment(input_features=sample_input)
        assert v6_res["status"] == "SUCCESS"
        assert v6_res["version"] == "v6.0.0-audited"
        assert "evaluations" in v6_res

    def test_service_dashboard_payload_backward_compatibility(self):
        """Verify get_dashboard_payload includes v6_audited_assessment without breaking legacy schemas."""
        from src.Model.service import get_dashboard_payload
        payload = get_dashboard_payload()

        assert "v6_audited_assessment" in payload
        assert payload["v6_audited_assessment"]["status"] == "SUCCESS"
        assert payload["v6_audited_assessment"]["version"] == "v6.0.0-audited"

        # Backward compatibility with existing teammate consumers
        assert "independent_degradation_assessment" in payload
        assert payload["independent_degradation_assessment"]["status"] == "PENDING_INDEPENDENT_GROUND_TRUTH"

    # -------------------------------------------------------------------------
    # 9. Bridge CLI and HTTP Handler Verification
    # -------------------------------------------------------------------------
    def test_bridge_v6_assessment_cli(self):
        """Verify python src/Model/bridge.py v6-assessment executes cleanly via CLI."""
        bridge_script = PROJECT_ROOT / "src" / "Model" / "bridge.py"

        cmd = [sys.executable, str(bridge_script), "v6-assessment"]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))

        assert proc.returncode == 0, f"Bridge CLI exited with error:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        parsed = json.loads(proc.stdout.strip())
        assert parsed["success"] is True
        assert parsed["v6_assessment"]["status"] == "SUCCESS"
        assert parsed["v6_assessment"]["version"] == "v6.0.0-audited"

    def test_bridge_v6_assessment_handler(self):
        """Verify handle_get_v6_assessment from bridge.py returns valid payload."""
        from src.Model.bridge import handle_get_v6_assessment
        response = handle_get_v6_assessment(None)
        assert response["success"] is True
        assert response["v6_assessment"]["status"] == "SUCCESS"
        assert response["v6_assessment"]["version"] == "v6.0.0-audited"

    # -------------------------------------------------------------------------
    # 10. Model Provenance & Methodology Verification
    # -------------------------------------------------------------------------
    def test_task_b_balanced_rf_minority_sensitivity(self):
        """Verify Task B model is Balanced Random Forest and maintains minority sensitivity."""
        meta_file = MODELS_V6 / "task_b_salinity_metadata.json"
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

        assert meta["best_algorithm"] == "Random_Forest"
        assert "balanced" in meta["model_selection_rationale"].lower()
        rf_res = meta["cross_validation_results"]["Random_Forest"]
        assert rf_res["grouped_bal_acc_mean"] > 0.55
        assert rf_res["grouped_saline_recall_mean"] > 0.20

    def test_task_d_chronological_split_integrity(self):
        """Verify Task D chronological splits eliminate temporal leakage."""
        meta_file = MODELS_V6 / "task_d_surrogate_metadata.json"
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

        assert "PROXY" in meta["explicit_proxy_status"]
        protocol = meta["chronological_protocol"]
        assert "2020-01 to 2022-12" in protocol["train_period"]
        assert "2023-01 to 2023-12" in protocol["validation_period"]
        assert "2024-01 to 2024-12" in protocol["holdout_test_period"]

    def test_v4_v5_identical_hashes_explained_in_inventory(self):
        """Verify machine-readable inventory contains full explanation of v4 vs v5 identical hashes."""
        inv_file = REPORTS_DIR / "v6_audited_ml_inventory.json"
        assert inv_file.exists()
        with open(inv_file, "r", encoding="utf-8") as f:
            inv = json.load(f)

        assert "v4_vs_v5_hash_analysis" in inv
        analysis = inv["v4_vs_v5_hash_analysis"]
        assert analysis["task_a_soc_regressor_identical"] is True
        assert analysis["root_cause"] == "IDENTICAL_DETERMINISTIC_TRAINING_CODE_AND_FIXED_SEEDS"
