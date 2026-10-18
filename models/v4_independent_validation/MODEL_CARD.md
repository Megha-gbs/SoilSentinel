# SoilSentinel V4 Independent Validation & Model Suite Model Card

## 1. Model Overview & Scope
- **Organization / Team**: SoilSentinel ML Workstream (Member 1: ML Training).
- **Architecture Version**: `v4_independent_validation`
- **Scope & Objectives**: Provide a scientifically defensible, globally applicable multi-task machine learning system for soil-health property estimation, independent physical soil degradation classification, and satellite-augmented temporal risk screening.
- **Critical Policy**:
  - **No 100% Accuracy Claims**: Metrics reflect genuine cross-validation and independent geographic holdouts.
  - **No Heuristic / Gridded Map Ground Truth Conflation**: Modeled soil maps (e.g. ISRIC SoilGrids v2.0) and engineering rule outputs are explicitly separated from laboratory-assayed ground truth.
  - **Preservation of Baselines**: Baseline (`v1`), multi-district (`v2`), and global (`v3`) models are fully retained and unmutated.

---

## 2. Multi-Task Target Architecture

### Task A — Laboratory-Measured Soil Organic Carbon Regressor
- **Target**: `organic_carbon_g_kg` ($g C / kg$) measured via dry combustion / wet oxidation laboratory assays.
- **Provenance**: ISRIC World Soil Information Service (WoSIS) Snapshot / Profiles.
- **Dataset Size**: $N = 360$ profile horizons across 6 global continents (Africa, Asia, Europe, North America, Oceania/Australia, South America).
- **Input Feature Schema**:
  - `ph_h2o`: Soil pH in water.
  - `clay_fraction`: Mass fraction of clay particles (< 0.002 mm, %).
  - `sand_fraction`: Mass fraction of sand particles (0.05 - 2.0 mm, %).
  - `silt_fraction`: Mass fraction of silt particles (0.002 - 0.05 mm, %).
  - `upper_depth`: Upper horizon boundary (cm).
  - `lower_depth`: Lower horizon boundary (cm).
  - `latitude`, `longitude`: Spatial coordinates (WGS84).
- **Validation Protocol**:
  - Standard 5-fold cross-validation.
  - Leave-One-Continent-Out (LOCO) cross-validation across 6 continents to evaluate cross-biome generalization.

### Task B — Independent Physical Soil Degradation Classifier
- **Target**: `degradation_label` (`Healthy_Normal`, `Saline_Degradation`, `Acidic_Degradation`).
- **Ground Truth Diagnostic Standards**:
  - **Saline Degradation**: Electrical Conductivity ($EC_{25} > 2.0\text{ dS/m}$), adhering to United States Salinity Laboratory (USSL), FAO, and ICAR-CSSRI diagnostic thresholds for salt accumulation.
  - **Acidic Degradation**: $pH_{H_2O} < 5.5$, reflecting severe acidification with aluminum/manganese phytotoxicity and phosphorus fixation.
  - **Healthy / Normal Soil**: $EC_{25} \le 2.0\text{ dS/m}$ and $5.5 \le pH_{H_2O} \le 8.5$.
- **Provenance**: ISRIC WoSIS analytical laboratory Electrical Conductivity and pH dataset ($N = 245$ analytical records across Australia, India, Mediterranean Spain/Italy, and North America).
- **Leakage Prevention**: Neither Electrical Conductivity nor pH are included as predictors. Input features strictly consist of soil texture (`clay_fraction`, `sand_fraction`, `silt_fraction`), horizon depths (`upper_depth`, `lower_depth`), and coordinates (`latitude`, `longitude`).
- **Validation Protocol**:
  - Stratified 5-fold cross-validation.
  - Leave-One-Region-Out (LORO) cross-validation across the 4 geographical regions.

### Task C — Satellite-Integrated Heuristic Risk Surrogate (Preserved Workstream)
- **Target**: `risk_category` (`Low`, `Medium`, `High`), derived from SoilSentinel's multi-factor hydrothermal heuristic index.
- **Dataset & Imagery Provenance**:
  - Multi-temporal series ($N = 60$ months, 2020-01 to 2024-12) combining NASA POWER agro-meteorology with **Blessi's genuine Copernicus Sentinel-2 10m L2A imagery** (180 GeoTIFFs, EPSG:32643, MGRS `43RFQ`).
- **Satellite Features**:
  - `satellite_ndvi`: Normalized Difference Vegetation Index computed from genuine 10m NIR (B08) and Red (B04) bands.
  - `satellite_valid_pixel_fraction`: Fraction of non-cloud/shadow valid pixels derived from Sentinel-2 Scene Classification Layer (SCL).
  - `satellite_scl_vegetation_fraction`: Fraction of pixels classified by ESA Sen2Cor as vegetation (SCL classes 4 & 5).
- **Validation Protocol**:
  - Chronological split: 2020-01 to 2022-12 (36 months Train), 2023-01 to 2023-12 (12 months Validation), 2024-01 to 2024-12 (12 months Test).
  - Performance compared between Baseline Climate-only and Satellite-Integrated models.

---

## 3. Explainability (SHAP) Protocol & Attribution Disclaimers
- **Explainer Architecture**: TreeSHAP (`shap.TreeExplainer`) fitted directly on the final gradient-boosted and random-forest estimators.
- **Verification of Additivity**: Local explanations satisfy $\sum_{i=1}^M \phi_i = f(x) - \mathbb{E}[f(x)]$ within $| \Delta | < 10^{-4}$.
- **CRITICAL SCIENTIFIC DISCLAIMER**:
  > **SHAP explains the statistical feature attribution of the trained mathematical model, NOT agronomic or physical causality.**
  > A positive SHAP value for clay fraction or temperature indicates that the model used that feature to increase its prediction; it does NOT constitute physical evidence that the feature caused soil degradation.

---

## 4. Out-of-Distribution (OOD) Uncertainty & Safe Inference
- **Domain Applicability Detector**: An `IsolationForest` (contamination 5%) and physical texture conservation validator (`sand + silt + clay == 100% ± 5%`) monitor every inference request.
- **Abstention Policy**:
  - If input texture violates mass conservation or falls outside the 1st–99th empirical percentile bounds of the laboratory training set, the system flags `in_domain: false` and issues an explicit uncertainty notice.
  - Predictions for geographic regions absent from the training set are returned with a warning that cross-continental variance is elevated.
- **Inference Requirements**: Pure Python and CPU-only (`scikit-learn`, `joblib`, `numpy`, `pandas`). Zero GPU or cloud runtime dependencies.
