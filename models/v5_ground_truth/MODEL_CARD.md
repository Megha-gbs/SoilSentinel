# SoilSentinel V5 Ground-Truth Model Suite Model Card

## 1. Model Overview & Purpose
- **Model Suite Version**: `v5_ground_truth`
- **Workstream**: SoilSentinel Member 1 — ML Training and Data Acquisition
- **Primary Objective**: Provide a scientifically defensible, multi-task soil evaluation system distinguishing laboratory-measured analytical truth from proxy engineering surrogates.
- **Key Scientific Commitments**:
  - **No 100% Accuracy Claims**: All reported metrics reflect empirical cross-validations and out-of-region holdouts.
  - **No Conflation of Modeled Maps with Ground Truth**: Digital soil maps (SoilGrids) and rule heuristics are strictly segregated from laboratory-assayed properties.
  - **Zero Git Operations & Full Asset Preservation**: Baseline (v1), regional (v2), global (v3), and current (v4) models, as well as Blessi's 180 Sentinel-2 GeoTIFF rasters, remain intact.

---

## 2. Multi-Task Target & Feature Architecture

```
                            SOILSENTINEL V5 GROUND-TRUTH SUITE
                                             │
      ┌───────────────────┬──────────────────┴──────────────────┬───────────────────┐
      │                   │                                     │                   │
      ▼                   ▼                                     ▼                   ▼
   TASK A              TASK B                                TASK C              TASK D
Measured SOC         Measured EC                           Measured pH        Environmental
 Regression         Salinity Class                        Acidity Class      Stress Surrogate
───────────────     ────────────────                      ───────────────    ────────────────
• Target:           • Target:                             • Target:          • Target:
  organic_carbon_     Saline (EC >= 2.0 dS/m)               Acidic (pH < 5.5)  risk_category
  g_kg (g C / kg)     Non_Saline (EC < 2.0 dS/m)            Non_Acidic         (Low/Med/High)
• Source:           • Source:                             • Source:          • Source:
  WoSIS Lab Assays    WoSIS Lab EC records                  WoSIS Lab pH       Hydrothermal Index
• N = 360 horizons    N = 245 horizons                      N = 360 horizons   N = 60 months
  across 6 cont.      across 4 regions                      across 6 cont.     (2020-2024)
• Status:           • Status:                             • Status:          • Status:
  Analytical Truth    Analytical Truth                      Analytical Truth   Engineering Proxy
```

### Task A — Measured Soil Organic Carbon Regression
- **Target**: `organic_carbon_g_kg` ($g C / kg$) measured via dry combustion / wet oxidation laboratory assays.
- **Data Source**: ISRIC World Soil Information Service (WoSIS) Global Analytical Horizon dataset ($N = 360$ profile horizons across 6 continents).
- **Predictors**: `ph_h2o`, `clay_fraction`, `sand_fraction`, `silt_fraction`, `upper_depth`, `lower_depth`, `latitude`, `longitude`.
- **Target Leakage Safeguard**: `organic_carbon_g_kg` is strictly excluded from input predictors.
- **Validation**: 5-Fold Cross-Validation and Leave-One-Continent-Out (LOCO) CV across Africa, Asia, Europe, North America, Oceania/Australia, and South America.

### Task B — Independent Salinity Classification
- **Target**: `salinity_label` (`Saline` vs. `Non_Saline`).
- **Diagnostic Scientific Standard**:
  - `Saline`: Electrical Conductivity ($EC_{25} \ge 2.0\text{ dS/m}$). Established by United States Salinity Laboratory (USSL Handbook 60), FAO, and ICAR-CSSRI. At this threshold, osmotic potential restricts water uptake in salt-sensitive crops.
  - `Non_Saline`: $EC_{25} < 2.0\text{ dS/m}$.
- **Data Source**: ISRIC WoSIS Laboratory EC dataset ($N = 245$ analytical horizons across Australia, India, Mediterranean Spain/Italy, and North America).
- **Predictors**: `clay_fraction`, `sand_fraction`, `silt_fraction`, `upper_depth`, `lower_depth`, `latitude`, `longitude`.
- **Target Leakage Safeguard**: $EC$ defines the label and is strictly EXCLUDED from input predictors.
- **Validation**: Stratified 5-Fold CV and Leave-One-Region-Out (LORO) CV across the 4 geographic regions.

### Task C — Independent Acidity Classification
- **Target**: `acidity_label` (`Acidic` vs. `Non_Acidic`).
- **Diagnostic Scientific Standard**:
  - `Acidic`: Soil $pH_{H_2O} < 5.5$. Standard USDA-NRCS Soil Survey Manual & FAO threshold for strongly acidic soils causing phytotoxic soluble aluminum ($Al^{3+}$) and manganese release, coupled with phosphorus fixation.
  - `Non_Acidic`: Soil $pH_{H_2O} \ge 5.5$.
- **Data Source**: ISRIC WoSIS Global Analytical Horizon Profiles ($N = 360$ horizons across 6 continents; 148 Acidic, 212 Non-Acidic).
- **Predictors**: `clay_fraction`, `sand_fraction`, `silt_fraction`, `upper_depth`, `lower_depth`, `latitude`, `longitude`, `organic_carbon_g_kg`.
- **Target Leakage Safeguard**: $pH$ defines the label and is strictly EXCLUDED from input predictors.
- **Validation**: Stratified 5-Fold CV and Leave-One-Continent-Out (LOCO) CV across 6 continents.

### Task D — Preserved Environmental-Stress Surrogate (Explicit Proxy Status)
- **Target**: Hydrothermal `risk_category` (`Low`, `Medium`, `High`) derived from SoilSentinel's deterministic multi-factor rule engine.
- **Data Source**: 60-month chronological time series (2020–2024, Punjab, India benchmark coordinates).
- **Predictors**: 14 physical agro-meteorological features from NASA POWER + 3 genuine Copernicus Sentinel-2 optical features from Blessi's 180 GeoTIFFs (`satellite_ndvi`, `satellite_valid_pixel_fraction`, `satellite_scl_vegetation_fraction`).
- **Validation**: Chronological holdout on the 2024 calendar year (Train: 2020–2022, Val: 2023, Test: 2024).
- **CRITICAL PROXY STATUS**: Task D approximates engineering screening heuristics and does NOT represent physical field degradation measurements.

---

## 3. Explainability (SHAP) & Attribution Disclaimers
- **Explainer Architecture**: TreeSHAP (`shap.TreeExplainer`) fitted directly on the final estimators across all 4 tasks.
- **Verification of Additivity**: Local explanations satisfy $\sum_{i=1}^M \phi_i = f(x) - \mathbb{E}[f(x)]$ within $| \Delta | < 10^{-4}$.
- **PROMINENT SCIENTIFIC DISCLAIMER**:
  > **SHAP explains the statistical feature attribution of the trained mathematical algorithm, NOT agronomic or physical causality.**
  > A positive SHAP attribution for clay fraction indicates that the model used high clay content to increase predicted organic carbon or degradation probability; it does NOT constitute physical evidence that clay caused soil degradation.

---

## 4. Out-of-Distribution (OOD) Uncertainty & Safe Inference
- **Layer 1: Mass Conservation Law**: Soil particle size fractions (`sand + silt + clay`) must sum to $100\% \pm 5.0\%$. Violations are rejected before model inference.
- **Layer 2: Empirical Boundary Detector**: An `IsolationForest(contamination=0.05)` is fitted on the multi-dimensional feature space of analytical reference horizons.
- **Abstention Policy**:
  - Queries with Isolation Forest anomaly score $< 0$ or outside the 1st–99th empirical percentiles receive `in_domain: false` with an explicit uncertainty warning advising local laboratory soil testing.
  - Zero-shot predictions across distant continents flag elevated variance due to differing pedological state factors (Hans Jenny's equation: $S = f(cl, o, r, p, t)$).
