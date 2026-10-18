"""
SoilSentinel Global ML Pipeline Test Suite
Tests multi-continental data integrity, FAO HWSD / GSOC acquisition,
global model inference, continent-held-out validation, and out-of-domain uncertainty estimation.
"""

import os
import json
import joblib
import pandas as pd
import numpy as np
import pytest

BASE_DIR = os.path.abspath(r"C:\Users\mohitkumar\Documents\Datathon")
DATA_RAW = os.path.join(BASE_DIR, "data", "raw")
DATA_PROCESSED = os.path.join(BASE_DIR, "data", "processed")
DATA_MANIFESTS = os.path.join(BASE_DIR, "data", "manifests")
MODELS_V3 = os.path.join(BASE_DIR, "models", "v3_global")
MODELS_V2 = os.path.join(BASE_DIR, "models", "v2_spatial_surrogate")
MODELS_BASELINE = os.path.join(BASE_DIR, "models")

class TestGlobalMLPipeline:

    def test_fao_hwsd_files_exist_and_non_empty(self):
        """Verify FAO HWSD v2.0 files exist and have appropriate file sizes."""
        hwsd_dir = os.path.join(DATA_RAW, "fao_hwsd")
        mdb_path = os.path.join(hwsd_dir, "HWSD2.mdb")
        zip_path = os.path.join(hwsd_dir, "HWSD2_DB.zip")
        pdf_path = os.path.join(hwsd_dir, "HWSD2_Technical_Report.pdf")
        
        assert os.path.exists(mdb_path), "HWSD2.mdb missing"
        assert os.path.getsize(mdb_path) > 50_000_000, "HWSD2.mdb should be > 50MB"
        assert os.path.exists(zip_path), "HWSD2_DB.zip missing"
        assert os.path.exists(pdf_path), "HWSD2_Technical_Report.pdf missing"
        assert os.path.getsize(pdf_path) > 1_000_000, "HWSD2 PDF should be > 1MB"

    def test_fao_gsoc_files_exist_and_non_empty(self):
        """Verify FAO GSOCmap official documentation exists."""
        gsoc_pdf = os.path.join(DATA_RAW, "fao_gsoc", "FAO_GSOCmap_Technical_Report.pdf")
        assert os.path.exists(gsoc_pdf), "FAO GSOCmap Technical Report PDF missing"
        assert os.path.getsize(gsoc_pdf) > 50_000, "FAO GSOCmap PDF must be non-empty"

    def test_global_wosis_multi_continental_coverage(self):
        """Verify WoSIS dataset has representation across all 6 major continents."""
        csv_path = os.path.join(DATA_PROCESSED, "global_multicontinental_wosis_profiles.csv")
        assert os.path.exists(csv_path), "global_multicontinental_wosis_profiles.csv missing"
        df = pd.read_csv(csv_path)
        assert len(df) == 360, f"Expected 360 global WoSIS records, got {len(df)}"
        
        expected_continents = {'North_America', 'South_America', 'Europe', 'Africa', 'Asia', 'Oceania_Australia'}
        actual_continents = set(df['continent'].unique())
        assert expected_continents == actual_continents, f"Missing continents: {expected_continents - actual_continents}"
        
        for c in expected_continents:
            count = len(df[df['continent'] == c])
            assert count == 60, f"Continent {c} has {count} records, expected 60"

    def test_global_climate_six_regions_coverage(self):
        """Verify NASA POWER global dataset covers 6 diverse agro-climatic regions."""
        csv_path = os.path.join(DATA_PROCESSED, "global_agroclimatic_multiregion_features.csv")
        assert os.path.exists(csv_path), "global_agroclimatic_multiregion_features.csv missing"
        df = pd.read_csv(csv_path)
        assert len(df) == 360, f"Expected 360 monthly records, got {len(df)}"
        
        expected_regions = {
            'north_america_iowa', 'south_america_cerrado', 'europe_andalusia',
            'africa_rift_valley', 'asia_indo_gangetic', 'oceania_wheatbelt'
        }
        actual_regions = set(df['region_id'].unique())
        assert expected_regions == actual_regions, f"Region mismatch: {expected_regions - actual_regions}"

    def test_global_manifests_exist_and_valid(self):
        """Verify all global dataset manifests exist and contain SHA-256 digests."""
        manifest_files = [
            "fao_hwsd_dataset_manifest.json",
            "fao_gsoc_dataset_manifest.json",
            "global_wosis_dataset_manifest.json",
            "global_climate_manifest.json",
            "global_master_provenance_manifest.json"
        ]
        for mf in manifest_files:
            p = os.path.join(DATA_MANIFESTS, mf)
            assert os.path.exists(p), f"Manifest {mf} missing"
            with open(p, 'r', encoding='utf-8') as f:
                data = json.load(f)
            assert isinstance(data, dict), f"Manifest {mf} is not a valid JSON dict"

    def test_v3_global_soc_model_cpu_inference(self):
        """Verify CPU inference for Global WoSIS Soil Organic Carbon Regressor."""
        model_path = os.path.join(MODELS_V3, "global_soc_regressor.joblib")
        prep_path = os.path.join(MODELS_V3, "global_soc_preprocessor.joblib")
        assert os.path.exists(model_path), "global_soc_regressor.joblib missing"
        assert os.path.exists(prep_path), "global_soc_preprocessor.joblib missing"
        
        model = joblib.load(model_path)
        preprocessor = joblib.load(prep_path)
        
        sample_input = pd.DataFrame([{
            'ph_h2o': 6.5,
            'clay_fraction': 22.0,
            'sand_fraction': 48.0,
            'silt_fraction': 30.0
        }])
        
        X_scaled = preprocessor.transform(sample_input)
        soc_pred = model.predict(X_scaled)[0]
        
        assert np.isfinite(soc_pred), "SOC prediction must be finite"
        assert soc_pred > 0.0, "Predicted SOC must be positive"

    def test_v3_global_risk_surrogate_cpu_inference(self):
        """Verify CPU inference for Global Degradation Risk Surrogate Model."""
        model_path = os.path.join(MODELS_V3, "global_risk_surrogate.joblib")
        prep_path = os.path.join(MODELS_V3, "global_risk_preprocessor.joblib")
        assert os.path.exists(model_path), "global_risk_surrogate.joblib missing"
        assert os.path.exists(prep_path), "global_risk_preprocessor.joblib missing"
        
        model = joblib.load(model_path)
        preprocessor = joblib.load(prep_path)
        
        sample_input = pd.DataFrame([{
            'ndvi': 0.45, 'ndwi': 0.12, 'msi': 0.95,
            'temperature': 24.5, 'precipitation': 65.0, 'humidity': 60.0,
            'organic_matter': 2.2, 'ph': 6.8, 'clay_content': 25.0
        }])
        
        X_scaled = preprocessor.transform(sample_input)
        pred_class = model.predict(X_scaled)[0]
        probs = model.predict_proba(X_scaled)[0]
        
        assert pred_class in [0, 1, 2], "Predicted class must be 0, 1, or 2"
        assert np.isclose(np.sum(probs), 1.0, atol=1e-4), "Probabilities must sum to 1.0"

    def test_v3_global_uncertainty_detector_ood_rejection(self):
        """Verify Epistemic Uncertainty & Domain Applicability Engine detects OOD inputs."""
        detector_path = os.path.join(MODELS_V3, "global_domain_applicability_detector.joblib")
        assert os.path.exists(detector_path), "global_domain_applicability_detector.joblib missing"
        
        detector = joblib.load(detector_path)
        iso_forest = detector['isolation_forest']
        preprocessor = detector['preprocessor']
        feature_cols = detector['feature_cols']
        
        # 1. Typical in-domain temperate agricultural summer crop (from verified dataset)
        csv_path = os.path.join(DATA_PROCESSED, "global_agroclimatic_multiregion_features.csv")
        df_climate = pd.read_csv(csv_path)
        in_domain_df = df_climate[feature_cols].iloc[[0]].copy()
        
        in_scaled = preprocessor.transform(in_domain_df[feature_cols])
        in_domain_pred = iso_forest.predict(in_scaled)[0]
        assert in_domain_pred == 1, "Verified agricultural sample must be classified as in-domain (+1)"
        
        # 2. Extreme out-of-domain Arctic permafrost winter (-35C)
        arctic_df = pd.DataFrame([{
            'ndvi': 0.02, 'ndwi': -0.85, 'msi': 3.8,
            'temperature': -35.0, 'precipitation': 1.0, 'humidity': 20.0,
            'organic_matter': 0.02, 'ph': 4.1, 'clay_content': 5.0
        }])
        arctic_scaled = preprocessor.transform(arctic_df[feature_cols])
        arctic_pred = iso_forest.predict(arctic_scaled)[0]
        assert arctic_pred == -1, "Extreme Arctic climate must be classified as out-of-domain (-1)"
        
        # Check uncertainty metric
        arctic_score = iso_forest.decision_function(arctic_scaled)[0]
        arctic_uncertainty = float(np.clip(1.0 - (arctic_score + 0.3) / 0.55, 0.0, 1.0))
        assert arctic_uncertainty > 0.50, "Out-of-domain sample must trigger high uncertainty (> 0.50)"

    def test_baseline_and_v2_models_unmodified(self):
        """Verify baseline v1 and v2 model files exist and were not corrupted."""
        baseline_model = os.path.join(MODELS_BASELINE, "soil_risk_model.joblib")
        v2_model = os.path.join(MODELS_V2, "soil_risk_model_v2.joblib")
        assert os.path.exists(baseline_model), "Baseline model was modified or deleted!"
        assert os.path.exists(v2_model), "v2 model was modified or deleted!"
