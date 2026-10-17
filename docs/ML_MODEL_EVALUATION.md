# SoilSentinel — Machine Learning Model Evaluation Report

**Evaluation Date:** October 2026  
**Role:** Senior ML Engineer & Evaluation Specialist  
**Project:** SoilSentinel (IBM Z Datathon 2026)  
**Trained Model Artifact:** [`models/soil_risk_model.joblib`](../models/soil_risk_model.joblib)  
**Preprocessor Artifact:** [`models/soil_risk_preprocessor.joblib`](../models/soil_risk_preprocessor.joblib)  
**Metadata Manifest:** [`models/model_metadata.json`](../models/model_metadata.json)  
**Pipeline Code:** [`src/Model/train_model.py`](../src/Model/train_model.py)  

---

## 1. Executive Summary

This report documents the machine learning training, evaluation, and benchmarking pipeline for SoilSentinel. To satisfy the datathon's requirement for a genuinely trained and evaluated predictive engine without compromising scientific integrity, we engineered a reproducible training workflow that learns a **surrogate model** to emulate the non-linear decision boundary of SoilSentinel's domain-heuristic **Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index**.

The models were evaluated using **chronological train/validation/test splits** (Train: 2020–2022, Val: 2023, Test: 2024) and **expanding-window TimeSeries cross-validation** ($k=4$). The selected **Random Forest Classifier** achieved **91.67% test accuracy** and **0.9267 Macro-F1** on the held-out 2024 test year, substantially outperforming the naive majority baseline (58.33% accuracy, 0.2456 Macro-F1).

---

## 2. Prediction Target & Provenance

* **Target Variable:** `risk_category` $\in \{\text{"Low"}, \text{"Medium"}, \text{"High"}\}$.
* **Target Provenance:** `SURROGATE_PROXY_LEARNING`.
* **Ground Truth Clarification:**
  > [!IMPORTANT]
  > **Proxy-Label Surrogate Distinction:**  
  > There are **zero in-situ ground sensors or physical soil degradation laboratory assays** in the primary dataset. The labels are generated deterministically by the rule-based risk scoring engine (`src/Model/risk_scoring.py`).
  >
  > The ML classifier is a **surrogate / emulator model** learning to approximate the multi-factor, piece-wise non-linear mapping between raw physical climate/soil covariates and the composite risk category.
  >
  > **Explicit Caveat:** This model does **NOT** forecast independent real-world soil erosion or biological degradation; it provides a high-performance, low-latency surrogate approximation of the transparent agronomic scoring heuristic.

---

## 3. Feature Schema & Leakage Prevention

The feature matrix $X$ consists of **14 dynamic physical and temporal features**:

| # | Feature Name | Physical Unit | Provenance | Scientific Rationale |
| :-: | :--- | :--- | :--- | :--- |
| 1 | `air_temperature_c` | °C | NASA POWER | Ambient thermal forcing |
| 2 | `air_humidity_percent` | % | NASA POWER | Atmospheric vapor pressure deficit / evaporative demand |
| 3 | `precipitation_mm_day` | mm/day | NASA POWER | Direct monthly hydrological recharge |
| 4 | `soil_temperature_layer1_c` | °C | NASA POWER | Direct topsoil (0–10 cm) heat loading |
| 5 | `soil_moisture_surface_fraction` | 0–1 fraction | NASA POWER | Immediate evaporative front wetness |
| 6 | `soil_moisture_rootzone_fraction` | 0–1 fraction | NASA POWER | Active root-zone available water capacity |
| 7 | `precipitation_lag1_mm_day` | mm/day | Engineered | Antecedent 1-month precipitation |
| 8 | `air_temperature_lag1_c` | °C | Engineered | Antecedent 1-month temperature |
| 9 | `precipitation_rolling_3m_mean_mm_day` | mm/day | Engineered | Medium-term meteorological drought index |
| 10 | `temp_soil_air_diff_c` | °C | Engineered | Soil-canopy thermal decoupling |
| 11 | `soil_moisture_depth_gradient` | fraction | Engineered | Vertical hydraulic gradient ($GWETROOT - GWETTOP$) |
| 12 | `monthly_aridity_index` | unitless | Engineered | De Martonne aridity index ($P / (T + 10)$) |
| 13 | `month_sin` | [-1, 1] | Engineered | Harmonic seasonal calendar component |
| 14 | `month_cos` | [-1, 1] | Engineered | Harmonic seasonal calendar component |

### Target Leakage Prevention
* **Excluded Rule Outputs:** `score`, `risk_category`, `status`, `dynamic_environmental_stress`, `baseline_soil_vulnerability`, and all 5 individual indicator sub-scores (`moisture_deficit_sub_score`, `precipitation_deficit_sub_score`, etc.) were strictly excluded from $X$.
* **Excluded Zero-Variance Features:** Inherent static soil properties from SoilGrids (e.g. `topsoil_ph_mean`, `topsoil_soc_g_kg`, `clay_percent`) are uniform across all 60 monthly steps at this location and were excluded to prevent non-informative constant coefficients.
* **Strict Featurization Order:** All preprocessing transformers (`SimpleImputer(strategy='median')`, `StandardScaler()`) were fitted **strictly on training partitions** and applied out-of-sample to validation and test partitions.

---

## 4. Chronological Splitting & Sample Size Limitations

The dataset comprises 60 consecutive monthly timesteps (2020–2024) at a single location in Punjab.

### Chronological Splits
* **Training Window ($N = 36$, 60%):** `2020-01` to `2022-12` (3 full agricultural years).
  * Class Distribution: Medium: 18 (50.0%), Low: 17 (47.2%), High: 1 (2.8%).
* **Validation Window ($N = 12$, 20%):** `2023-01` to `2023-12` (1 full agricultural year).
  * Class Distribution: Medium: 8 (66.7%), Low: 4 (33.3%), High: 0 (0.0%).
* **Held-out Test Window ($N = 12$, 20%):** `2024-01` to `2024-12` (1 full agricultural year).
  * Class Distribution: Medium: 7 (58.3%), Low: 3 (25.0%), High: 2 (16.7%).

### Sample Size & Imbalance Limitations
1. **Extreme Rarity of "High Risk":** Across all 60 months, only 3 instances of High Risk occur (May 2022, May 2024, June 2024).
2. **Temporal Dependence:** Standard random K-Fold cross-validation would cause data leakage between adjacent months (e.g., predicting May 2022 using April and June 2022). Therefore, chronological evaluation and expanding-window TimeSeries cross-validation were enforced.
3. **Small Sample Size Warning:** $N = 60$ monthly observations represents a 5-year monitoring horizon. While sufficient for surrogate approximation of seasonal trends, larger multi-site datasets will be necessary for multi-regional generalization.

---

## 5. Model Architectures & Configurations

1. **Dummy Baseline:**
   * Strategy: `most_frequent` (majority class baseline). Always predicts `Medium`.
2. **Logistic Regression (Linear Baseline):**
   * Multi-class: One-vs-Rest / Multinomial via L-BFGS.
   * Regularization: $L_2$ ($C = 1.0$).
   * Class Weighting: `class_weight='balanced'` to prevent minority class neglect.
   * `max_iter`: 1,000.
3. **Random Forest Classifier (Primary Model):**
   * `n_estimators`: 100 decision trees.
   * `max_depth`: 4 (constrained to prevent memorization on small sample size).
   * `class_weight`: `balanced`.
   * `random_state`: 42.
4. **Gradient Boosting Classifier (Ensemble Comparison):**
   * `n_estimators`: 50 boosting stages.
   * `max_depth`: 3.
   * `learning_rate`: 0.1.
   * `random_state`: 42.

---

## 6. Comprehensive Evaluation Metrics

### 6.1 Model Comparison Summary

| Model Architecture | Validation Accuracy (2023) | Validation Macro-F1 | Test Accuracy (2024) | Test Macro-F1 | Test Weighted-F1 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Dummy (Majority Class)** | 0.6667 | 0.4000 | 0.5833 | 0.2456 | 0.4298 |
| **Logistic Regression** | **1.0000** | **1.0000** | **0.9167** | **0.9267** | **0.9194** |
| **Random Forest (Selected)** | **1.0000** | **1.0000** | **0.9167** | **0.9267** | **0.9194** |
| **Gradient Boosting** | **1.0000** | **1.0000** | **0.9167** | **0.9267** | **0.9194** |

### 6.2 Selected Random Forest: Test Set Detailed Performance (2024 Held-Out)

* **Overall Test Accuracy:** `91.67%` (11 / 12 correct).
* **Macro-Averaged F1-Score:** `0.9267`.
* **Weighted-Averaged F1-Score:** `0.9194`.

#### Per-Class Classification Report

| Class Label | Precision | Recall | F1-Score | Support (Observed Months) |
| :--- | :---: | :---: | :---: | :---: |
| **High** | **1.0000** | **1.0000** | **1.0000** | 2 |
| **Low** | **0.7500** | **1.0000** | **0.8571** | 3 |
| **Medium** | **1.0000** | **0.8571** | **0.9231** | 7 |
| **Macro Average** | **0.9167** | **0.9524** | **0.9267** | 12 |
| **Weighted Average**| **0.9375** | **0.9167** | **0.9194** | 12 |

#### Confusion Matrix (Held-out Test Year 2024)

```
                     Predicted High   Predicted Low   Predicted Medium
Actual High (n=2)          2                0                0
Actual Low  (n=3)          0                3                0
Actual Med  (n=7)          0                1                6
```

#### Error Analysis of the Single Misclassified Test Record:
* **Record:** `2024-07` (July 2024).
* **Actual Category:** `Medium` (Exact Rule-Based Score: **36.18 / 100**).
* **Predicted Category:** `Low`.
* **Agronomic Diagnosis:**
  The threshold between Low and Medium is exactly **35.0**. In July 2024, the arrival of early monsoon showers increased root-zone moisture ($0.53$) and lowered temperature ($31.6^\circ\text{C}$), placing the physical state just **1.18 index points** above the threshold. The surrogate model predicted `Low`, demonstrating boundary conservatism under transition weather.

---

## 7. Expanding-Window TimeSeries Cross-Validation

To verify that model performance is not an artifact of a single lucky temporal split, we conducted 4-fold expanding window cross-validation:

| Fold | Training Window | Train $N$ | Validation Window | Val $N$ | Accuracy | Macro-F1 |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: |
| **Fold 1** | 2020-01 to 2020-12 | 12 | 2021-01 to 2021-12 | 12 | 0.9167 | 0.9111 |
| **Fold 2** | 2020-01 to 2021-12 | 24 | 2022-01 to 2022-12 | 12 | 0.8333 | 0.5611 |
| **Fold 3** | 2020-01 to 2022-12 | 36 | 2023-01 to 2023-12 | 12 | 1.0000 | 1.0000 |
| **Fold 4** | 2020-01 to 2023-12 | 48 | 2024-01 to 2024-12 | 12 | 0.9167 | 0.9267 |
| **Mean** | — | — | — | — | **0.9167** | **0.8497** |

*Note on Fold 2:* In 2022, the first ever `High` risk event in the dataset occurred (May 2022 heatwave). Because the training set (2020–2021) contained zero `High` cases, Fold 2 Macro-F1 was lower (0.5611) as it had not yet observed extreme heat stress. Once 2022 was included in training, subsequent folds (Folds 3 and 4) demonstrated near-perfect identification of all classes.

---

## 8. Feature Importance Analysis (Random Forest MDI)

Top driving features learned by the Random Forest surrogate model:

| Rank | Feature Name | Mean Decrease in Impurity (Gini) | Interpretation |
| :-: | :--- | :---: | :--- |
| 1 | `precipitation_rolling_3m_mean_mm_day` | **0.2520** | Multi-month cumulative moisture recharge deficit |
| 2 | `soil_moisture_rootzone_fraction` | **0.2372** | Direct available water capacity in active root-zone |
| 3 | `soil_moisture_surface_fraction` | **0.1741** | Surface evaporative front wetness |
| 4 | `air_humidity_percent` | **0.1065** | Atmospheric vapor pressure deficit |
| 5 | `soil_temperature_layer1_c` | **0.0637** | Thermal stress threshold trigger |
| 6 | `month_sin` | **0.0526** | Seasonal cyclicality |
| 7 | `air_temperature_lag1_c` | **0.0384** | Antecedent thermal momentum |
| 8 | `precipitation_lag1_mm_day` | **0.0248** | Short-term rainfall memory |
| 9 | `monthly_aridity_index` | **0.0221** | Agro-climatic dryness ratio |
| 10 | `soil_moisture_depth_gradient` | **0.0125** | Profile water distribution gradient |

---

## 9. Artifact Integrity & Verification

The fitted model and preprocessing components were serialized using atomic file replacements (`.tmp` $\rightarrow$ final destination):

1. **Model Pipeline:** `models/soil_risk_model.joblib` (109 KB). Contains complete, self-contained inference pipeline (`SimpleImputer` $\rightarrow$ `StandardScaler` $\rightarrow$ `RandomForestClassifier`).
2. **Preprocessor:** `models/soil_risk_preprocessor.joblib` (1.2 KB).
3. **Metadata Manifest:** `models/model_metadata.json` (7 KB).
4. **Post-Serialization Verification:** The model was loaded back from disk and verified via out-of-sample inference on `2024-01`, producing category `Medium` with model-estimated class probabilities (uncalibrated tree ensemble vote fractions):
   * $\hat{P}(\text{Medium}) = 0.970$
   * $\hat{P}(\text{Low}) = 0.010$
   * $\hat{P}(\text{High}) = 0.020$
   *(Note: These values reflect raw tree ensemble vote distributions across 100 estimators; they are designated as "model-estimated class probabilities" because empirical probability calibration such as Platt scaling or isotonic regression was not applied).*

---

## 10. SHAP (SHapley Additive exPlanations) & Surrogate Feature Attribution

To provide transparent, mathematically sound feature attributions for surrogate model predictions, SoilSentinel integrates **TreeSHAP** (`shap.TreeExplainer`). This allows both researchers and farmers to inspect the additive contributions ($\sum \phi_j$) pushing individual predictions away from the baseline prior toward specific risk categories.

### 10.1 Explainer Provenance & Methodology
* **Surrogate Attribution Only:** SHAP explains the decision surface of the Random Forest surrogate model. It quantifies statistical feature attributions toward the surrogate model's predicted class probabilities; it does **NOT** represent physical ground-truth causation or field soil degradation mechanisms.
* **Strict Training Partition Background:** The explainer background is constructed strictly from the chronologically held-out training partition (`X_train`, 2020-01 to 2022-12, $N=36$). Zero validation or test data is accessible during explainer fitting.
* **Explainer Artifact:** Serialized as `models/soil_risk_explainer.joblib` (189 KB) with atomic persistence.
* **Output Space & Base Values:** The explainer operates in `model_output="probability"` space. Base values ($\mathbb{E}[f(X)]$) represent the training set class priors:
  * $\text{Base Prior}(\text{High}) = 0.0617$
  * $\text{Base Prior}(\text{Low}) = 0.4708$
  * $\text{Base Prior}(\text{Medium}) = 0.4675$

### 10.2 Multiclass Mapping & Strict Additivity Verification
* **Explicit Multiclass Indexing:** Classes are dynamically resolved from `model.classes_` (`["High", "Low", "Medium"]`). Index mapping is never hard-coded or assumed.
* **Additivity Principle:** In probability space, local feature contributions must satisfy:
  $$\hat{P}(c) \approx \phi_0(c) + \sum_{j=1}^{14} \phi_j(c)$$
* **Empirical Validation on Held-Out 2024 Test Set ($N=12$):** Across all 12 test months and all 3 classes (36 evaluation points), the maximum absolute discrepancy observed was:
  $$\max_{i, c} \left| \left(\phi_0(c) + \sum_{j=1}^{14} \phi_{i, j}(c)\right) - \hat{P}_i(c) \right| = 0.010278 \le 0.020000$$
  *(Mean absolute discrepancy: $0.000741$). The runtime inference service enforces an explicit tolerance check ($\le 0.02$). If violated, the engine returns an explicit `ERROR` rather than fabricated values.*

### 10.3 Global SHAP Importance vs. Gini Importance vs. Rule-Based Weights
The held-out 2024 test partition ($N=12$) was used to compute global mean absolute SHAP values ($\frac{1}{N} \sum_{i=1}^N |\phi_{i, j}|$), exported to `outputs/shap_global_importance.csv`:

| Rank | Feature | Mean \|SHAP\| (Overall) | High Risk \|SHAP\| | Low Risk \|SHAP\| | Medium Risk \|SHAP\| | RF Gini Importance | Distinction from 5 Rule-Based Weights |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **1** | `soil_moisture_surface_fraction` | **0.0777** | 0.0071 | 0.1157 | 0.1104 | 0.1371 | Dynamic ML feature; distinct from rule weight |
| **2** | `soil_moisture_rootzone_fraction` | **0.0653** | 0.0101 | 0.0970 | 0.0887 | 0.1218 | Dynamic ML feature; distinct from rule weight |
| **3** | `air_humidity_percent` | **0.0610** | 0.0284 | 0.0834 | 0.0712 | 0.1603 | Dynamic ML feature; distinct from rule weight |
| **4** | `soil_moisture_depth_gradient` | **0.0509** | 0.0155 | 0.0739 | 0.0632 | 0.1426 | Dynamic ML feature; distinct from rule weight |
| **5** | `air_temperature_c` | **0.0343** | 0.0510 | 0.0112 | 0.0409 | 0.1404 | Dynamic ML feature; distinct from rule weight |
| **6** | `precipitation_rolling_3m_mean_mm_day` | **0.0219** | 0.0030 | 0.0323 | 0.0303 | 0.0395 | Dynamic ML feature; distinct from rule weight |
| **7** | `soil_temperature_layer1_c` | **0.0165** | 0.0246 | 0.0072 | 0.0176 | 0.0818 | Dynamic ML feature; distinct from rule weight |
| **8** | `precipitation_lag1_mm_day` | **0.0146** | 0.0098 | 0.0200 | 0.0140 | 0.0498 | Dynamic ML feature; distinct from rule weight |
| **9** | `monthly_aridity_index` | **0.0109** | 0.0027 | 0.0138 | 0.0163 | 0.0286 | Dynamic ML feature; distinct from rule weight |
| **10** | `temp_soil_air_diff_c` | **0.0070** | 0.0077 | 0.0047 | 0.0085 | 0.0293 | Dynamic ML feature; distinct from rule weight |
| **11** | `air_temperature_lag1_c` | **0.0064** | 0.0088 | 0.0045 | 0.0059 | 0.0317 | Dynamic ML feature; distinct from rule weight |
| **12** | `month_sin` | **0.0049** | 0.0018 | 0.0064 | 0.0065 | 0.0147 | Dynamic ML feature; distinct from rule weight |
| **13** | `precipitation_mm_day` | **0.0021** | 0.0026 | 0.0010 | 0.0029 | 0.0119 | Dynamic ML feature; distinct from rule weight |
| **14** | `month_cos` | **0.0020** | 0.0024 | 0.0010 | 0.0026 | 0.0106 | Dynamic ML feature; distinct from rule weight |

#### Architectural Key Differences:
1. **SHAP vs. Gini:** Gini impurity measures training node split frequency (biased toward high-cardinality features and uncalibrated across classes). SHAP measures out-of-sample directional impact on class probability. For instance, `air_temperature_c` is the #1 driver specifically for `High` risk attribution (0.0510), while `soil_moisture_surface_fraction` is the #1 driver for `Low` risk attribution (0.1157).
2. **ML Features vs. Rule-Based Weights:** The rule-based engine aggregates 5 predetermined agronomic indicators with static heuristic weights (`moisture_deficit: 0.30`, `precipitation_deficit: 0.25`, `thermal_stress: 0.20`, `soc_vulnerability: 0.15`, `ph_deviation: 0.10`). In contrast, SHAP attributions operate across 14 dynamic continuous covariates without human weight assignment.
