# Model Card: SoilSentinel v2.0 Spatial-Temporal Risk Surrogate Model

## 1. Model Details
- **Model Name:** SoilSentinel Multi-District Spatial-Temporal Soil Degradation Risk Classifier (`soil_risk_model_v2.joblib`)
- **Version:** `2.0.0-rf-multidistrict-surrogate`
- **Architecture:** Balanced Random Forest Classifier (`n_estimators=100`, `max_depth=12`, `min_samples_split=4`, `min_samples_leaf=2`, `class_weight='balanced'`, `random_state=42`)
- **Input Feature Vector:** 9 features: `ndvi`, `ndwi`, `msi`, `temperature`, `precipitation`, `humidity`, `organic_matter`, `ph`, `clay_content`
- **Target Variable:** `risk_class` (3 discrete classes: `0 = Low`, `1 = Moderate`, `2 = High`)
- **Target Nature:** Heuristic surrogate approximating the domain-expert rule-based composite environmental risk index across diverse agro-climatic conditions.
- **Explainability:** TreeSHAP (`soil_risk_explainer_v2.joblib`), verified with additivity discrepancy < 0.02.

## 2. Intended Use & Boundaries
- **Primary Use:** Rapid, CPU-bound screening and multi-factor stress approximation across Punjab agricultural districts.
- **Operational Domain:** Punjab agro-climatic zones (Sub-Mountain Undulating, Central Plain, and South-Western Arid zones).
- **Out-of-Scope Use:** MUST NOT be presented as a physical laboratory replacement or an independently measured biological soil health metric. Does not track live microbial activity or physical compaction directly.

## 3. Training Data & Cross-Validation
- **Source Data:** `data/processed/punjab_multidistrict_features.csv`
- **Sample Size:** $N = 420$ monthly records (7 districts $\times$ 60 months, 2020–2024).
- **Class Support:** Low: 198 (47.1%), Moderate: 178 (42.4%), High: 44 (10.5%).
- **Spatial GroupKFold (7 Folds):**
  - Mean Balanced Accuracy: **92.84%**
  - Mean Macro F1-Score: **0.8712**
- **Spatial Location-Held-Out (Bathinda Arid Zone):**
  - Balanced Accuracy: **90.67%**
  - Recall High Risk: **100.0%**
- **Temporal Holdout (2024 across all 7 districts):**
  - Accuracy: **94.05%**
  - Balanced Accuracy: **91.95%**

## 4. Explainability & Key Drivers
Ranked by Global Mean Absolute SHAP value:
1. `ndvi` (0.3344) — Primary indicator of crop canopy and surface vegetative cover.
2. `msi` (0.3204) — Moisture Stress Index capturing crop drought stress.
3. `precipitation` (0.2312) — Water deficit trigger.
4. `organic_matter` (0.2289) — Soil buffer capacity against thermal and hydraulic stress.
5. `temperature` (0.1706) — Heat stress and evapotranspiration driver.

## 5. Artifacts & Inference
- Model file: `models/v2_spatial_surrogate/soil_risk_model_v2.joblib`
- Preprocessor: `models/v2_spatial_surrogate/soil_risk_preprocessor_v2.joblib`
- Explainer: `models/v2_spatial_surrogate/soil_risk_explainer_v2.joblib`
- Metadata: `models/v2_spatial_surrogate/model_metadata_v2.json`
- Hardware Requirement: Standard CPU (< 1 ms inference per sample).
