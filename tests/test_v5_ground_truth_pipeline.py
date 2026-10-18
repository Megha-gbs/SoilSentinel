"""
SoilSentinel V5 Ground-Truth Pipeline Test Suite
================================================
Automated test suite verifying:
1. Task A: Measured Soil Organic Carbon (WoSIS) Model Inference & Leakage Prevention
2. Task B: Independent Salinity (EC >= 2.0 dS/m) Classifier & Leakage Prevention
3. Task C: Independent Acidity (pH < 5.5) Classifier & Leakage Prevention
4. Task D: Preserved Environmental-Stress Surrogate & Explicit Proxy Status
5. TreeSHAP Feature Attribution Artifacts across all 4 tasks
6. Out-Of-Distribution (OOD) Domain Applicability & Texture Conservation
7. Full Preservation of Baseline (v1), Regional (v2), Global (v3), and Current (v4) Models
8. Full Preservation of Blessi's 180 Sentinel-2 GeoTIFF files
"""

import os
import json
import joblib
import numpy as np
import pandas as pd
import pytest

BASE_DIR = os.path.abspath(r"C:\Users\mohitkumar\Documents\Datathon")
DATA_RAW = os.path.join(BASE_DIR, "data", "raw")
DATA_PROCESSED = os.path.join(BASE_DIR, "data", "processed")
MODELS_V5 = os.path.join(BASE_DIR, "models", "v5_ground_truth")
MODELS_V4 = os.path.join(BASE_DIR, "models", "v4_independent_validation")
MODELS_V3 = os.path.join(BASE_DIR, "models", "v3_global")
MODELS_V2 = os.path.join(BASE_DIR, "models", "v2_spatial_surrogate")
MODELS_BASELINE = os.path.join(BASE_DIR, "models")


class TestV5GroundTruthPipeline:

    # -------------------------------------------------------------------------
    # Task A: Measured Soil Organic Carbon Regression
    # -------------------------------------------------------------------------
    def test_task_a_soc_cpu_inference(self):
        """Verify Task A SOC Regressor artifacts exist, prevent leakage, and run CPU inference."""
        model_path = os.path.join(MODELS_V5, "task_a_soc_regressor.joblib")
        prep_path = os.path.join(MODELS_V5, "task_a_soc_preprocessor.joblib")
        meta_path = os.path.join(MODELS_V5, "task_a_soc_metadata.json")
        shap_path = os.path.join(MODELS_V5, "task_a_soc_shap_importance.csv")

        assert os.path.exists(model_path), "task_a_soc_regressor.joblib missing"
        assert os.path.exists(prep_path), "task_a_soc_preprocessor.joblib missing"
        assert os.path.exists(meta_path), "task_a_soc_metadata.json missing"
        assert os.path.exists(shap_path), "task_a_soc_shap_importance.csv missing"

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        assert meta["target"] == "organic_carbon_g_kg"
        assert meta["sample_count"] == 360
        assert meta["continent_count"] == 6

        # Zero Target Leakage Check
        assert "organic_carbon_g_kg" not in meta["feature_schema"], "Target leakage: target in features!"

        model = joblib.load(model_path)
        prep = joblib.load(prep_path)

        sample = pd.DataFrame([{
            "ph_h2o": 6.8,
            "clay_fraction": 24.5,
            "sand_fraction": 42.0,
            "silt_fraction": 33.5,
            "upper_depth": 0,
            "lower_depth": 15,
            "latitude": 30.73,
            "longitude": 76.77
        }])

        X_sc = prep["scaler"].transform(prep["imputer"].transform(sample[prep["feature_cols"]]))
        pred = model.predict(X_sc)

        assert isinstance(pred[0], (float, np.floating))
        assert pred[0] > 0.0, f"Predicted SOC should be positive, got {pred[0]}"

    # -------------------------------------------------------------------------
    # Task B: Independent Salinity Classification
    # -------------------------------------------------------------------------
    def test_task_b_salinity_cpu_inference(self):
        """Verify Task B Salinity Classifier artifacts exist, prevent leakage, and run inference."""
        model_path = os.path.join(MODELS_V5, "task_b_salinity_classifier.joblib")
        prep_path = os.path.join(MODELS_V5, "task_b_salinity_preprocessor.joblib")
        meta_path = os.path.join(MODELS_V5, "task_b_salinity_metadata.json")
        shap_path = os.path.join(MODELS_V5, "task_b_salinity_shap_importance.csv")

        assert os.path.exists(model_path), "task_b_salinity_classifier.joblib missing"
        assert os.path.exists(prep_path), "task_b_salinity_preprocessor.joblib missing"
        assert os.path.exists(meta_path), "task_b_salinity_metadata.json missing"
        assert os.path.exists(shap_path), "task_b_salinity_shap_importance.csv missing"

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        assert set(meta["classes"]) == {"Non_Saline", "Saline"}
        assert meta["sample_count"] == 245

        # Zero Target Leakage Check
        assert "electrical_conductivity_ds_m" not in meta["feature_schema"], "Target leakage: EC in features!"
        assert "salinity_label" not in meta["feature_schema"], "Target leakage: label in features!"

        model = joblib.load(model_path)
        prep = joblib.load(prep_path)

        sample = pd.DataFrame([{
            "clay_fraction": 38.0,
            "sand_fraction": 22.0,
            "silt_fraction": 40.0,
            "upper_depth": 0,
            "lower_depth": 20,
            "latitude": -32.65,
            "longitude": 134.58
        }])

        X_sc = prep["scaler"].transform(prep["imputer"].transform(sample[prep["feature_cols"]]))
        pred_label = model.predict(X_sc)[0]
        pred_probs = model.predict_proba(X_sc)[0]

        assert pred_label in {"Non_Saline", "Saline"}
        assert np.isclose(np.sum(pred_probs), 1.0, atol=1e-4)

    # -------------------------------------------------------------------------
    # Task C: Independent Acidity Classification
    # -------------------------------------------------------------------------
    def test_task_c_acidity_cpu_inference(self):
        """Verify Task C Acidity Classifier artifacts exist, prevent leakage, and run inference."""
        model_path = os.path.join(MODELS_V5, "task_c_acidity_classifier.joblib")
        prep_path = os.path.join(MODELS_V5, "task_c_acidity_preprocessor.joblib")
        meta_path = os.path.join(MODELS_V5, "task_c_acidity_metadata.json")
        shap_path = os.path.join(MODELS_V5, "task_c_acidity_shap_importance.csv")

        assert os.path.exists(model_path), "task_c_acidity_classifier.joblib missing"
        assert os.path.exists(prep_path), "task_c_acidity_preprocessor.joblib missing"
        assert os.path.exists(meta_path), "task_c_acidity_metadata.json missing"
        assert os.path.exists(shap_path), "task_c_acidity_shap_importance.csv missing"

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        assert set(meta["classes"]) == {"Non_Acidic", "Acidic"}
        assert meta["sample_count"] == 360
        assert meta["continent_count"] == 6

        # Zero Target Leakage Check
        assert "ph_h2o" not in meta["feature_schema"], "Target leakage: pH in features!"
        assert "acidity_label" not in meta["feature_schema"], "Target leakage: label in features!"

        model = joblib.load(model_path)
        prep = joblib.load(prep_path)

        sample = pd.DataFrame([{
            "clay_fraction": 15.6,
            "sand_fraction": 27.4,
            "silt_fraction": 57.0,
            "upper_depth": 0,
            "lower_depth": 10,
            "latitude": 33.35,
            "longitude": -117.24,
            "organic_carbon_g_kg": 9.6
        }])

        X_sc = prep["scaler"].transform(prep["imputer"].transform(sample[prep["feature_cols"]]))
        pred_label = model.predict(X_sc)[0]
        pred_probs = model.predict_proba(X_sc)[0]

        assert pred_label in {"Non_Acidic", "Acidic"}
        assert np.isclose(np.sum(pred_probs), 1.0, atol=1e-4)

    # -------------------------------------------------------------------------
    # Task D: Preserved Environmental-Stress Surrogate & Proxy Status
    # -------------------------------------------------------------------------
    def test_task_d_surrogate_cpu_inference_with_satellite(self):
        """Verify Task D Surrogate runs inference and documents explicit proxy status."""
        model_path = os.path.join(MODELS_V5, "task_d_surrogate_model.joblib")
        prep_path = os.path.join(MODELS_V5, "task_d_surrogate_preprocessor.joblib")
        meta_path = os.path.join(MODELS_V5, "task_d_surrogate_metadata.json")
        shap_path = os.path.join(MODELS_V5, "task_d_surrogate_shap_importance.csv")

        assert os.path.exists(model_path), "task_d_surrogate_model.joblib missing"
        assert os.path.exists(prep_path), "task_d_surrogate_preprocessor.joblib missing"
        assert os.path.exists(meta_path), "task_d_surrogate_metadata.json missing"
        assert os.path.exists(shap_path), "task_d_surrogate_shap_importance.csv missing"

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        assert "proxy_label_disclaimer" in meta
        assert "DOES NOT constitute physical field degradation" in meta["proxy_label_disclaimer"]

        model = joblib.load(model_path)
        prep = joblib.load(prep_path)

        sample = pd.DataFrame([{
            "air_temperature_c": 28.5,
            "air_humidity_percent": 65.0,
            "precipitation_mm_day": 2.5,
            "soil_temperature_layer1_c": 29.0,
            "soil_moisture_surface_fraction": 0.35,
            "soil_moisture_rootzone_fraction": 0.40,
            "precipitation_lag1_mm_day": 1.2,
            "air_temperature_lag1_c": 27.8,
            "precipitation_rolling_3m_mean_mm_day": 3.1,
            "temp_soil_air_diff_c": 0.5,
            "soil_moisture_depth_gradient": 0.05,
            "monthly_aridity_index": 0.85,
            "month_sin": 0.866,
            "month_cos": -0.5,
            "satellite_ndvi": 0.58,
            "satellite_valid_pixel_fraction": 1.0,
            "satellite_scl_vegetation_fraction": 0.62
        }])

        X_sc = prep["scaler"].transform(prep["imputer"].transform(sample[prep["integrated_features"]]))
        pred_label = model.predict(X_sc)[0]
        assert pred_label in {"Low", "Medium", "High"}

    # -------------------------------------------------------------------------
    # TreeSHAP Feature Attribution across all 4 tasks
    # -------------------------------------------------------------------------
    def test_shap_importance_artifacts_across_all_tasks(self):
        """Verify SHAP importance CSV files exist and have non-negative importances."""
        for task, fname in [
            ("Task A", "task_a_soc_shap_importance.csv"),
            ("Task B", "task_b_salinity_shap_importance.csv"),
            ("Task C", "task_c_acidity_shap_importance.csv"),
            ("Task D", "task_d_surrogate_shap_importance.csv")
        ]:
            p = os.path.join(MODELS_V5, fname)
            assert os.path.exists(p), f"{task} SHAP file {fname} missing"
            df = pd.read_csv(p)
            assert len(df) > 0, f"{task} SHAP file is empty"
            assert "feature" in df.columns and "mean_abs_shap" in df.columns
            assert (df["mean_abs_shap"] >= 0).all(), f"{task} has negative SHAP values"

    # -------------------------------------------------------------------------
    # Domain Applicability & Out-Of-Distribution Uncertainty
    # -------------------------------------------------------------------------
    def test_v5_domain_applicability_and_texture_conservation(self):
        """Verify IsolationForest and boundary detector flag OOD inputs."""
        iso_path = os.path.join(MODELS_V5, "v5_domain_applicability_detector.joblib")
        meta_path = os.path.join(MODELS_V5, "v5_domain_applicability_metadata.json")

        assert os.path.exists(iso_path), "v5_domain_applicability_detector.joblib missing"
        assert os.path.exists(meta_path), "v5_domain_applicability_metadata.json missing"

        iso = joblib.load(iso_path)
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        # 1. Normal in-domain sample
        normal_sample = pd.DataFrame([{
            "clay_fraction": 25.0,
            "sand_fraction": 45.0,
            "silt_fraction": 30.0,
            "upper_depth": 0,
            "lower_depth": 20,
            "latitude": 28.0,
            "longitude": 76.0
        }])[meta["features"]].values
        normal_score = iso.predict(normal_sample)[0]
        assert normal_score == 1, "Normal sample should be in-domain (1)"

        # 2. Extreme anomalous sample (out of distribution)
        extreme_sample = pd.DataFrame([{
            "clay_fraction": 99.0,
            "sand_fraction": 0.1,
            "silt_fraction": 0.1,
            "upper_depth": 500,
            "lower_depth": 900,
            "latitude": -89.0,
            "longitude": -179.0
        }])[meta["features"]].values
        extreme_score = iso.predict(extreme_sample)[0]
        assert extreme_score == -1, "Extreme sample should be flagged as anomaly (-1)"

    # -------------------------------------------------------------------------
    # Full Preservation of All Prior Versions
    # -------------------------------------------------------------------------
    def test_all_prior_models_preserved(self):
        """Verify Baseline v1, V2 spatial, V3 global, and V4 models are all intact."""
        assert os.path.exists(os.path.join(MODELS_BASELINE, "soil_risk_model.joblib")), "Baseline v1 model missing"
        assert os.path.exists(os.path.join(MODELS_BASELINE, "soil_risk_preprocessor.joblib")), "Baseline preprocessor missing"
        assert os.path.exists(os.path.join(MODELS_V2, "soil_risk_model_v2.joblib")), "V2 model missing"
        assert os.path.exists(os.path.join(MODELS_V3, "global_soc_regressor.joblib")), "V3 global SOC model missing"
        assert os.path.exists(os.path.join(MODELS_V3, "global_risk_surrogate.joblib")), "V3 global risk model missing"
        assert os.path.exists(os.path.join(MODELS_V4, "task_a_soc_regressor.joblib")), "V4 task A model missing"
        assert os.path.exists(os.path.join(MODELS_V4, "task_b_degradation_classifier.joblib")), "V4 task B model missing"
        assert os.path.exists(os.path.join(MODELS_V4, "task_c_satellite_surrogate.joblib")), "V4 task C model missing"

    # -------------------------------------------------------------------------
    # Blessi Satellite Data Preservation
    # -------------------------------------------------------------------------
    def test_blessi_satellite_data_preservation(self):
        """Verify all 180 Sentinel-2 GeoTIFF rasters from Blessi are intact."""
        sat_dir = os.path.join(DATA_RAW, "satellite", "spectral_subsets")
        assert os.path.exists(sat_dir), "Blessi satellite raster directory missing"
        tifs = [f for f in os.listdir(sat_dir) if f.endswith(".tif")]
        assert len(tifs) == 180, f"Expected 180 satellite GeoTIFFs, found {len(tifs)}"
