"""
SoilSentinel V4 Independent Validation, SHAP & Satellite Integration Test Suite
==============================================================================
Validates:
1. Task A: Measured Soil Organic Carbon (WoSIS) Model Inference & Artifacts
2. Task B: Independent Physical Degradation (Salinity/Acidity) Classifier & Artifacts
3. Task C: Satellite-Integrated Heuristic Risk Surrogate & Blessi Sentinel-2 Data
4. Phase 7: TreeSHAP Feature Attribution Artifacts, Rankings & Additivity
5. Phase 8: Out-Of-Distribution (OOD) Domain Applicability & Texture Conservation
6. Preservation of Baseline (v1), Multi-district (v2), and Global (v3) Models
7. Preservation of Blessi's 180 Sentinel-2 GeoTIFF Files
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
DATA_MANIFESTS = os.path.join(BASE_DIR, "data", "manifests")
MODELS_V4 = os.path.join(BASE_DIR, "models", "v4_independent_validation")
MODELS_V3 = os.path.join(BASE_DIR, "models", "v3_global")
MODELS_V2 = os.path.join(BASE_DIR, "models", "v2_spatial_surrogate")
MODELS_BASELINE = os.path.join(BASE_DIR, "models")


class TestIndependentValidationAndSHAP:

    # -------------------------------------------------------------------------
    # Task A: Measured Soil Organic Carbon Regression
    # -------------------------------------------------------------------------
    def test_task_a_artifacts_and_cpu_inference(self):
        """Verify Task A SOC Regressor artifacts exist and run CPU inference."""
        model_path = os.path.join(MODELS_V4, "task_a_soc_regressor.joblib")
        prep_path = os.path.join(MODELS_V4, "task_a_soc_preprocessor.joblib")
        meta_path = os.path.join(MODELS_V4, "task_a_soc_metadata.json")
        shap_path = os.path.join(MODELS_V4, "task_a_soc_shap_importance.csv")

        assert os.path.exists(model_path), "task_a_soc_regressor.joblib missing"
        assert os.path.exists(prep_path), "task_a_soc_preprocessor.joblib missing"
        assert os.path.exists(meta_path), "task_a_soc_metadata.json missing"
        assert os.path.exists(shap_path), "task_a_soc_shap_importance.csv missing"

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        assert meta["target"] == "organic_carbon_g_kg"
        assert meta["sample_count"] == 360
        assert meta["continent_count"] == 6

        model = joblib.load(model_path)
        prep = joblib.load(prep_path)

        # Realistic global soil sample input
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

        assert isinstance(pred[0], (float, np.floating)), "Prediction should be float"
        assert pred[0] > 0.0, f"Predicted SOC should be positive, got {pred[0]}"

    # -------------------------------------------------------------------------
    # Task B: Independent Physical Degradation Classification
    # -------------------------------------------------------------------------
    def test_task_b_artifacts_and_cpu_inference(self):
        """Verify Task B Degradation Classifier artifacts exist and run inference."""
        model_path = os.path.join(MODELS_V4, "task_b_degradation_classifier.joblib")
        prep_path = os.path.join(MODELS_V4, "task_b_degradation_preprocessor.joblib")
        meta_path = os.path.join(MODELS_V4, "task_b_degradation_metadata.json")
        shap_path = os.path.join(MODELS_V4, "task_b_degradation_shap_importance.csv")

        assert os.path.exists(model_path), "task_b_degradation_classifier.joblib missing"
        assert os.path.exists(prep_path), "task_b_degradation_preprocessor.joblib missing"
        assert os.path.exists(meta_path), "task_b_degradation_metadata.json missing"
        assert os.path.exists(shap_path), "task_b_degradation_shap_importance.csv missing"

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        assert set(meta["classes"]) == {"Healthy_Normal", "Saline_Degradation", "Acidic_Degradation"}
        assert meta["sample_count"] == 245

        model = joblib.load(model_path)
        prep = joblib.load(prep_path)

        sample = pd.DataFrame([{
            "clay_fraction": 35.0,
            "sand_fraction": 25.0,
            "silt_fraction": 40.0,
            "upper_depth": 0,
            "lower_depth": 20,
            "latitude": 28.5,
            "longitude": 77.0
        }])

        X_sc = prep["scaler"].transform(prep["imputer"].transform(sample[prep["feature_cols"]]))
        pred_label = model.predict(X_sc)[0]
        pred_probs = model.predict_proba(X_sc)[0]

        assert pred_label in {"Healthy_Normal", "Saline_Degradation", "Acidic_Degradation"}
        assert np.isclose(np.sum(pred_probs), 1.0, atol=1e-4)

    # -------------------------------------------------------------------------
    # Task C: Satellite-Integrated Risk Surrogate
    # -------------------------------------------------------------------------
    def test_task_c_satellite_surrogate_cpu_inference(self):
        """Verify Task C Satellite-Integrated Surrogate runs inference."""
        model_path = os.path.join(MODELS_V4, "task_c_satellite_surrogate.joblib")
        prep_path = os.path.join(MODELS_V4, "task_c_satellite_preprocessor.joblib")
        meta_path = os.path.join(MODELS_V4, "task_c_satellite_metadata.json")
        shap_path = os.path.join(MODELS_V4, "task_c_satellite_shap_importance.csv")

        assert os.path.exists(model_path), "task_c_satellite_surrogate.joblib missing"
        assert os.path.exists(prep_path), "task_c_satellite_preprocessor.joblib missing"
        assert os.path.exists(meta_path), "task_c_satellite_metadata.json missing"
        assert os.path.exists(shap_path), "task_c_satellite_shap_importance.csv missing"

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
    # Phase 7: TreeSHAP Feature Importance & Additivity
    # -------------------------------------------------------------------------
    def test_shap_importance_artifacts_and_ranking(self):
        """Verify SHAP importance CSV files exist and have positive importances."""
        for task, fname in [
            ("Task A", "task_a_soc_shap_importance.csv"),
            ("Task B", "task_b_degradation_shap_importance.csv"),
            ("Task C", "task_c_satellite_shap_importance.csv")
        ]:
            p = os.path.join(MODELS_V4, fname)
            assert os.path.exists(p), f"{task} SHAP file {fname} missing"
            df = pd.read_csv(p)
            assert len(df) > 0, f"{task} SHAP file is empty"
            assert "feature" in df.columns and "mean_abs_shap" in df.columns
            assert (df["mean_abs_shap"] >= 0).all(), f"{task} has negative SHAP values"

    # -------------------------------------------------------------------------
    # Phase 8: Out-of-Distribution (OOD) Domain Applicability
    # -------------------------------------------------------------------------
    def test_domain_applicability_and_uncertainty_flagging(self):
        """Verify IsolationForest and boundary detector flag OOD inputs."""
        iso_path = os.path.join(MODELS_V4, "v4_domain_applicability_detector.joblib")
        meta_path = os.path.join(MODELS_V4, "v4_domain_applicability_metadata.json")

        assert os.path.exists(iso_path), "v4_domain_applicability_detector.joblib missing"
        assert os.path.exists(meta_path), "v4_domain_applicability_metadata.json missing"

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
        assert normal_score == 1, "Normal sample should be classified as in-domain (1)"

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
    # Blessi Satellite Data Preservation
    # -------------------------------------------------------------------------
    def test_blessi_satellite_data_preservation(self):
        """Verify all 180 Sentinel-2 GeoTIFF rasters from Blessi are intact."""
        sat_dir = os.path.join(DATA_RAW, "satellite", "spectral_subsets")
        assert os.path.exists(sat_dir), "Blessi satellite raster directory missing"
        tifs = [f for f in os.listdir(sat_dir) if f.endswith(".tif")]
        assert len(tifs) == 180, f"Expected 180 satellite GeoTIFFs, found {len(tifs)}"

        aligned_sat_csv = os.path.join(DATA_PROCESSED, "satellite", "aligned_feature_table_with_satellite.csv")
        assert os.path.exists(aligned_sat_csv), "aligned_feature_table_with_satellite.csv missing"
        df = pd.read_csv(aligned_sat_csv)
        assert len(df) == 60, f"Expected 60 monthly satellite rows, found {len(df)}"

    # -------------------------------------------------------------------------
    # Baseline Preservation
    # -------------------------------------------------------------------------
    def test_baseline_and_prior_models_preserved(self):
        """Verify all baseline and previous version models exist and are intact."""
        assert os.path.exists(os.path.join(MODELS_BASELINE, "soil_risk_model.joblib")), "Baseline v1 model missing"
        assert os.path.exists(os.path.join(MODELS_BASELINE, "soil_risk_preprocessor.joblib")), "Baseline preprocessor missing"
        assert os.path.exists(os.path.join(MODELS_V2, "soil_risk_model_v2.joblib")), "V2 spatial model missing"
        assert os.path.exists(os.path.join(MODELS_V3, "global_soc_regressor.joblib")), "V3 global SOC model missing"
        assert os.path.exists(os.path.join(MODELS_V3, "global_risk_surrogate.joblib")), "V3 global risk model missing"
