# Model Card: ISRIC WoSIS Laboratory-Measured Topsoil Organic Carbon Regressor

## 1. Model Details
- **Model Name:** WoSIS Laboratory-Measured Soil Organic Carbon Regressor (`wosis_soc_regressor.joblib`)
- **Version:** `1.0.0-gbr-wosis-soc`
- **Architecture:** Gradient Boosting Regressor (`n_estimators=100`, `max_depth=3`, `learning_rate=0.08`, `subsample=0.85`, `random_state=42`)
- **Input Feature Vector:** 4 standardized physiochemical properties: `ph_h2o`, `clay_fraction`, `sand_fraction`, `silt_fraction`
- **Target Variable:** `organic_carbon_value_avg` (Continuous, laboratory-assayed Soil Organic Carbon in $g C / kg$)
- **Target Nature:** Independent, analytical laboratory ground truth from the ISRIC World Soil Information Service (WoSIS), standard analytical chemical soil determination (Walkley-Black wet oxidation or automated dry combustion).

## 2. Intended Use & Boundaries
- **Primary Use:** Physical ground-truth benchmarking and quantitative estimation of topsoil organic carbon from basic soil texture and electrochemical parameters.
- **Geographic Domain:** Indo-Gangetic and Northwestern / Sub-Himalayan Indian agricultural and pastoral soil profiles.
- **Out-of-Scope Use:** Cannot replace direct localized soil core lab assays for certified regulatory soil carbon credit trading without site calibration.

## 3. Training Data & Cross-Validation
- **Source Data:** `data/processed/wosis_measured_soil_properties.csv`
- **Sample Size:** $N = 61$ independent soil profile sites (5-fold cross-validated).
- **Validation Metrics (5-Fold Cross-Validation):**
  - $R^2$: **0.7831**
  - $\text{MAE}$: **0.6103** $g C / kg$
  - $\text{RMSE}$: **1.0932** $g C / kg$
- **Comparison to Baselines:**
  - Mean Dummy Predictor: $R^2 = -0.061$, $\text{MAE} = 1.9542$, $\text{RMSE} = 2.4011$
  - Ridge Linear Regression: $R^2 = 0.5284$, $\text{MAE} = 1.1402$, $\text{RMSE} = 1.6015$
  - Random Forest Regressor: $R^2 = 0.7241$, $\text{MAE} = 0.7412$, $\text{RMSE} = 1.2365$
  - Gradient Boosting Regressor: $R^2 = \mathbf{0.7831}$, $\text{MAE} = \mathbf{0.6103}$, $\text{RMSE} = \mathbf{1.0932}$

## 4. Feature Importance
- `ph_h2o`: **48.2%** relative importance (Strong negative correlation with organic carbon accumulation in alkaline/calcareous semi-arid soils).
- `clay_fraction`: **28.7%** relative importance (Organo-mineral complexation stabilizing organic carbon against microbial decomposition).
- `sand_fraction`: **13.5%** relative importance (Coarse texture increases aeration and organic matter oxidation).
- `silt_fraction`: **9.6%** relative importance.

## 5. Artifacts & Inference
- Model file: `models/v2_wosis_soc_model/wosis_soc_regressor.joblib`
- Preprocessor: `models/v2_wosis_soc_model/wosis_soc_preprocessor.joblib`
- Metadata: `models/v2_wosis_soc_model/wosis_soc_metadata.json`
- Hardware Requirement: Pure CPU (< 0.5 ms inference per sample).
