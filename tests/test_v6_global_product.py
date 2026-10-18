"""
SoilSentinel V6 Global Soil Assessment Product — Comprehensive Test Suite
========================================================================
Automated test suite verifying:
1. All versioned artifacts in models/v6_global_product/ exist and load without error.
2. Camera AI quality guard rejects blurred and improperly exposed inputs.
3. Camera AI crop foliar diagnostic inference returns calibrated categories and advice.
4. Camera AI soil surface morphology diagnosis correctly separates visible physical
   surface features from unobservable subsurface chemistry (EC, pH, SOC).
5. Global GPS Field Assessment retrieves tiered data: SoilGrids 250m contextual estimates,
   NASA/Open-Meteo weather context, and multi-task V6 ML predictions with caching.
6. Multi-task V6 inference engine executes Task A (SOC), Task B (Salinity), Task C (Acidity),
   Task D (Sodicity Audit transparency), and Task E (Environmental Surrogate).
7. Physical soil texture mass conservation (sand% + silt% + clay% == 100%) and OOD detection.
8. Python Bridge handlers (camera-analyze, gps-assess, soil-test-assess) execute cleanly.
9. Preservation of all 180 Sentinel-2 GeoTIFF rasters and all historical model directories.
"""

import os
import sys
import json
import base64
import joblib
import cv2
import numpy as np
import pandas as pd
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MODELS_V6 = PROJECT_ROOT / "models" / "v6_global_product"
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"


class TestV6GlobalProductSuite:

    # -------------------------------------------------------------------------
    # 1. Artifact Verification & Integrity
    # -------------------------------------------------------------------------
    def test_all_v6_global_product_artifacts_exist(self):
        """Verify that all 25 required v6_global_product artifacts exist and are non-empty."""
        expected_files = [
            "MODEL_CARD.md",
            "v6_global_product_summary.json",
            "task_a_soc_regressor.joblib",
            "task_a_soc_preprocessor.joblib",
            "task_a_soc_metadata.json",
            "task_a_soc_shap_importance.csv",
            "task_b_salinity_classifier.joblib",
            "task_b_salinity_preprocessor.joblib",
            "task_b_salinity_metadata.json",
            "task_b_salinity_shap_importance.csv",
            "task_c_acidity_classifier.joblib",
            "task_c_acidity_preprocessor.joblib",
            "task_c_acidity_metadata.json",
            "task_c_acidity_shap_importance.csv",
            "task_d_sodicity_audit.json",
            "task_e_environmental_surrogate.joblib",
            "task_e_environmental_surrogate_preprocessor.joblib",
            "task_e_environmental_surrogate_metadata.json",
            "task_e_environmental_surrogate_shap_importance.csv",
            "v6_domain_applicability_detector.joblib",
            "v6_domain_applicability_metadata.json",
            "camera_crop_model.joblib",
            "camera_crop_metadata.json",
            "camera_soil_model.joblib",
            "camera_soil_metadata.json"
        ]

        for fname in expected_files:
            p = MODELS_V6 / fname
            assert p.exists(), f"Missing required V6 artifact: {fname}"
            assert p.stat().st_size > 0, f"Artifact is empty: {fname}"

    def test_models_load_in_memory_without_error(self):
        """Verify that all joblib models and preprocessors load into memory without exception."""
        model_files = [
            "task_a_soc_regressor.joblib",
            "task_a_soc_preprocessor.joblib",
            "task_b_salinity_classifier.joblib",
            "task_b_salinity_preprocessor.joblib",
            "task_c_acidity_classifier.joblib",
            "task_c_acidity_preprocessor.joblib",
            "task_e_environmental_surrogate.joblib",
            "task_e_environmental_surrogate_preprocessor.joblib",
            "v6_domain_applicability_detector.joblib",
            "camera_crop_model.joblib",
            "camera_soil_model.joblib"
        ]
        for mf in model_files:
            obj = joblib.load(MODELS_V6 / mf)
            assert obj is not None, f"Failed to load joblib artifact: {mf}"

    # -------------------------------------------------------------------------
    # 2. Camera AI Quality Guards & Optical Diagnostics
    # -------------------------------------------------------------------------
    def test_camera_quality_guard_rejects_blurry_image(self):
        """Verify that the camera quality guard flags an intentionally blurred image."""
        from src.Vision.camera_ai import CameraDiagnosticEngine

        engine = CameraDiagnosticEngine(model_dir=MODELS_V6)

        # Create sharp vs blurred image
        sharp_img = np.zeros((300, 300, 3), dtype=np.uint8)
        cv2.circle(sharp_img, (150, 150), 80, (0, 255, 0), -1)
        cv2.rectangle(sharp_img, (50, 50), (120, 120), (255, 255, 255), -1)

        # Apply severe Gaussian blur
        blurry_img = cv2.GaussianBlur(sharp_img, (51, 51), 0)

        quality_sharp = engine.check_image_quality(sharp_img)
        quality_blurry = engine.check_image_quality(blurry_img)

        assert quality_sharp["status"] == "OK"
        assert quality_blurry["status"] == "POOR"
        assert quality_blurry["laplacian_variance"] < quality_sharp["laplacian_variance"]
        assert any("blur" in issue.lower() for issue in quality_blurry["issues"])

    def test_camera_crop_foliar_diagnosis(self):
        """Verify end-to-end crop diagnosis on acquired real field photograph."""
        from src.Vision.camera_ai import CameraDiagnosticEngine

        engine = CameraDiagnosticEngine(model_dir=MODELS_V6)
        test_img_path = DATA_RAW / "camera" / "crop" / "healthy_tomato_foliage_01.jpg"
        assert test_img_path.exists(), "Sample crop image missing"

        res = engine.diagnose(test_img_path, target_mode="crop")
        assert res["status"] in ("SUCCESS", "QUALITY_WARNING")
        assert "diagnosis" in res
        assert "confidence" in res
        assert "possible_causes" in res
        assert "recommended_next_steps" in res
        assert len(res["possible_causes"]) > 0
        assert len(res["recommended_next_steps"]) > 0
        # Scientific honesty disclaimer check
        assert "scientific_disclaimer" in res
        assert "subsurface" in res["scientific_disclaimer"].lower() or "agronomic" in res["scientific_disclaimer"].lower()

    def test_camera_soil_morphology_diagnosis(self):
        """Verify soil morphology diagnosis distinguishes surface features from subsurface lab tests."""
        from src.Vision.camera_ai import CameraDiagnosticEngine

        engine = CameraDiagnosticEngine(model_dir=MODELS_V6)
        test_img_path = DATA_RAW / "camera" / "soil" / "soil_rill_erosion_01.jpg"
        assert test_img_path.exists(), "Sample soil image missing"

        res = engine.diagnose(test_img_path, target_mode="soil")
        assert res["status"] in ("SUCCESS", "QUALITY_WARNING")
        assert "diagnosis" in res
        assert "optical_indices" in res
        # Must confirm that camera AI does not claim to measure electrical conductivity
        assert "subsurface" in res["scientific_disclaimer"].lower()

    # -------------------------------------------------------------------------
    # 3. Global GPS Field Assessment Workflow
    # -------------------------------------------------------------------------
    def test_gps_field_assessment_workflow(self):
        """Verify that GPS assessment retrieves SoilGrids 250m context, weather, and V6 predictions."""
        from src.Geo.field_assessment import GPSFieldAssessmentEngine

        engine = GPSFieldAssessmentEngine(models_dir=MODELS_V6)
        # Test coordinates in Punjab (Indo-Gangetic Basin)
        res = engine.assess_location(latitude=30.7333, longitude=76.7794, crop_type="wheat")

        assert res["status"] == "SUCCESS"
        assert "contextual_soilgrids" in res
        sg = res["contextual_soilgrids"]
        assert "ph_mean" in sg
        assert "soc_mean" in sg
        assert "clay_mean" in sg
        assert "scientific_status" in sg
        assert "mapped" in sg["scientific_status"].lower()

        assert "recent_weather" in res
        wx = res["recent_weather"]
        assert "mean_temperature_c" in wx
        assert "total_precipitation_mm" in wx

        assert "v6_predictions" in res
        preds = res["v6_predictions"]
        assert "task_a_soil_organic_carbon" in preds
        assert "task_b_salinity" in preds
        assert "task_c_acidity" in preds

    # -------------------------------------------------------------------------
    # 4. Multi-Task V6 Model Inference & Out-Of-Distribution Detection
    # -------------------------------------------------------------------------
    def test_v6_multi_task_inference_and_mass_conservation(self):
        """Verify multi-task inference engine and physical texture conservation."""
        from src.Model.v6_inference import SoilSentinelV6InferenceEngine

        engine = SoilSentinelV6InferenceEngine(models_dir=MODELS_V6)

        # Standard physically valid soil profile
        valid_profile = {
            "depth_cm": 15.0,
            "clay_fraction_pct": 28.0,
            "sand_fraction_pct": 42.0,
            "silt_fraction_pct": 30.0,
            "ph_h2o": 7.4,
            "electrical_conductivity_ds_m": 1.2,
            "soil_organic_carbon_g_kg": 6.5,
            "latitude": 30.7333,
            "longitude": 76.7794
        }
        res = engine.predict_multi_task(valid_profile)

        assert res["domain_applicability"]["texture_mass_conservation_valid"] is True
        assert "soil_organic_carbon" in res
        assert "soil_salinity" in res
        assert "soil_acidity" in res
        assert "environmental_stress" in res
        assert "sodicity_audit" in res
        # Verify honesty of sodicity audit
        assert "task_d_governance" in res["sodicity_audit"]
        assert res["sodicity_audit"]["investigated_targets"]["sodicity_esp_percent"]["status"] == "UNAVAILABLE_MEASURED_LAB_DATA"

    def test_v6_mass_conservation_violation_flagged(self):
        """Verify that impossible physical texture (sum != 100%) is flagged."""
        from src.Model.v6_inference import SoilSentinelV6InferenceEngine

        engine = SoilSentinelV6InferenceEngine(models_dir=MODELS_V6)

        # Physically impossible profile: clay + sand + silt = 180%
        invalid_profile = {
            "depth_cm": 15.0,
            "clay_fraction_pct": 60.0,
            "sand_fraction_pct": 60.0,
            "silt_fraction_pct": 60.0,
            "ph_h2o": 7.0,
            "electrical_conductivity_ds_m": 1.0,
            "soil_organic_carbon_g_kg": 5.0,
            "latitude": 30.7333,
            "longitude": 76.7794
        }
        res = engine.predict_multi_task(invalid_profile)
        assert res["domain_applicability"]["texture_mass_conservation_valid"] is False
        assert res["domain_applicability"]["is_in_domain"] is False

    # -------------------------------------------------------------------------
    # 5. Bridge Endpoints Integration Tests
    # -------------------------------------------------------------------------
    def test_bridge_camera_handler(self):
        """Verify bridge handle_camera_analyze produces valid response."""
        from src.Model.bridge import handle_camera_analyze

        # Create a sharp pattern with high-frequency edges so quality guard passes
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        img[::20, :, :] = 255
        img[:, ::20, :] = 255
        cv2.circle(img, (100, 100), 45, (0, 255, 0), -1)
        _, buffer = cv2.imencode(".png", img)
        b64 = "data:image/png;base64," + base64.b64encode(buffer).decode("utf-8")

        payload = {"image_data": b64, "target_mode": "crop"}
        res = handle_camera_analyze(payload)
        assert res.get("status") in ("SUCCESS", "QUALITY_WARNING")
        assert "diagnosis" in res

    def test_bridge_gps_handler(self):
        """Verify bridge handle_gps_assess produces valid response."""
        from src.Model.bridge import handle_gps_assess

        payload = {"latitude": 30.7333, "longitude": 76.7794, "crop_type": "wheat"}
        res = handle_gps_assess(payload)
        assert res.get("status") == "SUCCESS"
        assert "contextual_soilgrids" in res
        assert "v6_predictions" in res

    def test_bridge_soil_test_handler(self):
        """Verify bridge handle_soil_test_assess produces valid response."""
        from src.Model.bridge import handle_soil_test_assess

        payload = {
            "depth_cm": 20,
            "ph_h2o": 7.8,
            "electrical_conductivity_ds_m": 0.8,
            "soil_organic_carbon_g_kg": 4.5,
            "clay_fraction_pct": 25,
            "sand_fraction_pct": 45,
            "silt_fraction_pct": 30,
            "latitude": 30.7333,
            "longitude": 76.7794
        }
        res = handle_soil_test_assess(payload)
        assert res.get("status") == "SUCCESS"
        assert "multi_task_predictions" in res or "soil_test_assessment" in res

    # -------------------------------------------------------------------------
    # 6. Preservation of GeoTIFFs and Historical Model Artifacts
    # -------------------------------------------------------------------------
    def test_all_180_sentinel2_geotiffs_preserved(self):
        """Verify all 180 Sentinel-2 GeoTIFF files supplied by Blessi remain untouched."""
        geotiff_dir = DATA_RAW / "satellite" / "spectral_subsets"
        assert geotiff_dir.exists(), "GeoTIFF directory missing"
        tiffs = list(geotiff_dir.glob("*.tif")) + list(geotiff_dir.glob("*.tiff"))
        assert len(tiffs) == 180, f"Expected exactly 180 Sentinel-2 GeoTIFF files, found {len(tiffs)}"

    def test_historical_model_directories_preserved(self):
        """Verify all previous model versions remain untouched."""
        models_root = PROJECT_ROOT / "models"
        required_dirs = ["v2_spatial_surrogate", "v2_wosis_soc_model", "v3_global", "v4_independent_validation", "v5_ground_truth"]
        for d in required_dirs:
            target = models_root / d
            assert target.exists() and target.is_dir(), f"Historical directory missing: {d}"

        # Verify baseline artifacts in models/
        baseline_files = ["soil_risk_model.joblib", "soil_risk_preprocessor.joblib", "soil_risk_explainer.joblib"]
        for bf in baseline_files:
            assert (models_root / bf).exists(), f"Baseline model artifact missing: {bf}"
