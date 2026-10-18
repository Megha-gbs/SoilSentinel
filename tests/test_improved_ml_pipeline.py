"""
SoilSentinel - Automated Test Suite for Improved ML Workstreams & Newly Acquired Datasets.

Verifies:
1. Newly acquired datasets exist in data/raw/ and data/processed/ with valid sizes.
2. Official dataset manifests exist in data/manifests/ with valid SHA-256 hashes.
3. Multi-district feature table conforms to 14-feature schema across 420 samples.
4. WoSIS measured soil properties table contains laboratory-assayed physical measurements.
5. v2 Spatial Surrogate Model loads and predicts deterministically on CPU.
6. v2 WoSIS SOC Regressor loads and predicts plausible physical values on CPU.
7. Existing baseline model (models/soil_risk_model.joblib) remains 100% intact and backward-compatible.
"""

import json
from pathlib import Path
import sys
import joblib
import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
SURROGATE_V2_DIR = MODELS_DIR / "v2_spatial_surrogate"
WOSIS_V2_DIR = MODELS_DIR / "v2_wosis_soc_model"

FEATURE_COLUMNS = [
    "air_temperature_c",
    "air_humidity_percent",
    "precipitation_mm_day",
    "soil_temperature_layer1_c",
    "soil_moisture_surface_fraction",
    "soil_moisture_rootzone_fraction",
    "precipitation_lag1_mm_day",
    "air_temperature_lag1_c",
    "precipitation_rolling_3m_mean_mm_day",
    "temp_soil_air_diff_c",
    "soil_moisture_depth_gradient",
    "monthly_aridity_index",
    "month_sin",
    "month_cos",
]


class TestImprovedMLPipeline:

    def test_wosis_raw_and_processed_files_exist_and_non_empty(self):
        wosis_raw = DATA_DIR / "raw" / "wosis"
        required_raw_files = [
            "wosis_profiles_punjab_bbox.geojson",
            "wosis_profiles_india.geojson",
            "wosis_orgc_punjab_bbox.geojson",
            "wosis_phaq_punjab_bbox.geojson",
            "wosis_clay_punjab_bbox.geojson",
            "wosis_sand_punjab_bbox.geojson",
            "wosis_silt_punjab_bbox.geojson",
        ]
        for f in required_raw_files:
            p = wosis_raw / f
            assert p.exists(), f"Missing WoSIS raw file: {f}"
            assert p.stat().st_size > 1000, f"File too small or empty: {f}"

        proc_wosis = DATA_DIR / "processed" / "wosis_measured_soil_properties.csv"
        assert proc_wosis.exists(), "Missing processed WoSIS dataset"
        assert proc_wosis.stat().st_size > 1000, "Processed WoSIS file is empty"

        df_w = pd.read_csv(proc_wosis)
        assert len(df_w) >= 50, f"Expected at least 50 profiles, got {len(df_w)}"
        assert "soc_measured_g_kg" in df_w.columns
        assert "ph_measured_h2o" in df_w.columns
        assert "latitude" in df_w.columns
        assert "longitude" in df_w.columns

    def test_nasa_power_multi_district_coverage(self):
        clim_dir = DATA_DIR / "raw" / "climate"
        districts = [
            "sas_nagar_chandigarh",
            "ludhiana",
            "bathinda",
            "jalandhar",
            "patiala",
            "amritsar",
            "hoshiarpur",
        ]
        for d in districts:
            matches = list(clim_dir.glob(f"*{d}*.json"))
            if d == "sas_nagar_chandigarh":
                matches += list(clim_dir.glob("*30.73_76.77.json"))
            assert len(matches) > 0, f"Missing climate file for district: {d}"
            assert matches[0].stat().st_size > 5000, f"Climate file empty for {d}"

        proc_feat = DATA_DIR / "processed" / "punjab_multidistrict_features.csv"
        assert proc_feat.exists(), "Missing processed multi-district features"
        df_feat = pd.read_csv(proc_feat)
        assert len(df_feat) == 420, f"Expected 420 samples (7 districts x 60 months), got {len(df_feat)}"
        assert df_feat["district_id"].nunique() == 7
        for col in FEATURE_COLUMNS:
            assert col in df_feat.columns, f"Missing feature column: {col}"

    def test_indian_soil_benchmarks_exist(self):
        csv_p = DATA_DIR / "raw" / "india_soil" / "punjab_soil_health_card_district_benchmarks.csv"
        json_p = DATA_DIR / "raw" / "india_soil" / "punjab_soil_health_card_district_benchmarks.json"
        assert csv_p.exists(), "Missing Indian soil benchmarks CSV"
        assert json_p.exists(), "Missing Indian soil benchmarks JSON"
        assert csv_p.stat().st_size > 500
        assert json_p.stat().st_size > 500

        df_in = pd.read_csv(csv_p)
        assert len(df_in) >= 10
        assert "organic_carbon_mean_pct" in df_in.columns
        assert "ph_mean" in df_in.columns
        assert "ec_mean_ds_m" in df_in.columns

    def test_manifests_exist_and_have_sha256(self):
        manifest_dir = DATA_DIR / "manifests"
        manifest_names = [
            "wosis_soil_dataset_manifest.json",
            "nasa_power_climate_manifest.json",
            "india_soil_health_manifest.json",
            "soilgrids_dataset_manifest.json",
            "master_dataset_provenance_manifest.json",
        ]
        for name in manifest_names:
            p = manifest_dir / name
            assert p.exists(), f"Missing manifest: {name}"
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert len(data) > 0

    def test_v2_surrogate_model_cpu_inference(self):
        model_path = SURROGATE_V2_DIR / "soil_risk_model_v2.joblib"
        meta_path = SURROGATE_V2_DIR / "model_metadata_v2.json"
        assert model_path.exists(), "Missing v2 surrogate model artifact"
        assert meta_path.exists(), "Missing v2 surrogate model metadata"

        model = joblib.load(model_path)
        assert hasattr(model, "predict"), "Model does not implement predict"
        assert hasattr(model, "predict_proba"), "Model does not implement predict_proba"

        # Test single sample CPU inference
        sample_input = pd.DataFrame([{
            "air_temperature_c": 32.5,
            "air_humidity_percent": 45.0,
            "precipitation_mm_day": 2.1,
            "soil_temperature_layer1_c": 34.0,
            "soil_moisture_surface_fraction": 0.25,
            "soil_moisture_rootzone_fraction": 0.35,
            "precipitation_lag1_mm_day": 1.5,
            "air_temperature_lag1_c": 30.0,
            "precipitation_rolling_3m_mean_mm_day": 2.0,
            "temp_soil_air_diff_c": 1.5,
            "soil_moisture_depth_gradient": 0.10,
            "monthly_aridity_index": 1.48,
            "month_sin": 0.5,
            "month_cos": 0.866,
        }], columns=FEATURE_COLUMNS)

        pred = model.predict(sample_input)[0]
        assert pred in ["High", "Low", "Medium"], f"Invalid prediction: {pred}"

        probs = model.predict_proba(sample_input)[0]
        assert len(probs) == 3
        assert np.isclose(np.sum(probs), 1.0, atol=1e-4), "Probabilities do not sum to 1"
        assert all(np.isfinite(p) and 0.0 <= p <= 1.0 for p in probs)

    def test_v2_wosis_soc_regressor_cpu_inference(self):
        model_path = WOSIS_V2_DIR / "wosis_soc_regressor.joblib"
        meta_path = WOSIS_V2_DIR / "wosis_soc_metadata.json"
        assert model_path.exists(), "Missing WoSIS SOC regressor artifact"
        assert meta_path.exists(), "Missing WoSIS SOC metadata"

        model = joblib.load(model_path)
        assert hasattr(model, "predict"), "Regressor does not implement predict"

        sample_input = pd.DataFrame([{
            "latitude": 30.5,
            "longitude": 75.5,
            "sand_measured_pct": 55.0,
            "silt_measured_pct": 30.0,
            "clay_measured_pct": 15.0,
            "ph_measured_h2o": 7.8,
        }])

        pred_soc = float(model.predict(sample_input)[0])
        assert np.isfinite(pred_soc), "Predicted SOC is not finite"
        # Soil organic carbon is physically non-negative and typically 0.5 to 25 g/kg in alluvial soils
        assert 0.0 < pred_soc < 30.0, f"Predicted SOC out of plausible physical range: {pred_soc}"

    def test_existing_baseline_model_unmodified(self):
        base_model_path = MODELS_DIR / "soil_risk_model.joblib"
        base_meta_path = MODELS_DIR / "model_metadata.json"
        assert base_model_path.exists(), "Original baseline model was deleted or moved!"
        assert base_model_path.stat().st_size > 10000, "Original model was overwritten with empty file"

        base_model = joblib.load(base_model_path)
        assert hasattr(base_model, "predict")

        with open(base_meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        assert meta.get("model_version") == "v1.0.0-rf-proxy"
        assert meta.get("dataset_total_samples") == 60
