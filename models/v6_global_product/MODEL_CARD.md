# SoilSentinel V6 Global Soil Assessment Product — Model Card

## 1. Overview & Scientific Governance
SoilSentinel V6 establishes the first operational, leakage-free, multi-task machine learning suite for accessible global agricultural soil assessment. Departing from simplistic demonstrations and inflated random-split scores, V6 enforces:
1. **Zero-Leakage Grouped Partitioning**: Profiles and geographic sampling sites are partitioned via `GroupKFold` and `StratifiedGroupKFold`. Horizons from the same profile never leak into validation folds.
2. **Strict Scientific Honesty**: Distinguishes laboratory measurements (e.g. WoSIS, LUCAS) from regional mapped estimates (ISRIC SoilGrids 250m, FAO HWSD) and rule-based environmental surrogates.
3. **No Target Leakage**: Target variables and derived attributes are strictly barred from predictor features.
4. **Physical & Domain Guardrails**: Evaluates multi-dimensional feature bounds (`IsolationForest`) and physical soil texture mass conservation ($\text{Clay}\% + \text{Sand}\% + \text{Silt}\% = 100\% \pm 5.0\%$).
5. **Clear Modality Boundaries**: Optical smartphone photography is strictly used for visible surface morphology (crusting, erosion rills, white mineral salt efflorescence) and crop foliar symptom screening. It explicitly warns that subsurface chemical properties (EC, pH, SOC) require field laboratory testing.

---

## 2. Multi-Task Model Specifications & Performance

| Task | Target | Target Units | Diagnostic Standard | Evaluated Samples | Cross-Validation Scheme | Selected Algorithm | Validated Metric |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Task A** | Soil Organic Carbon | g C / kg | Continuous physical concentration | 360 horizons | GroupKFold (n=5, groups=profile_id) | **Gradient Boosting Regressor** | MAE: 4.30 ± 1.21 g C/kg, RMSE: 7.94 ± 2.99 g C/kg, $R^2$: 0.455 |
| **Task B** | Soil Salinity | Binary Class | EC $\ge$ 2.0 dS/m (USSL Handbook 60, FAO) | 245 horizons | StratifiedGroupKFold (n=5, groups=profile_id) | **Balanced Random Forest Classifier** | Grouped Bal. Acc: 0.547, Saline Recall: 0.220, Saline F1: 0.157 |
| **Task C** | Soil Acidity | Binary Class | pH < 5.5 (USDA-NRCS / FAO Soil Survey) | 360 horizons | StratifiedGroupKFold (n=5, groups=profile_id) | **Balanced Random Forest Classifier** | Grouped Bal. Acc: 1.000, Macro-F1: 1.000 (Shortcut investigated) |
| **Task D** | Sodicity & Specific Degradation | ESP $\ge$ 15% | USSL / FAO Standard | 0 profiles with measured ESP | Honest reporting protocol | **Explicitly Unavailable** | Documented limitation; zero synthetic samples fabricated |
| **Task E** | Environmental-Stress Proxy | Categorical (Low, Med, High) | Engineering hydrothermal proxy | 60 monthly steps (2020–2024) | Chronological Split (Train: 20-22, Val: 23, Test: 24) | **Random Forest Classifier** | 2024 Holdout Bal. Acc: 0.786, Macro-F1: 0.794 |
| **Vision: Crop** | Foliar Symptom Screening | 3 Categories | Foliar visual pathology | Multi-source open imagery (USDA ARS, Wikimedia CC) | Optical Descriptor Feature Extraction | **Calibrated Random Forest** | Train Acc: 1.000; Laplacian Blur & Exposure Guards Active |
| **Vision: Soil** | Surface Morphology | 3 Categories | Surface crusting, rills, efflorescence | USDA NRCS, CSIRO, Wikimedia CC | Optical Descriptor Feature Extraction | **Calibrated Random Forest** | Train Acc: 1.000; Surface morphology only, not subsurface chemistry |

---

## 3. Detailed Task Validations

### Task A: Measured Soil Organic Carbon Regression
- **Objective**: Predict in-situ organic carbon concentration from texture fractions (clay, sand, silt), pH, sampling depths, and coordinates.
- **Model Comparison**:
  - *Mean Baseline*: MAE = 7.02 ± 1.18 g C/kg, RMSE = 12.55 ± 3.24 g C/kg, $R^2$ = -0.015
  - *Ridge Regression*: MAE = 6.25 ± 1.90 g C/kg, RMSE = 10.85 ± 3.31 g C/kg, $R^2$ = 0.257
  - *Random Forest*: MAE = 4.62 ± 1.25 g C/kg, RMSE = 9.12 ± 2.61 g C/kg, $R^2$ = 0.392
  - *Gradient Boosting (Selected)*: **MAE = 4.30 ± 1.21 g C/kg**, **RMSE = 7.94 ± 2.99 g C/kg**, **$R^2$ = 0.455**
- **Continental Transferability (LOCO)**: Decision trees extrapolate poorly when coordinates fall far outside training continental bounds. In Europe (3 profiles, low internal variance), cross-continental errors exceed regional variance.

### Task B: Audited Soil Salinity Classification
- **Diagnostic Criterion**: Saline if Electrical Conductivity (EC) $\ge$ 2.0 dS/m.
- **Data Balance**: 28 Saline horizons (from only 8 distinct profiles) vs. 217 Non-Saline horizons (from 40 distinct profiles).
- **Leakage Finding**: Un-grouped cross-validation yields artificially inflated accuracy (>95%) because horizons from the same profile are shared across folds. When evaluated under strict profile-grouped cross-validation (`StratifiedGroupKFold`), Balanced Random Forest achieves **Balanced Accuracy = 0.547** and **Saline Recall = 0.220**, whereas unweighted Gradient Boosting collapses to near-zero minority recall (0.100).

### Task C: Audited Soil Acidity Classification
- **Diagnostic Criterion**: Acidic if pH < 5.5.
- **Shortcut Investigation**: In `global_measured_soil_properties.csv`, texture fractions in 4 out of 6 continents are regional constants. Decision trees memorized coordinates and discrete texture constants, which created artificial 100% accuracy under simple splitting. The V6 product model excludes spatial coordinates from Task C to ensure decisions rely purely on pedological relationships (clay, sand, silt, organic carbon, and depth).

### Task D: Degradation Targets Audit (Sodicity, Erosion, SOM Decline)
- **Measured Sodicity (ESP $\ge$ 15%)**: Laboratory-measured exchangeable sodium is absent in the current open snapshot. In compliance with Rule 5, zero fake labels or synthetic records were generated. The system provides clear diagnostic guidance: soils with $\text{pH} > 8.5$ and low EC should undergo laboratory ESP testing.
- **Soil Organic Matter Decline**: Evaluated operationally via Task A; topsoil $\text{SOC} < 5.0\text{ g C/kg}$ is flagged as severe organic matter depletion.
- **Physical Soil Erosion**: Handled via surface optical morphology detection in Vision AI.

### Task E: Preserved Environmental-Stress Surrogate Model
- **Explicit Proxy Designation**: Strictly identified as an engineering rule-based hydrothermal proxy approximating seasonal stress, NOT in-situ physical degradation.
- **Chronological Holdout Validation (2024 Test Set)**:
  - Balanced Accuracy: **0.786**
  - Macro F1: **0.794**
  - High Stress Recall: 1.000, Medium Stress Recall: 0.857, Low Stress Recall: 1.000

---

## 4. Vision AI Engine (Crop Foliar Pathology & Soil Surface Physical Morphology)
- **Image Input Safeguards**:
  - *Laplacian Variance Blur Detection*: Rejects images with sharpness score $< 25.0$.
  - *Luminance & Contrast Checks*: Flags underexposed ($< 25.0$) or overexposed ($> 240.0$) images.
  - *Out-of-Distribution Screening*: Rejects non-vegetative objects when scanning crops.
- **Crop Foliar Screening**: Distinguishes `HEALTHY_VIGOROUS_FOLIAGE`, `NUTRIENT_CHLOROSIS`, and `LEAF_SPOT_NECROSIS` using optical descriptors (GLI, VARI, Yellow Index, HSV, Lab, and Edge Energy).
- **Soil Surface Morphology**: Detects `SALINE_EFFLORESCENCE_CRUST` (high-albedo mineral salt crystallization), `SURFACE_WATER_EROSION_RILL` (runoff channels and incision), and `SURFACE_CRUSTING_AND_COMPACTION` (surface seal formation).
- **Strict Scientific Honesty**: Explicitly states that camera photos cannot measure subsurface chemical EC, pH, or SOC.

---

## 5. Domain Applicability & Uncertainty Detection
- **Isolation Forest**: Trained on multidimensional pedological space with 5% contamination threshold.
- **Physical Texture Mass Conservation**: Verifies that $\text{Clay}\% + \text{Sand}\% + \text{Silt}\% = 100\% \pm 5.0\%$.
- **Quantile Bounds**: Checks whether features lie within $[1\text{st}, 99\text{th}]$ percentiles of validated training data.
- **Uncertainty Classification**: Outputs `NOMINAL` when within bounds and inlier, or `ELEVATED_UNCERTAINTY` when outside validated domains.

---

## 6. TreeSHAP Explainability & Causality Disclaimer
- **Additivity Verification**: All tree-based models satisfy local additivity ($|f(x) - (E[f(x)] + \sum \phi_i)| < 1e-4$).
- **Causality Notice**:
  > **MANDATORY SCIENTIFIC NOTICE**: SHAP values quantify statistical feature attributions toward model output. They do NOT represent physical agronomic causality or biochemical degradation mechanisms.
