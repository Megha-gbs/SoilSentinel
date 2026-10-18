# Soil Sentinel — Automated Data Collection Pipeline

> 🚀 **Live Production Deployment on IBM LinuxONE (s390x):**  
> **Web Portal:** [http://148.100.109.202:3100/index.html](http://148.100.109.202:3100/index.html)  
> **System & Model Health Status:** [http://148.100.109.202:3100/api/health](http://148.100.109.202:3100/api/health)  
> **Target Architecture:** IBM LinuxONE / Linux on IBM Z (s390x), Node.js v22.23.3 (node:sqlite zero-compilation built-in engine), Python ML Bridge (port 5101), OpenCV 4.6.0.  
> **Demo Credentials:**  
> - 🌾 **Farmer Workspace:** `farmer.demo@soilsentinel.local` | `DemoSoil2026!`  
> - 🔬 **Researcher Workspace:** `researcher.demo@soilsentinel.local` | `DemoSoil2026!`

Soil Sentinel is an automated data collection and preprocessing pipeline for agricultural risk monitoring and soil health intelligence. It automatically queries authoritative environmental data sources without requiring manual browser downloads.

## Data Sources

1. **NASA POWER API (Agroclimatology Community)**
   - **Service Endpoint:** `https://power.larc.nasa.gov/api/temporal/monthly/point`
   - **Temporal Resolution:** Monthly (2020–2024, 60 records)
   - **Parameters Collected:**
     - `T2M`: Air Temperature at 2 Meters (°C)
     - `RH2M`: Air Relative Humidity at 2 Meters (%)
     - `PRECTOTCORR`: Precipitation Corrected (mm/day)
     - `GWETTOP`: Surface Soil Wetness (0 to 1 fraction)
     - `GWETROOT`: Root Zone Soil Wetness (0 to 1 fraction)
     - `TSOIL1`: Soil Temperature Layer 1 0–10 cm (°C)
   - **Raw Storage:** `data/raw/climate/nasa_power_monthly_2020_2024_30.73_76.77.json`
   - **Processed Storage:** `data/processed/climate_data.csv`

2. **ISRIC SoilGrids v2.0**
   - **Service Endpoint:** `https://files.isric.org/soilgrids/latest/data/` (Official VRT Streaming Service)
   - **Depth Intervals:** `0-5cm`, `5-15cm`, `15-30cm`
   - **Properties Collected:**
     - `phh2o`: Soil pH in H₂O solution (raw DN / 10 = standard pH)
     - `clay`: Clay mass fraction (raw DN / 10 = %)
     - `sand`: Sand mass fraction (raw DN / 10 = %)
     - `silt`: Silt mass fraction (raw DN / 10 = %)
     - `soc`: Soil Organic Carbon (raw DN / 10 = g/kg)
   - **Raw Storage:** `data/raw/soil/soilgrids_raw_metadata.json`
   - **Processed Storage:** `data/processed/soil_data.csv`

3. **Combined Features**
   - **Processed Storage:** `data/processed/combined_features.csv`
   - Aligns monthly climate time series with regional depth-weighted topsoil baseline features (0–30 cm).

4. **Standardized Feature Table**
   - **Generated Storage:** `data/feature_table.csv`
   - Engineered feature table containing 53 validated features including temporal context, lag/rolling precipitation, thermal coupling, moisture gradients, and soil texture ratios.
   - **Data Dictionary:** Complete feature-by-feature definitions, units, formulas, provenance, and limitations are documented in [`docs/data_dictionary.md`](docs/data_dictionary.md).

---

## Study Region Configuration

Configured in `config/settings.yaml`:
- **Region:** Indo-Gangetic Agricultural Plains / Punjab
- **Nominal Coordinates:** Latitude `30.7300° N`, Longitude `76.7700° E`
- **Sampled Agricultural Coordinates:** Latitude `30.7392° N`, Longitude `76.7764° E` (1.0 km distance from urban center, avoiding NODATA urban masking)
- **Time Window:** 2020–2024 (Monthly)

---

## Execution Instructions

From the project root in the Windows terminal or VS Code terminal:

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the automated data collection pipeline
python src/data_collection/download_all.py

# 3. Generate the engineered feature table
python src/features.py
```

### Optional Flags
- `--force`: Force re-download and bypass cached raw API responses:
  ```powershell
  python src/data_collection/download_all.py --force
  ```
- Or run through the project entrypoint:
  ```powershell
  python main.py
  ```

---

## Risk Scoring & Prediction Engine (Member 2)

Soil Sentinel implements a transparent, deterministic **Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index** ([`src/Model/risk_scoring.py`](src/Model/risk_scoring.py)).

> [!NOTE]
> **Heuristic Agronomic Index (Not a Trained ML Model):**  
> The engine is a deterministic, rule-based screening index calibrated to agronomic baselines in the Indo-Gangetic Plains. It does **not** employ a trained machine learning model, statistical regression, or neural network.

### Exact Component Scores, Normalization, and Weights

| Sub-Index Group | Contributing Indicator | Feature Source & Unit | Scaling & Normalization Range | Weight |
| :--- | :--- | :--- | :--- | :---: |
| **Dynamic Environmental Stress (70%)** | Root-zone Soil Moisture Deficit | NASA POWER `GWETROOT` (fraction) | Inverted: $[0.75 \rightarrow 0.0, 0.25 \rightarrow 100.0]$ | **30%** (`0.30`) |
| | Meteorological Recharge Deficit | NASA POWER rolling 3m mean ($\text{mm/day}$) | Inverted: $[6.0 \rightarrow 0.0, 0.5 \rightarrow 100.0]$, damped by Moisture Buffering Factor $\beta \in [0.50, 1.00]$ | **25%** (`0.25`) |
| | Topsoil Thermal Stress | NASA POWER `TSOIL1` ($^\circ\text{C}$) | Direct: $[24.0 \rightarrow 0.0, 38.0 \rightarrow 100.0]$ | **15%** (`0.15`) |
| **Static Baseline Soil Vulnerability (30%)** | Topsoil SOC Depletion | SoilGrids `soc` ($0–30\,\text{cm}$, $\text{g/kg}$) | Inverted: $[25.0 \rightarrow 0.0, 5.0 \rightarrow 100.0]$ | **15%** (`0.15`) |
| | Topsoil pH Deviation | SoilGrids `phh2o` ($0–30\,\text{cm}$) | Piecewise: $0.0$ for $[6.5, 7.5]$, linear deviation up to $\pm 2.0$ units $\rightarrow 100.0$ | **15%** (`0.15`) |
| **Total** | | | **All 5 Component Weights Sum to Exactly 1.00** | **100%** (`1.00`) |

### Moisture Buffering Formula
Precipitation deficit penalty is adjusted by the rootzone moisture buffering factor $\beta$:
$$\text{Score}_{\text{precip}} = \text{round}(\text{RawScore} \times \beta, 2)$$
$$\beta = \begin{cases} 1.00 & \text{if } \text{moisture} \le 0.35 \text{ (depleted root-zone; 100% penalty retained)} \\ 0.50 & \text{if } \text{moisture} \ge 0.65 \text{ (ample root-zone; 50% maximum relief)} \\ 1.0 - 0.5 \times \frac{\text{moisture} - 0.35}{0.65 - 0.35} & \text{if } 0.35 < \text{moisture} < 0.65 \text{ (intermediate buffering)} \end{cases}$$

### Composite Score and Risk Categories
$$\text{Composite Score} = \operatorname{round}\left(\sum_{i=1}^{5} \text{Weight}_i \times \text{Score}_i, 2\right) \in [0.0, 100.0]$$
- **Low Risk:** $[0.0, 35.0)$
- **Medium Risk:** $[35.0, 65.0)$
- **High Risk:** $[65.0, 100.0]$

---

## Prediction & Inference Execution

```powershell
# 1. Permissive Prediction (Default: single-month fallback for boundary records 2020-01 and 2020-02)
python src/Model/predict.py --input data/feature_table.csv --output outputs/predictions.csv --audit-log logs/audit_log.csv

# 2. Strict Prediction (Rejects unobserved rolling history with INSUFFICIENT_HISTORY)
python src/Model/predict.py --input data/feature_table.csv --output outputs/predictions_strict.csv --strict --audit-log logs/audit_log.csv
```

---

## Machine Learning Surrogate Engine

SoilSentinel provides a genuinely trained machine learning surrogate pipeline ([`src/Model/train_model.py`](src/Model/train_model.py)) designed to approximate the multi-factor heuristic risk classification directly from raw environmental and hydrological covariates:

* **Algorithm:** Random Forest Classifier (100 trees, balanced class weights, max depth 4).
* **Feature Schema:** 14 dynamic physical and temporal indicators (zero target leakage; no sub-scores or composite score).
* **Split Strategy:** Strict chronological split (Train: 2020–2022, Validation: 2023, Held-out Test: 2024) + 4-fold TimeSeries cross-validation.
* **Test Performance (2024 Held-Out):** **91.67% Accuracy**, **0.9267 Macro-F1** (vs. Naive Majority Baseline 58.33% Accuracy, 0.2456 Macro-F1).
* **Target Provenance:** Explicitly qualified as `SURROGATE_PROXY_LEARNING` emulating the rule-based index (not field degradation assays).
* **Serialized Artifacts:**
  * Model Pipeline: [`models/soil_risk_model.joblib`](models/soil_risk_model.joblib)
  * Preprocessor: [`models/soil_risk_preprocessor.joblib`](models/soil_risk_preprocessor.joblib)
  * SHAP Explainer: [`models/soil_risk_explainer.joblib`](models/soil_risk_explainer.joblib)
  * Metadata Manifest: [`models/model_metadata.json`](models/model_metadata.json)
  * Global SHAP Importance: [`outputs/shap_global_importance.csv`](outputs/shap_global_importance.csv)
* **SHAP Explainability:**
  * TreeSHAP explainer fitted strictly on the transformed 2020–2022 training partition background ($N=36$).
  * Multiclass probability attribution with runtime additivity verification ($\le 0.02$ tolerance).
  * Returns JSON-native signed impacts, top-5 drivers, original feature values, and direction.
  * Disclaims physical causation (explains surrogate model decision surface, not soil degradation ground truth).
* **Detailed Reports:**
  * Dataset & Provenance Audit: [`docs/ML_DATASET_AUDIT.md`](docs/ML_DATASET_AUDIT.md)
  * ML Evaluation & Benchmarking: [`docs/ML_MODEL_EVALUATION.md`](docs/ML_MODEL_EVALUATION.md)

```powershell
# Train and evaluate ML surrogate models and generate SHAP explainer
python src/Model/train_model.py
```

---

## Validation & Integrity

- **Missing Values:** Zero unexpected nulls or fabricated records. Exactly 1 boundary NaN in 1-month lags and 2 boundary NaNs in 3-month rolling windows reflecting unobserved historical start values.
- **Physical Bounds:** Temperature (-50°C to 60°C), Humidity (0% to 100%), Precipitation (0 to 500 mm/day), Soil pH (3.0 to 11.0), Texture sum (clay + sand + silt ≈ 100%).
- **Audit Trail:** Cumulative, append-only CSV audit logger (`logs/audit_log.csv`) recording timestamped ISO 8601 UTC entries without storing raw features or credentials.
- **Data Dictionary:** Detailed feature catalog and operational limitations are documented in [`docs/data_dictionary.md`](docs/data_dictionary.md).



---


---

## Full-Stack Web Application & API Gateway

### Live IBM LinuxONE (s390x) Deployment

The production instance of SoilSentinel is actively running on an **IBM LinuxONE (Linux on IBM Z, s390x)** mainframe server:

* **Live Application URL:** [http://148.100.109.202:3100/index.html](http://148.100.109.202:3100/index.html)
* **Live System Health Check:** [http://148.100.109.202:3100/api/health](http://148.100.109.202:3100/api/health)
* **Verified Runtime Stack:**
  - **Target Architecture:** s390x (IBM Z Enterprise Architecture)
  - **Node.js Engine:** v22.23.3 (running native zero-compilation `node:sqlite` DatabaseSync)
  - **Python ML Bridge:** Active on port 5101 with multi-task heuristic & surrogate inference
  - **Vision Engine:** OpenCV 4.6.0 enabled for morphological soil analysis
  - **Persistence:** Relational user management and 144+ persisted assessments in SQLite

SoilSentinel includes a role-based Node.js Express gateway and responsive web interfaces:

* **Gateway Server:** [`server.js`](server.js) — Express-based application server with session persistence in SQLite (`node:sqlite` / `better-sqlite3`), Helmet security headers, bcrypt authentication, and rate limiting.
* **Landing Page:** [`index.html`](index.html) — Overview of SoilSentinel capabilities and entry point.
* **Authentication Portal:** [`auth.html`](auth.html) — Role-based sign-in and registration for Farmers and Researchers.
* **Farmer Dashboard:** [`farmer-dashboard.html`](farmer-dashboard.html) — Dynamic risk assessment, voice guidance advisory, crop suitability recommendations, recovery action simulator, and multilingual support.
* **Researcher Dashboard:** [`researcher-dashboard.html`](researcher-dashboard.html) — Multi-factor historical dataset explorer, TreeSHAP explainability attributions, what-if meteorological scenario stress-testing, and compliance audit trail.
* **Python Backend Bridge:** [`src/Model/bridge.py`](src/Model/bridge.py) — Spawns as a background HTTP microservice (`http://127.0.0.1:5001` / `http://127.0.0.1:5101`) with graceful fallback to CLI execution.

### Pre-configured Development Demo Accounts

For local demonstration and offline auditing, development demo credentials are pre-seeded in the database:

| Role | Email | Password | Primary Capabilities |
| :--- | :--- | :--- | :--- |
| **Farmer** | `farmer.demo@soilsentinel.local` | `DemoSoil2026!` | Field risk assessment, crop viability scoring, voice advisory, recovery simulator |
| **Researcher** | `researcher.demo@soilsentinel.local` | `DemoSoil2026!` | Historical dataset exploration, TreeSHAP explainability, what-if meteorological simulation, audit trail |


## Website experience and evidence visualizations

The canonical web application remains the Express-served HTML/CSS/JavaScript experience. The dashboard pages use the existing authenticated assessment API and Python bridge; they do not calculate or replace the backend risk score in the browser.

### Dashboard visuals added
- Farmer workspace: rule-based screening-index timeline, component sub-score bars, climate trend chart, configured study-area map, and a contextual assessment helper grounded in the currently loaded payload.
- Researcher workspace: screening-index history, component sub-score comparison, monthly climate trend, depth-specific soil property comparison, and the configured study-area map.
- A read-only authenticated endpoint, `GET /api/assessment/observations`, returns an allow-listed subset of `data/feature_table.csv` through the Python bridge.
- Charts display empty/error states when source data are unavailable. The map uses the configured sampled Punjab-area reference point; it is not a farm boundary or parcel-level risk map.

### Start the website
1. Install Node dependencies from the project root: `npm ci`.
2. Create `.env` from `.env.example` and set a unique `SESSION_SECRET` of at least 32 characters.
3. Install Python dependencies from `requirements-core.txt` (or the documented requirements for the full pipeline).
4. Start the application with `npm start`, then open `http://localhost:3000`.
5. Development demo accounts are available only when `NODE_ENV` is not `production` and `ENABLE_DEMO_ACCOUNTS` is not `false`; see the existing credentials/configuration in the README. Do not ship a development database or demo credentials into production.

### Data interpretation guardrails
- The climate time series contains 60 monthly rows from 2020-01 through 2024-12 for the configured regional study point.
- Precipitation is displayed as the `precipitation_mm_day` field (mm/day), not monthly accumulated precipitation.
- SoilGrids depth values are modeled regional baselines, not monthly field-lab observations.
- The risk history is a sequence of outputs from the deterministic screening index, not independent measurements of soil degradation.
- The assessment helper is a local, rule-based explanation interface, not a generative AI chatbot. It only answers supported questions from the loaded assessment payload.
- Leaflet/OpenStreetMap map tiles require network access. If the map library cannot load, the page provides a coordinate-based fallback link rather than inventing a spatial layer.

### Website verification notes
Run JavaScript syntax checks with `node --check server.js` and `node --check dashboard-visuals.js`; Python bridge syntax can be checked with `python -m py_compile src/Model/bridge.py`. These checks verify syntax only; they do not replace browser-level testing, authentication testing, or an actual LinuxONE deployment smoke test.
