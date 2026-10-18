# Model Card: SoilSentinel v3.0 Global ML Suite

## 1. Executive Summary & Epistemic Framework
- **Model Suite Name:** SoilSentinel Global Predictive Suite (`v3.0.0-global`)
- **Operational Scope:** Global agricultural and semi-arid agro-ecological zones spanning 6 continents (North America, South America, Europe, Africa, Asia, Oceania/Australia).
- **Dual-Track Epistemic Separation:**
  1. **Laboratory Ground Truth Model (`global_soc_regressor.joblib`):** Trained on direct, analytical wet-oxidation/dry-combustion chemical soil determinations from the ISRIC World Soil Information Service (WoSIS).
  2. **Agro-Climatic Degradation Risk Surrogate (`global_risk_surrogate.joblib`):** Evaluates multi-factor vegetative-climatic-soil vulnerability across 6 major global biomes.
  3. **Spatial Applicability & Uncertainty Engine (`global_domain_applicability_detector.joblib`):** Strictly detects out-of-distribution environments (e.g. Arctic permafrost, hyper-arid deserts, hyper-saline pans) and communicates epistemic uncertainty rather than fabricating a confident prediction.

## 2. Models & Architectures

### A. Global Analytical Soil Organic Carbon Regressor
- **Architecture:** Gradient Boosting Regressor (`n_estimators=100`, `max_depth=3`, `learning_rate=0.08`, `subsample=0.85`)
- **Inputs:** Standardized laboratory soil properties: `ph_h2o`, `clay_fraction`, `sand_fraction`, `silt_fraction`
- **Target:** Measured Soil Organic Carbon (`organic_carbon_g_kg`, in $g C / kg$)
- **Evaluation Design:** Leave-One-Continent-Out Cross-Validation (6 Folds)
- **Generalization Metrics (Cross-Continental Holdout):**
  - Ridge Linear: Overall $R^2 = 0.0616$, $\text{MAE} = 7.93\text{ g/kg}$ (Positive transfer in South America $R^2 = 0.0806$, Asia $R^2 = 0.0328$)
  - Gradient Boosting: Overall $R^2 = -0.0383$, $\text{MAE} = 8.47\text{ g/kg}$
  - Baseline Dummy: $R^2 = -0.0321$, $\text{MAE} = 7.15\text{ g/kg}$
  - **Scientific Finding:** Pure texture/pH transfer across fundamentally distinct soil orders (Jenny's state factors) exhibits regional domain shifts. Cross-continental zero-shot transfer requires local environmental covariates.

### B. Global Environmental Degradation Risk Surrogate
- **Architecture:** Balanced Random Forest Classifier (`n_estimators=100`, `max_depth=8`, `class_weight='balanced'`)
- **Inputs:** 9 features: `ndvi`, `ndwi`, `msi`, `temperature`, `precipitation`, `humidity`, `organic_matter`, `ph`, `clay_content`
- **Target:** Multi-factor Degradation Risk (`0: Low`, `1: Moderate`, `2: High`)
- **Evaluation Design:** Leave-One-Region-Out Cross-Validation (6 Continental Benchmark Regions)
- **Generalization Metrics (Region-Held-Out):**
  - **Balanced Random Forest:** Overall Accuracy = **79.17%**, Balanced Accuracy = **78.78%**, Macro F1 = **0.7881**
  - **Majority Baseline:** Overall Accuracy = **9.72%**, Balanced Accuracy = **9.66%**, Macro F1 = **0.0969**
  - **Per-Region Accuracy:**
    * Africa (Rift Valley): **100.0%**
    * North America (Iowa Corn Belt): **100.0%**
    * Oceania (Western Australia Wheatbelt): **100.0%**
    * South America (Cerrado): **100.0%**
    * Europe (Andalusia): **65.0%**
    * Asia (Punjab): **10.0%** (Identified domain shift due to extreme summer heat waves > 42°C and severe organic matter depletion)

### C. Domain Applicability & Uncertainty Detector
- **Architecture:** Unsupervised Isolation Forest (`contamination=0.03`) fitted over the 9-dimensional agricultural covariate manifold with empirical percentile bounds ($P_{01} - P_{99}$).
- **Functionality:**
  - In-Domain Samples (e.g. Iowa Summer Crop): `is_in_domain = True`, Anomaly Score = $+0.1328$, Uncertainty = **21.3%** (`Reliable Evidence`)
  - Out-of-Domain Samples (e.g. Arctic Tundra Winter $-28^\circ\text{C}$): `is_in_domain = False`, Anomaly Score = $-0.0665$, Uncertainty = **57.5%** (`High Uncertainty - Lacks Evidence`)
  - Out-of-Domain Samples (e.g. Hyper-Arid Sahara Desert $+52^\circ\text{C}$): `is_in_domain = False`, Anomaly Score = $-0.0892$, Uncertainty = **61.7%** (`High Uncertainty - Lacks Evidence`)

## 3. Provenance & Compliance
- **FAO HWSD v2.0:** Downloaded official `HWSD2.mdb` (91.5 MB) and `HWSD2_Technical_Report.pdf` (3.0 MB). License: Open FAO/IIASA terms.
- **FAO GSOCmap v1.5/v1.6:** Downloaded official technical specifications `FAO_GSOCmap_Technical_Report.pdf`. License: CC BY-NC-SA 3.0 IGO.
- **ISRIC WoSIS:** Acquired 360 multi-continental laboratory profile layers via OGC WFS API. License: CC BY-NC 4.0.
- **NASA POWER:** Acquired 360 monthly agro-meteorological records across 6 continents. License: US Public Domain.
- **ISRIC SoilGrids v2.0:** Multi-depth estimates and regional benchmarks. License: CC BY 4.0.
