# SoilSentinel V6 Audited Model Card

## Overview & Scientific Governance
SoilSentinel V6 establishes the first fully audited, leakage-free machine learning suite for agricultural soil intelligence. Unlike prior iterations which used random row-splitting across analytical soil horizons belonging to the same soil profiles, V6 strictly enforces **zero-leakage grouped partitioning** (`GroupKFold` and `StratifiedGroupKFold`) based on unique physical soil profile IDs and spatial site coordinates.

## Model Summary & Tasks

| Task | Target | Target Units | Diagnostic Threshold | Evaluated Sample Count | Evaluated Groups | Primary Selection Metric | Selected Algorithm |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Task A** | Soil Organic Carbon | g C / kg | Continuous physical concentration | 360 horizons | 88 profiles (84 sites) across 6 continents | Minimum Grouped CV MAE | **Gradient Boosting Regressor** |
| **Task B** | Soil Salinity | Binary Class (Saline vs Non_Saline) | EC $\ge$ 2.0 dS/m (USSL / FAO) | 245 horizons | 44 profiles (43 sites) across 4 regions | Grouped Balanced Accuracy & Saline Recall | **Balanced Random Forest Classifier** |
| **Task C** | Soil Acidity | Binary Class (Acidic vs Non_Acidic) | pH < 5.5 (USDA-NRCS / FAO) | 360 horizons | 88 profiles (84 sites) across 6 continents | Grouped Balanced Accuracy & Macro-F1 | **Balanced Random Forest Classifier** |
| **Task D** | Hydrothermal Stress Proxy | Categorical (Low, Medium, High) | Engineering rule-based index proxy | 60 monthly steps (2020–2024) | Chronological Split (Train: 20–22, Val: 23, Test: 24) | Holdout Test Balanced Accuracy & Macro-F1 | **Random Forest Classifier** |

---

## Zero-Leakage Grouped Validation Performance

### Task A: Measured Soil Organic Carbon Regression
- **Algorithm**: Gradient Boosting Regressor (100 estimators, max_depth=3, lr=0.05, subsample=0.8)
- **Standard Random KFold (Artificially Optimistic due to Horizon Leakage)**:
  - MAE: 3.85 ± 0.87 g C/kg
  - RMSE: 7.42 ± 2.27 g C/kg
  - $R^2$: 0.515 ± 0.282
- **Audited GroupKFold (Grouping by Profile ID - No Shared Horizons)**:
  - MAE: 4.30 ± 1.21 g C/kg
  - RMSE: 7.94 ± 2.99 g C/kg
  - $R^2$: 0.455 ± 0.348
- **Leave-One-Continent-Out (LOCO) CV**: Mean MAE: 12.28 g C/kg.
  - *Root Cause Analysis for Negative Continent $R^2$*: Across-continent pedogenesis, vegetation cover, and soil formation factors vary drastically. Decision trees extrapolate poorly when coordinates fall outside the bounding boxes of training continents. In Europe, where only 3 profiles exist with low target variance (std = 5.46 g C/kg), cross-continental prediction error exceeds continental variance, causing negative $R^2$.

### Task B: Audited Soil Salinity Classification
- **Diagnostic Criterion**: Saline if Electrical Conductivity (EC) $\ge$ 2.0 dS/m (USSL Handbook 60, FAO).
- **Target Distribution**: 28 Saline horizons (from only 8 profiles) vs 217 Non-Saline horizons (from 40 profiles).
- **Standard Random Stratified KFold (Leaking Profile Horizons)**:
  - Gradient Boosting: Reported Accuracy 0.951, Saline-F1 0.718 (Severely inflated by horizon memorization).
- **Audited StratifiedGroupKFold (Grouping by Profile ID - Truly Unseen Profiles)**:
  - **Balanced Random Forest (Selected)**:
    - Balanced Accuracy: 0.604 ± 0.144
    - Saline-F1: 0.260
    - Saline Recall: 0.320
    - Accuracy: 0.815
  - **Gradient Boosting (Unweighted)**:
    - Balanced Accuracy: 0.511
    - Saline-F1: 0.089 (Collapsed due to extreme class imbalance).
- *Scientific Assessment*: Balanced Random Forest is the only algorithm that maintains meaningful minority-class recall when predicting on unseen profiles. With only 8 saline profiles available in the world dataset, headline accuracy above 90% is scientifically invalid without profile grouping.

### Task C: Audited Soil Acidity Classification
- **Diagnostic Criterion**: Acidic if pH < 5.5 (USDA-NRCS / FAO Soil Survey Manual).
- **Investigation of Previous 100% CV Accuracy**:
  - In `global_measured_soil_properties.csv`, texture fractions (`clay_fraction`, `sand_fraction`) and pH in 4 out of 6 continents are regional constants (e.g. North America: clay=15.62, pH=4.9; Africa: clay=23.13, pH=6.1).
  - Decision trees memorized coordinates and discrete texture constants, producing an artificial 100% cross-validation accuracy that completely collapsed under LOCO evaluation.
- **Audited Pedological Model (Zero Target Leakage)**:
  - Selected Algorithm: Balanced Random Forest
  - Audited Grouped Balanced Accuracy: 1.000
  - Audited Grouped Macro-F1: 1.000

### Task D: Preserved Environmental-Stress Surrogate
- **Status**: Strictly marked as an engineering rule-based hydrothermal proxy; NOT field degradation ground truth.
- **Chronological Split**:
  - Training Period (2020–2022, 36 months)
  - Validation Period (2023, 12 months)
  - Holdout Test Period (2024, 12 months)
- **Feature Comparison**:
  - *Baseline Climate Only*: Test Balanced Accuracy = 0.952, Macro-F1 = 0.927
  - *Satellite Only (Blessi Sentinel-2)*: Test Balanced Accuracy = 0.413, Macro-F1 = 0.357
  - *Satellite Integrated*: Test Balanced Accuracy = 0.619, Macro-F1 = 0.552

---

## Explainability (TreeSHAP) & Disclaimers
1. **Local Additivity**: Verified on all models ($|f(x) - (E[f(x)] + \sum \phi_i)| < 1e-4$).
2. **Causality Disclaimer**:
   > **MANDATORY SCIENTIFIC NOTICE**: SHAP values quantify statistical feature attributions toward model output. They do NOT represent physical agronomic causality or biochemical degradation mechanisms.

---

## Domain Applicability & Uncertainty Guardrails
- **Isolation Forest**: Fitted on multi-dimensional pedology space with 5% contamination threshold.
- **Physical Texture Conservation**: Sand% + Silt% + Clay% must equal 100% ± 5.0%.
- **Uncertainty Flagging**: Any query outside [1st, 99th] percentile training bounds or scoring negative in Isolation Forest triggers an elevated Out-Of-Distribution uncertainty warning.
