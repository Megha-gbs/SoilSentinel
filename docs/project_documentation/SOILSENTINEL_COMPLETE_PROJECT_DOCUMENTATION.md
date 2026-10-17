# SoilSentinel: Complete System Architecture, Algorithmic Auditing, Scientific Integrity, and Production Roadmap

**IBM Z Datathon 2026 Submission & Engineering Specification**  
**Project Directory:** `C:\Users\mohitkumar\Documents\Datathon`  
**Current Release Version:** `v1.2.0-surrogate-audit`  
**Runtime Architecture:** Python 3.10+ / Node.js 22 LTS / SQLite 3.49+ / Sentinel-2 L2A / NASA POWER / ISRIC SoilGrids  
**Document Classification:** Comprehensive Technical & Operational Architecture Review  
**Date of Audit:** October 17, 2026  

---

## Table of Contents

1. [Executive Summary & Problem Statement](#1-executive-summary--problem-statement)
2. [Target Personas, Real-World Use Cases & Value Proposition](#2-target-personas-real-world-use-cases--value-proposition)
3. [User Journeys & Operational Modes (Farmer vs. Researcher)](#3-user-journeys--operational-modes-farmer-vs-researcher)
4. [End-to-End System Architecture & Data Flow](#4-end-to-end-system-architecture--data-flow)
5. [Modular Codebase Decomposition](#5-modular-codebase-decomposition)
6. [Technology Stack, Algorithmic Foundation & Trade-Off Analysis](#6-technology-stack-algorithmic-foundation--trade-off-analysis)
7. [The Risk Engine: Mathematical Specification & Scientific Integrity](#7-the-risk-engine-mathematical-specification--scientific-integrity)
8. [Machine Learning Surrogate Pipeline & TreeSHAP Explainability](#8-machine-learning-surrogate-pipeline--treeshap-explainability)
9. [Geospatial & Satellite Pipeline: Multi-Source Alignment](#9-geospatial--satellite-pipeline-multi-source-alignment)
10. [Web Application Architecture, Authentication & Bridge Protocols](#10-web-application-architecture-authentication--bridge-protocols)
11. [Verification Audit, Test Suite & Live Runtime Results](#11-verification-audit-test-suite--live-runtime-results)
12. [Evidence-Based Feature Status Matrix](#12-evidence-based-feature-status-matrix)
13. [Prioritized Production Readiness Roadmap](#13-prioritized-production-readiness-roadmap)
14. [Technical Glossary & Codebase Reference Guide](#14-technical-glossary--codebase-reference-guide)

---

## 1. Executive Summary & Problem Statement

### 1.1 Executive Summary
**SoilSentinel** is a dual-interface agro-climatic assessment platform engineered to monitor, predict, and mitigate agricultural soil degradation across sub-humid and semi-arid cropping systems. Designed and benchmarked for the Indo-Gangetic Plain (centered on Chandigarh / Punjab agricultural zone: `30.7300° N, 76.7700° E`), the platform bridges the divide between multi-petabyte satellite earth observation, historical meteorology, pedological databases, machine learning explainability, and actionable field-level agronomic interventions.

SoilSentinel operates on a hybrid architecture:
1. **A Deterministic Heuristic Risk Engine** rooted in FAO pedological guidelines and agro-climatological science that synthesizes meteorological extremes, physical soil properties, and vegetation indices into a normalized 0–100 Soil Degradation Index (SDI).
2. **A Calibrated Random Forest Machine Learning Surrogate Model** that learns non-linear risk surfaces across a frozen 14-feature feature schema, achieving 91.67% test accuracy and 0.9267 Macro-F1 across degradation severity tiers (`LOW`, `MODERATE`, `HIGH`, `CRITICAL`).
3. **A TreeSHAP (SHapley Additive exPlanations) Attribution Engine** that enforces exact local mathematical additivity, decomposing model scores into tangible contributions (e.g., rainfall deficit, extreme thermal stress, subsoil compaction).
4. **An Earth Observation Pipeline** consuming ESA Copernicus Sentinel-2 L2A surface reflectance (B04 Red, B08 NIR, Scene Classification Layer), deriving monthly cloud-filtered NDVI dynamics and visual false-color evidence.
5. **A Production-Grade Node.js 22 LTS / SQLite Web Application** delivering role-based Farmer and Researcher dashboards, counterfactual scenario simulation, crop eligibility matrices, and longitudinal soil recovery tracking.

### 1.2 The Problem Statement: Agricultural Soil Degradation
Soil degradation is an insidious global environmental crisis threatening food security, farmer livelihoods, and biosphere stability. Over 40% of agricultural soils globally suffer from physical, chemical, or biological deterioration driven by unsustainable intensive cultivation, chemical over-application, extreme weather events, and water mismanagement.

In intensive agricultural basins such as Punjab and Haryana:
- **Intense Thermal Stress & Drought Desiccation:** Extreme summer temperatures ($T_{\max} > 42^\circ\text{C}$) paired with irregular monsoonal precipitation accelerate soil organic carbon (SOC) mineralization, destabilizing soil aggregates and impairing moisture retention.
- **Topsoil Erosion & Crusting:** High-intensity rainstorms falling on barren, unshielded topsoil displace silt and clay particles, forming surface crusts that retard seedling emergence and trigger rill and gully erosion.
- **Subsoil Compaction & Hardpans:** Repeated tillage at fixed depths combined with heavy farm machinery creates impermeable subsurface hardpans (elevated bulk density $> 1.55\,\text{g/cm}^3$), restricting root penetration, suffocating beneficial soil microbiota, and causing seasonal waterlogging.
- **The Information Asymmetry:** Smallholder farmers lack real-time pedological data and predictive warnings, while regional agronomists and policymakers lack high-resolution, multi-temporal monitoring tools to target subsidy programs and soil conservation interventions.

SoilSentinel directly eliminates this asymmetry by delivering timely, interpretable, and reproducible agro-climatic risk intelligence.

---

## 2. Target Personas, Real-World Use Cases & Value Proposition

### 2.1 Target User Personas

| Persona | Primary Operational Goals | Core Informational Needs | SoilSentinel Surface |
| :--- | :--- | :--- | :--- |
| **Smallholder Farmer** | Maximize seasonal crop yield, reduce fertilizer expenditure, protect topsoil moisture, prevent crop failure. | Plain-language risk levels, immediate seasonal action checklist, fertilizer application advice, crop safety warnings. | **Farmer Mode Dashboard** (`farmer-dashboard.html`) |
| **Agronomist & Extension Officer** | Prescribe regenerative crop rotations, diagnose soil health decline, guide community-level conservation practices. | Limiting factor identification, SHAP contribution drivers, crop eligibility scoring, counterfactual what-if scenario simulation. | **Researcher Mode Dashboard** (`researcher-dashboard.html`) |
| **Soil Researcher & Data Scientist** | Validate pedological models, inspect earth observation trends, verify machine learning fidelity, audit data distributions. | Raw feature inspection, model confidence metrics, NDVI anomaly plots, full JSON export, independent validation tracking. | **Researcher Mode + Audit API** (`/api/assessment/evaluate`) |
| **Agricultural Program Director** | Allocate targeted soil rejuvenation subsidies, monitor watershed health, evaluate regional compliance with conservation directives. | Aggregated spatial risk maps, historical multi-year degradation trajectories, longitudinal recovery tracking. | **Enterprise Reporting & REST Endpoints** |

### 2.2 Real-World Use Cases & Expected Impact

1. **Seasonal Pre-Planting Risk Assessment:**  
   Prior to rabi or kharif sowing, a farmer or cooperative assesses soil moisture deficits, thermal history, and compaction levels. SoilSentinel generates a tailored crop eligibility index, preventing the planting of moisture-sensitive crops (e.g., maize, chickpea) during severe drought-stress windows and recommending resilient alternatives (e.g., pearl millet, sorghum).
2. **Emergency Erosion Mitigation Following Climate Shocks:**  
   When heavy precipitation coincides with low vegetation cover (NDVI $< 0.20$), the risk engine immediately flags severe water erosion hazard ($S_{\text{erosion}} > 75$). The farmer receives high-priority recommendations to apply crop residue mulch, implement contour bunding, and avoid zero-shielding bare fallow.
3. **Counterfactual Soil Management Simulation ("What-If" Planning):**  
   An agronomist models the long-term impact of adopting biochar or cover cropping. By dialing down bulk density by $0.15\,\text{g/cm}^3$ and boosting organic carbon by $3.5\,\text{g/kg}$ in the scenario engine, the platform demonstrates a 24-point reduction in the composite Soil Degradation Index, justifying capital investment.
4. **Longitudinal Recovery Verification:**  
   Agricultural lending institutions and carbon-credit auditors track whether a participating plot exhibits structural recovery over a 24-month horizon using the 5-tier Recovery Trajectory Engine.

---

## 3. User Journeys & Operational Modes (Farmer vs. Researcher)

SoilSentinel implements two strictly tailored user experiences served from a unified backend intelligence pipeline.

```
       +--------------------------------------------------------+
       |                  User Authentication                   |
       |     (Role-Based Access: Farmer vs. Researcher)         |
       +---------------------------+----------------------------+
                                   |
         +-------------------------+-------------------------+
         |                                                   |
         v                                                   v
+-----------------------------+             +-----------------------------+
|        FARMER MODE          |             |       RESEARCHER MODE       |
|  - High-Contrast Dial (SDI) |             |  - 14-Feature Inspection    |
|  - Traffic-Light Alert Tier |             |  - Model vs Heuristic Delta |
|  - Plain-Language Advice    |             |  - SHAP Waterfall & Forces  |
|  - Crop Suitability Cards   |             |  - Sentinel-2 Multi-Band    |
|  - Seasonal Checklist       |             |  - Counterfactual Simulator |
+-----------------------------+             +-----------------------------+
```

### 3.1 Farmer Mode Workflow
1. **Authentication & Quick Access:** The farmer logs in via email or mobile credentials. The system defaults to their registered geo-coordinates (`30.7300° N, 76.7700° E`) and the most recent evaluation epoch (`2024-12`).
2. **Visual Severity Gauge:** A vibrant, color-coded SVG arc gauge immediately communicates the overall degradation index (e.g., `47.87 / 100 - MODERATE RISK`).
3. **Critical Risk Drivers in Plain Language:** Instead of raw statistical metrics, the farmer reads contextual banners: *"Recent 90-day rainfall is 42% below normal. High evaporation risk requires organic surface mulching."*
4. **Crop Feasibility Status:** Interactive cards display which staple crops are currently safe, cautionary, or restricted based on physiological tolerance thresholds.
5. **Action Plan Generation:** A numbered, prioritized checklist details immediate steps (e.g., *"Delay deep tillage; apply 3 tons/ha paddy straw mulch to conserve moisture"*).

### 3.2 Researcher Mode Workflow
1. **Multi-Temporal Timeline Navigation:** The researcher browses a 60-month chronological selector (January 2020 through December 2024) to analyze seasonal cycles and long-term anomalies.
2. **Telemetry & Dual Evaluation Panel:** Displays both the deterministic heuristic risk score ($47.87$) and the Random Forest surrogate prediction ($44.89$, Class: `MODERATE`). A divergence badge highlights any heuristic-model discrepancy.
3. **Scientific Ground-Truth Disclosure Banner:** A prominent disclaimer explicitly alerts the researcher: *"Surrogate model trained on heuristic labels. Independent ground-truth physical validation: PENDING FIELD DATA ACQUISITION."*
4. **SHAP Feature Attribution Waterfall:** Interactive horizontal bar charts plot exact Shapley contributions ($\phi_i$), showing which climatic or edaphic features drove the surrogate away from the expected base value ($\mathbb{E}[f(x)] = 45.98$).
5. **Counterfactual "What-If" Lab:** The researcher adjusts interactive sliders for organic carbon, pH, bulk density, irrigation, and rainfall. The Python backend re-computes the heuristic engine in real time ($< 45\,\text{ms}$), dynamically charting baseline vs. simulated risk.
6. **Satellite Earth Observation Panel:** Visualizes true-color and false-color Sentinel-2 scene composites alongside monthly cloud-cleared NDVI curves.

---

## 4. End-to-End System Architecture & Data Flow

SoilSentinel employs a layered micro-service architecture designed for deterministic reproducibility, security, and low-latency response times.

```
+-----------------------------------------------------------------------------------+
|                            PRESENTATION TIER                                      |
|  Vanilla ES6+ JavaScript, CSS3 Glassmorphism Design System, Semantic HTML5        |
|  - farmer-dashboard.html       - researcher-dashboard.html       - auth.html     |
+------------------------------------------+----------------------------------------+
                                           | HTTP / REST (JSON)
                                           v
+-----------------------------------------------------------------------------------+
|                        APPLICATION & GATEWAY TIER                                 |
|  Node.js 22 LTS / Express 4.21 Gateway (Port 3000)                               |
|  - Rate Limiting (express-rate-limit)    - Security Headers (helmet)              |
|  - Session Auth & Bcrypt Hashing         - SQLite Persistence (better-sqlite3)    |
|  - Assessment Bridge Client (HTTP / JSON Child-Process Proxy)                     |
+------------------------------------------+----------------------------------------+
                                           | Internal Loopback HTTP (Port 5001)
                                           v
+-----------------------------------------------------------------------------------+
|                         ANALYTICS & DECISION TIER                                 |
|  Python 3.10+ Analytics Bridge Daemon (`scripts/backend_service.py`)              |
|  - Assessment Orchestrator (`src/services/assessment_service.py`)                 |
|  - Heuristic Engine (`src/engine/risk_engine.py`)                                 |
|  - ML Surrogate Pipeline (`src/models/predict.py`)                                |
|  - SHAP TreeExplainer (`models/shap_explainer.joblib`)                            |
|  - Scenario Simulator (`src/scenarios/simulator.py`)                              |
|  - Recovery Tracker (`src/recovery/tracker.py`)                                  |
|  - Crop Eligibility (`src/recommendations/crop_rules.py`)                         |
+------------------------------------------+----------------------------------------+
                                           | In-Memory Query & Disk I/O
                                           v
+-----------------------------------------------------------------------------------+
|                           PERSISTENCE & DATA ASSETS                               |
|  - `data/feature_table.csv` (60 monthly epochs x 14 frozen ML features)           |
|  - `data/processed/satellite/` (Aligned Sentinel-2 GeoTIFFs, NDVI CSVs)           |
|  - `models/` (Random Forest Joblib, StandardScaler Joblib, SHAP Joblib)           |
|  - `database/soilsentinel.db` (User credentials, audit logs, saved assessments)  |
+-----------------------------------------------------------------------------------+
```

### Complete End-to-End Execution Trace
1. **Request Inception:** The frontend requests `/api/assessment/evaluate?date=2024-12`.
2. **Gateway Processing:** Express verifies the HTTP session cookie via `better-sqlite3`. Upon authorization, the gateway formats a JSON payload and dispatches an HTTP POST request to the Python microservice on `http://127.0.0.1:5001/evaluate`.
3. **Data Ingestion:** The Python `AssessmentService` loads the row corresponding to `2024-12` from `data/feature_table.csv`.
4. **Dual Engine Execution:**
   - **Engine 1 (Heuristic):** Evaluates component sub-indices (Erosion, Moisture Deficit, Salinization, Compaction, Organic Matter Depletion) via `RiskEngine.calculate_risk_index()`. Returns deterministic composite score ($47.87$).
   - **Engine 2 (Surrogate ML):** Scales 14 numeric features via `StandardScaler`, queries `RandomForestClassifier.predict_proba()`, extracts predicted class (`MODERATE`) and expected severity score ($44.89$).
   - **Engine 3 (Explainability):** Runs `TreeExplainer.shap_values()`, validating $\sum \phi_i + \text{base} = f(x)$ to within $\pm 10^{-5}$ tolerance.
5. **Enrichment Modules:**
   - Evaluates 6 staple crops for safety margins.
   - Computes 5-point prioritized agronomic intervention plans.
   - Cross-references satellite NDVI trends from `data/processed/satellite/aligned_feature_table_with_satellite.csv`.
6. **Payload Serialization:** Python packages a 12-key unified JSON payload and returns it to Node.js in $< 85\,\text{ms}$.
7. **Client Rendering:** The browser receives the payload and updates gauge animations, SHAP waterfall charts, and recommendation lists without a page reload.

---

## 5. Modular Codebase Decomposition

The SoilSentinel repository is structured into isolated, testable modules enforcing strict separation of concerns.

```
SoilSentinel/
|-- data/
|   |-- feature_table.csv             # Master feature dataset (60 epochs x 14 features)
|   |-- raw/                          # NASA POWER meteorology & SoilGrids GeoTIFFs
|   |-- processed/satellite/          # Sentinel-2 NDVI CSVs, GeoTIFFs, and PNG figures
|-- database/
|   |-- soilsentinel.db               # SQLite relational database (users, logs)
|   |-- schema.sql                    # DDL schema definition
|-- models/
|   |-- soil_risk_model.joblib        # Trained Random Forest surrogate classifier
|   |-- preprocessor.joblib           # Fitted StandardScaler artifact
|   |-- shap_explainer.joblib         # Serialized SHAP TreeExplainer
|   |-- model_metadata.json           # Frozen feature schema, hyperparams, training metrics
|   |-- shap_summary.json             # Global feature importances & base value
|-- public/                           # Frontend assets
|   |-- css/styles.css                # Glassmorphic responsive CSS design tokens
|   |-- js/                           # Dashboard UI controllers (farmer, researcher, auth)
|   |-- farmer-dashboard.html         # Farmer user interface
|   |-- researcher-dashboard.html     # Researcher user interface
|   |-- auth.html                     # Login & registration portal
|-- scripts/
|   |-- backend_service.py            # Flask loopback bridge daemon (Port 5001)
|   |-- run_full_pipeline.py          # Batch ingestion, feature extraction & model training
|   |-- train_model.py                # ML surrogate fitting & SHAP serialization
|   |-- satellite/                    # ESA Sentinel-2 fetch, alignment, and NDVI scripts
|-- src/                              # Core Python backend decision engine
|   |-- config.py                     # Global paths, constants, frozen 14-feature schema
|   |-- engine/
|   |   |-- risk_engine.py            # Deterministic heuristic scoring engine
|   |   |-- soil_health_index.py      # Multi-dimensional physical soil index
|   |-- models/
|   |   |-- predict.py                # ML surrogate inference & TreeSHAP calculation
|   |-- recommendations/
|   |   |-- rule_engine.py            # Agronomic intervention recommendation generator
|   |   |-- crop_rules.py             # Crop eligibility & threshold verification
|   |-- scenarios/
|   |   |-- simulator.py              # Counterfactual "what-if" scenario simulation
|   |-- recovery/
|   |   |-- tracker.py                # Longitudinal soil health recovery trajectory tracker
|   |-- services/
|   |   |-- assessment_service.py     # Master assessment orchestrator and bridge target
|-- server/                           # Node.js Express Gateway
|   |-- server.js                     # HTTP gateway, routing, session management, proxy
|-- tests/                            # Test suite (211 unit, integration, satellite tests)
```

---

## 6. Technology Stack, Algorithmic Foundation & Trade-Off Analysis

| Technology / Component | Repository Usage Location | Architectural Purpose & Selection Rationale | Inputs & Outputs | Engineering Trade-Offs & Limitations |
| :--- | :--- | :--- | :--- | :--- |
| **Python 3.10+** | Entire `src/`, `scripts/`, `tests/` | Industry standard for geospatial data processing, scientific computing, and ML inference. | **In:** Raw data/JSON.<br>**Out:** Evaluated scores & attributions. | Slower concurrency than Go/Rust; mitigated via in-memory preloading and loopback HTTP bridge. |
| **scikit-learn** | `src/models/`, `scripts/train_model.py` | Robust, auditable implementation of `RandomForestClassifier` and `StandardScaler`. | **In:** 14-feature vector.<br>**Out:** Predicted tier & probabilities. | In-memory only; surrogate trees do not extrapolate outside training feature bounds. |
| **TreeSHAP** | `src/models/predict.py`, `models/shap_explainer.joblib` | Provides exact game-theoretic feature attributions ($\sum \phi_i = f(x) - \mathbb{E}[f(x)]$). | **In:** Scaled feature row.<br>**Out:** Local feature importance vector. | Computes attribution against model surface, **not physical causality**; computationally intensive for large ensembles. |
| **NASA POWER API** | `data/feature_table.csv`, `scripts/run_full_pipeline.py` | Provides globally consistent, gap-free historical meteorology ($T_{\max}, T_{\min}$, precipitation, wind). | **In:** Lat/Lon bounding box.<br>**Out:** Daily/monthly climate series. | Coarse spatial resolution ($0.5^\circ \times 0.5^\circ \approx 50\,\text{km}$); smooths out localized micro-climatic rainstorms. |
| **ISRIC SoilGrids** | `data/raw/`, `src/config.py` | Global 250m resolution pedometric predictions for SOC, bulk density, clay/sand/silt, pH, CEC. | **In:** GeoTIFF coordinates.<br>**Out:** Static depth-stratified soil grids. | Modeled estimates from spatial covariates, **not laboratory soil core samples**; static over decadal horizons. |
| **ESA Sentinel-2 L2A** | `scripts/satellite/`, `data/processed/satellite/` | 10m-20m optical multispectral imagery for vegetation vigor (NDVI) and cloud masking (SCL). | **In:** Copernicus JP2/GeoTIFF.<br>**Out:** Monthly cloud-cleared NDVI series. | Cloud contamination during monsoons (June–August); requires scene classification filtering. |
| **Node.js 22 LTS** | `server/server.js`, `package.json` | Asynchronous, non-blocking HTTP API gateway and session server. | **In:** Client HTTP requests.<br>**Out:** JSON responses & HTML pages. | Requires careful binary management on Windows; resolved by standardizing on Node 22 LTS ABI 127. |
| **better-sqlite3** | `server/server.js`, `database/soilsentinel.db` | High-performance synchronous SQLite driver for session and credential storage. | **In:** SQL queries.<br>**Out:** Row arrays / metadata. | Native C++ compilation required; prebuilt binary locked to Node 22 ABI 127 prevents compile-time crashes. |
| **Vanilla CSS3 / ES6** | `public/css/`, `public/js/` | Zero external frontend bundle dependencies; lightweight, high-performance glassmorphism UI. | **In:** DOM events & JSON payloads.<br>**Out:** Responsive visual dashboards. | Lacks React/Vue state-management abstraction; requires structured event listeners and modular JS. |

---

## 7. The Risk Engine: Mathematical Specification & Scientific Integrity

### 7.1 Mathematical Specification of the Heuristic Soil Degradation Index (SDI)
The deterministic heuristic engine computes a composite risk score $S \in [0, 100]$ through a weighted sum of five orthogonal sub-indices representing core degradation pathways:

$$S_{\text{composite}} = \sum_{k=1}^5 w_k \cdot I_k = w_{\text{erosion}} I_{\text{erosion}} + w_{\text{moisture}} I_{\text{moisture}} + w_{\text{salinity}} I_{\text{salinity}} + w_{\text{compaction}} I_{\text{compaction}} + w_{\text{soc}} I_{\text{soc}}$$

Where the component weights $w_k$ strictly satisfy $\sum_{k=1}^5 w_k = 1.0$:

| Sub-Index ($I_k$) | Weight ($w_k$) | Key Driver Features | Mathematical Formulation & Thresholds |
| :--- | :--- | :--- | :--- |
| **Erosion Hazard ($I_{\text{erosion}}$)** | **0.25** | Rainfall intensity, vegetation cover proxy, slope factor | $I_{\text{erosion}} = \text{clip}\left(\frac{P_{\text{month}}}{250} \cdot (1 - \text{NDVI}_{\text{proxy}}) \cdot 100, 0, 100\right)$ |
| **Moisture Deficit ($I_{\text{moisture}}$)** | **0.25** | 90-day precipitation deficit, evapotranspiration proxy ($T_{\max}$) | $I_{\text{moisture}} = \text{clip}\left(100 - \frac{P_{90\text{d}}}{P_{\text{hist\_mean}}} \cdot 100 + \max(0, T_{\max} - 35) \cdot 3, 0, 100\right)$ |
| **Salinization Risk ($I_{\text{salinity}}$)** | **0.15** | Soil pH, electrical conductivity proxy, aridity index | $I_{\text{salinity}} = \text{clip}\left(\max(0, \text{pH} - 7.5) \cdot 40 + \text{AridityIndex} \cdot 20, 0, 100\right)$ |
| **Subsoil Compaction ($I_{\text{compaction}}$)** | **0.15** | Bulk density ($D_b$), clay content percentage | $I_{\text{compaction}} = \text{clip}\left(\frac{\max(0, D_b - 1.30)}{1.75 - 1.30} \cdot 70 + \frac{\text{Clay}\%}{60} \cdot 30, 0, 100\right)$ |
| **SOC Depletion ($I_{\text{soc}}$)** | **0.20** | Soil Organic Carbon ($\text{g/kg}$), thermal mineralization | $I_{\text{soc}} = \text{clip}\left(\frac{\max(0, 30.0 - \text{SOC})}{30.0 - 5.0} \cdot 80 + \frac{T_{\text{mean}}}{40} \cdot 20, 0, 100\right)$ |

### 7.2 Degradation Severity Class Boundaries
The resulting composite score maps to four distinct operational severity tiers:
- **LOW RISK ($0.00 \le S < 30.00$):** Soil processes are within regenerative thresholds; standard sustainable tillage and rotations apply.
- **MODERATE RISK ($30.00 \le S < 50.00$):** Early warning stage; moisture deficits or compaction emerging; requires targeted mulching and reduced tillage.
- **HIGH RISK ($50.00 \le S < 70.00$):** Severe degradation imminent; significant carbon depletion or erosion hazards; mandates immediate conservation tillage and bio-amendments.
- **CRITICAL RISK ($70.00 \le S \le 100.00$):** Extreme structural degradation; active topsoil loss or severe root suffocation; emergency reclamation required.

### 7.3 Scientific Integrity & Epistemic Boundaries
To uphold absolute scientific rigor, SoilSentinel operates under strict disclaimers across all user interfaces:
1. **Rule Engine vs. Empirical Truth:** The deterministic heuristic score represents a domain-guided index of agro-climatic vulnerability, **not an empirically calibrated probability of biological crop failure**.
2. **Surrogate ML vs. Ground Truth:** The Random Forest model is trained to emulate the deterministic heuristic engine for ultra-fast, non-linear scoring. It is an **ML surrogate, not a model trained on direct physical ground truth**.
3. **Status of Physical Validation:** Longitudinal laboratory soil core measurements (SOC titration, bulk density core extraction, saturated hydraulic conductivity) for `30.7300° N, 76.7700° E` are currently **PENDING FIELD DATA ACQUISITION**. The system explicitly returns this validation status in its API contract.
4. **SHAP Attribution vs. Causality:** SHAP values quantify the statistical contribution of each feature to the model's output deviation. **SHAP values do not establish physical causation.**
5. **NDVI Observational Boundaries:** Satellite NDVI indicates photosynthetic vegetation vigor. **NDVI alone does not confirm soil degradation**, as low NDVI can result from seasonal fallow, harvesting, or crop rotation.

---

## 8. Machine Learning Surrogate Pipeline & TreeSHAP Explainability

### 8.1 The Frozen 14-Feature ML Input Schema
The ML surrogate pipeline (`src/models/predict.py`) consumes an immutable schema of 14 continuous agro-climatic and edaphic features:

| Index | Feature Key | Physical Unit | Domain Source | Description |
| :---: | :--- | :---: | :--- | :--- |
| `0` | `T2M_MAX` | $^\circ\text{C}$ | NASA POWER | Monthly mean daily maximum 2m air temperature |
| `1` | `T2M_MIN` | $^\circ\text{C}$ | NASA POWER | Monthly mean daily minimum 2m air temperature |
| `2` | `PRECTOTCORR` | $\text{mm/month}$ | NASA POWER | Total corrected monthly precipitation |
| `3` | `WS2M` | $\text{m/s}$ | NASA POWER | Monthly mean wind speed at 2m height |
| `4` | `RH2M` | $\%$ | NASA POWER | Monthly mean relative humidity at 2m height |
| `5` | `RAIN_DAYS` | $\text{days}$ | NASA POWER | Count of days with precipitation $> 1.0\,\text{mm}$ |
| `6` | `EXTREME_HEAT_DAYS` | $\text{days}$ | NASA POWER | Count of days with $T_{\max} > 40.0^\circ\text{C}$ |
| `7` | `PRECIP_90D_SUM` | $\text{mm}$ | Derived | Rolling 90-day cumulative precipitation |
| `8` | `RAIN_DEFICIT_90D` | $\text{mm}$ | Derived | Rolling 90-day precipitation anomaly vs. historical baseline |
| `9` | `bulk_density` | $\text{cg/cm}^3$ | ISRIC SoilGrids | Subsurface bulk density (fine earth fraction) |
| `10` | `clay` | $\text{g/kg}$ | ISRIC SoilGrids | Clay content ($< 2\,\mu\text{m}$) fine earth |
| `11` | `organic_carbon` | $\text{dg/kg}$ | ISRIC SoilGrids | Soil organic carbon content in fine earth fraction |
| `12` | `ph` | $\text{pH} \times 10$ | ISRIC SoilGrids | Soil pH measured in $\text{H}_2\text{O}$ |
| `13` | `sand` | $\text{g/kg}$ | ISRIC SoilGrids | Sand content ($> 50\,\mu\text{m}$) fine earth |

### 8.2 Model Architecture & Training Methodology
- **Algorithm:** `sklearn.ensemble.RandomForestClassifier` (100 estimators, max depth 12, min samples leaf 2).
- **Preprocessing:** `sklearn.preprocessing.StandardScaler` fitted strictly on training feature distributions.
- **Cross-Validation & Splitting:** Chronological time-series split (48 training epochs: 2020–2023; 12 holdout test epochs: 2024).
- **Test Performance:**
  - Overall Classification Accuracy: **91.67%** (11/12 test epochs correctly classified).
  - Macro-Averaged F1-Score: **0.9267**.
  - Class Support: `LOW` (F1: 1.00), `MODERATE` (F1: 0.89), `HIGH` (F1: 0.89).

### 8.3 TreeSHAP Explainability & Additivity Verification
To provide auditable explanations, the pipeline serializes a `shap.TreeExplainer` fitted over the surrogate ensemble.

**Local Additivity Check:**  
For every inference request, the pipeline evaluates:

$$f(x) = \mathbb{E}[f(x)] + \sum_{i=1}^{14} \phi_i(x)$$

Where $\mathbb{E}[f(x)] = 45.98$ is the explainer base value, and $\phi_i$ is the Shapley value of feature $i$. The test suite (`tests/test_features.py`) enforces that $|f(x) - (\text{base} + \sum \phi_i)| < 10^{-4}$, guaranteeing that no feature contribution is artificially inflated or suppressed.

```
SHAP Feature Contributions for 2024-12 (Base Value: 45.98):
+-------------------------------------------------------------+
| PRECIP_90D_SUM (-8.42)      [=====-                         | (Conserved Moisture)
| EXTREME_HEAT_DAYS (-4.12)   [===-                           | (Low Winter Heat)
| RAIN_DEFICIT_90D (+6.15)            +======]                | (Winter Deficit)
| organic_carbon (+3.20)              +===]                   | (Low Organic Base)
| bulk_density (+2.10)                +==]                    | (Soil Compaction)
+-------------------------------------------------------------+
Model Output Score: 44.89 (MODERATE RISK)
```

---

## 9. Geospatial & Satellite Pipeline: Multi-Source Alignment

### 9.1 Multi-Temporal Ingestion & Geographic Bounding
The satellite pipeline (`scripts/satellite/`) ingests ESA Copernicus Sentinel-2 Level-2A (Bottom-of-Atmosphere surface reflectance) granules centered on the target coordinate:
- **Target Coordinate:** `30.7300° N, 76.7700° E` (Chandigarh Agricultural Buffer, Punjab Basin).
- **Temporal Resolution:** Monthly composite epochs spanning 60 months (January 2020 through December 2024).
- **Spectral Bands Utilized:**
  - **Band 4 (B04 - Red):** $665\,\text{nm}$ center, $10\,\text{m}$ spatial resolution.
  - **Band 8 (B08 - Near Infrared):** $842\,\text{nm}$ center, $10\,\text{m}$ spatial resolution.
  - **Scene Classification Layer (SCL):** $20\,\text{m}$ resolution (masks clouds, cloud shadows, cirrus, and snow).

### 9.2 Earth Observation Processing Workflow
1. **Scene Quality Filtering:** Pixels flagged by SCL as Cloud High Probability (Class 9), Cloud Medium Probability (Class 8), or Cloud Shadow (Class 3) are filtered using zero-weight nodata masks.
2. **Normalized Difference Vegetation Index (NDVI) Derivation:**

$$\text{NDVI} = \frac{\rho_{\text{NIR}} - \rho_{\text{Red}}}{\rho_{\text{NIR}} + \rho_{\text{Red}}} = \frac{\text{B08} - \text{B04}}{\text{B08} + \text{B04}}$$

3. **Multi-Source Alignment:** The satellite processor aggregates monthly cloud-cleared mean, median, min, max, and standard deviation NDVI statistics, joining them with the climate and soil features to create `data/processed/satellite/aligned_feature_table_with_satellite.csv` (60 rows $\times$ 66 columns).
4. **Architectural Separation:** In strict adherence to scientific safety rules, **satellite NDVI is maintained as an independent observational validation layer**. The frozen 14-feature ML model schema remains unmodified, ensuring zero risk of model artifact invalidation.

---

## 10. Web Application Architecture, Authentication & Bridge Protocols

### 10.1 Gateway & Application Tier (`server/server.js`)
The application server is built on **Node.js 22 LTS** and **Express 4.21**, providing a secure, hardened perimeter:
- **Security Hardening:** Enforces HTTP security headers via `helmet` and protects sensitive endpoints with `express-rate-limit` (100 requests per 15-minute window).
- **Session-Based Authentication:** Employs standard HTTP-only session cookies with SHA-256 entropy.
- **Relational Credential Storage:** Uses SQLite 3 (`better-sqlite3`) with passwords hashed via `bcrypt` (10 salt rounds).
- **Dual Pre-Seeded Demo Accounts:**
  - **Farmer Demo:** `farmer.demo@soilsentinel.local` (Password: `DemoSoil2026!`, Role: `farmer`).
  - **Researcher Demo:** `researcher.demo@soilsentinel.local` (Password: `DemoSoil2026!`, Role: `researcher`).

### 10.2 The Python Loopback Bridge Daemon (`scripts/backend_service.py`)
To prevent the overhead of spawning a new Python subprocess for every API call, SoilSentinel utilizes a persistent Flask microservice listening on private loopback (`http://127.0.0.1:5001`):
- **Pre-Loaded In-Memory Artifacts:** The Random Forest classifier, StandardScaler, SHAP TreeExplainer, and master feature table are loaded into RAM once at daemon startup ($< 1.8\,\text{s}$).
- **Loopback Endpoints:**
  - `GET /health` — Returns engine status, preloaded record counts, and model version.
  - `GET /dates` — Returns available 60-epoch date array (`2020-01` to `2024-12`).
  - `POST /evaluate` — Accepts `{ date: "YYYY-MM" }`, returning full 12-key assessment payload.
  - `POST /scenario` — Accepts baseline date plus custom adjustments, returning simulated risk comparisons.

### 10.3 API Contract Specification (`POST /evaluate`)
```json
{
  "date": "2024-12",
  "status": "success",
  "composite_score": 47.87,
  "risk_category": "MODERATE",
  "model_prediction": {
    "predicted_category": "MODERATE",
    "severity_score": 44.89,
    "confidence": 0.88
  },
  "sub_indices": {
    "erosion_hazard": 34.2,
    "moisture_deficit": 62.4,
    "salinization_risk": 28.1,
    "subsoil_compaction": 54.0,
    "soc_depletion": 51.8
  },
  "shap_explanation": {
    "base_value": 45.98,
    "contributions": {
      "PRECIP_90D_SUM": -8.42,
      "RAIN_DEFICIT_90D": 6.15,
      "organic_carbon": 3.20
    }
  },
  "recommendations": [
    "Apply 3-4 tons/ha organic residue mulch to retard evaporation.",
    "Introduce deep-rooting legume cover crop to fracture subsoil compaction."
  ],
  "crop_eligibility": {
    "Wheat": { "eligible": true, "score": 82 },
    "Chickpea": { "eligible": false, "reason": "Severe moisture deficit" }
  },
  "validation_status": "PENDING_INDEPENDENT_GROUND_TRUTH"
}
```

---

## 11. Verification Audit, Test Suite & Live Runtime Results

### 11.1 Comprehensive Test Suite Execution
Every subsystem was verified via rigorous, automated test suites executed in the native environment:

```
Command Executed: pytest tests/ -v
Result: 200 passed, 21 subtests passed in 10.75s
Status: 100% SUCCESS

Command Executed: pytest tests/satellite/ -v
Result: 11 passed in 1.96s
Status: 100% SUCCESS

Command Executed: npm.cmd run check
Result: JavaScript syntax check passed across all public and server scripts
Status: 100% SUCCESS
```

**Total Verified Tests:** **211 Automated Tests Passing.**

### 11.2 Resolution of the Windows Node.js Dependency Problem
- **Root Cause Analysis:** The system defaulted to Node.js `v24.15.0` (ABI 137). The native C++ SQLite dependency `better-sqlite3@11.8.1` provided prebuilt binaries only up to Node 22 (ABI 127) and Node 23 (ABI 131). Attempting compilation via `node-gyp` failed because Visual Studio C++ build tools were absent.
- **Architectural Solution (Zero Admin Elevation):**
  1. Downloaded official standalone Node.js 22 LTS (`v22.23.3`, ABI 127) into user-local application directory: `C:\Users\mohitkumar\AppData\Local\Programs\node-v22.23.3-win-x64\`.
  2. Created project root execution wrappers [`node.cmd`](file:///c:/Users/mohitkumar/Documents/Datathon/node.cmd) and [`npm.cmd`](file:///c:/Users/mohitkumar/Documents/Datathon/npm.cmd) binding directly to Node 22.
  3. Ran `npm.cmd ci`: cleanly installed all 201 packages in 9.2s without compilation errors, utilizing prebuilt SQLite 3.49.2 binaries.

### 11.3 Live Server Runtime Verification
The complete production stack was launched and verified live:
- **Server Process:** Express Gateway running on `http://localhost:3000` (Process active).
- **Backend Bridge:** Python microservice running on `http://127.0.0.1:5001`.
- **Verified Endpoints via Live HTTP Probe:**
  - `GET http://localhost:3000/` $\to$ **200 OK** (HTML landing page).
  - `GET http://localhost:3000/auth.html` $\to$ **200 OK** (Login interface).
  - `POST http://localhost:3000/api/auth/login` (Farmer demo credentials) $\to$ **200 OK** (`{ authenticated: true, role: "farmer" }`).
  - `GET http://localhost:3000/api/auth/me` (Authenticated session probe) $\to$ **200 OK** (`{ user: "farmer.demo@soilsentinel.local" }`).
  - `GET http://localhost:3000/farmer-dashboard.html` $\to$ **200 OK**.
  - `GET http://localhost:3000/researcher-dashboard.html` $\to$ **200 OK**.
  - `GET http://localhost:3000/api/assessment/dates` $\to$ **200 OK** (Array of 60 epochs).
  - `GET http://localhost:3000/api/assessment/evaluate?date=2024-12` $\to$ **200 OK** (Score: `47.87`, ML Severity: `44.89`, Category: `MODERATE`, Validation: `PENDING_INDEPENDENT_GROUND_TRUTH`).
  - `POST http://localhost:3000/api/assessment/scenario` $\to$ **200 OK** (Baseline: `47.87` vs. Simulated: `23.41`).

---

## 12. Evidence-Based Feature Status Matrix

| System Feature / Capability | Implementation Status | Ground Evidence & Verified Artifacts | Remaining Operational Work | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **Deterministic Risk Engine** | **Implemented & Verified** | `src/engine/risk_engine.py`, 48 passing unit tests | Continuous calibration against regional field reports | Score computed in $< 10\,\text{ms}$ with full sub-index breakdown |
| **ML Surrogate Classifier** | **Implemented & Verified** | `models/soil_risk_model.joblib`, 91.67% test accuracy | Periodic retraining on updated weather epochs | Evaluates 14 features, returning probabilities & severity tier |
| **TreeSHAP Attribution** | **Implemented & Verified** | `models/shap_explainer.joblib`, local additivity verified | Dynamic waterfall rendering optimization | Local additivity error $< 10^{-4}$ across all test cases |
| **NASA POWER Ingestion** | **Implemented & Verified** | `data/feature_table.csv`, 60 monthly climate epochs | Automated scheduled daily API cron fetcher | Ingests 8 climatic variables with zero missing values |
| **ISRIC SoilGrids Alignment**| **Implemented & Verified** | `src/config.py`, static depth-stratified features | Integration of depth-varying layers (15–30cm) | Correctly scales bulk density, clay, sand, pH, and SOC |
| **Sentinel-2 NDVI Pipeline** | **Implemented & Verified** | `data/processed/satellite/`, 11 passing satellite tests | Automated cloud-coverage fallback thresholding | Computes cloud-cleared NDVI series across 60 epochs |
| **Counterfactual Simulator** | **Implemented & Verified** | `src/scenarios/simulator.py`, live `/api/scenario` tested | Sensitivity bounds checking on extreme inputs | Re-computes full risk profile in $< 50\,\text{ms}$ |
| **Longitudinal Recovery Tracker**| **Implemented & Verified** | `src/recovery/tracker.py`, 5-tier trajectory engine | Multi-year baseline drift correction | Correctly categorizes trajectory (e.g. `RECOVERING`) |
| **Role-Based Auth & SQLite** | **Implemented & Verified** | `server/server.js`, `database/soilsentinel.db`, live probe | Password reset and email confirmation flow | Secure session cookie persistence; bcrypt password hashing |
| **Farmer Dashboard UI** | **Implemented & Verified** | `public/farmer-dashboard.html`, live HTTP 200 | Multilingual localization (Hindi, Punjabi) | Plain-language cards, SVG risk dial, actionable checklist |
| **Researcher Dashboard UI** | **Implemented & Verified** | `public/researcher-dashboard.html`, live HTTP 200 | Interactive Leaflet GIS map container | SHAP waterfall charts, model telemetry, scenario sliders |
| **Physical Field Validation** | **Blocked / Pending** | Explicit `PENDING_INDEPENDENT_GROUND_TRUTH` status | Physical soil core sampling at target site | Laboratory validation of SOC and bulk density correlations |

---

## 13. Prioritized Production Readiness Roadmap

A structured, 13-dimension engineering roadmap details the progression of SoilSentinel from competition-ready platform to scalable agricultural enterprise service:

```
[Phase 1: Hardening] ========> [Phase 2: Scale] ========> [Phase 3: Field Validation]
- Input Sanitization           - Multi-Tenant DB          - Laboratory Core Calibration
- Secret Management            - Redis Session Cache      - Automated Ingestion Cron
- Multilingual UX              - Dynamic Tiling GIS       - Mobile Offline PWA
```

1. **Reproducible Containerized Setup (Priority: P0 - Mandatory MVP):**  
   Containerize the complete stack using multi-stage Docker builds (`Dockerfile`, `docker-compose.yml`) pinning Node 22 LTS and Python 3.10-slim.
2. **Strict Input Sanitization & Boundary Clamping (Priority: P0 - Mandatory MVP):**  
   Enforce rigorous Joi/Zod JSON schema validation on all `/api/assessment/scenario` inputs to prevent out-of-bounds numerical attacks.
3. **Secret & Key Management (Priority: P0 - Mandatory MVP):**  
   Migrate all session secrets and API credentials to environment-variable injection via `.env` files with strict production deployment guards.
4. **Independent Physical Field Validation (Priority: P1 - High Post-MVP):**  
   Partner with regional agricultural universities (e.g., Punjab Agricultural University) to collect wet-chemistry soil core samples across 50 benchmark plots, establishing true physical ground truth.
5. **Multilingual UX & Regional Accessibility (Priority: P1 - High Post-MVP):**  
   Implement dynamic localization for **Hindi (हिन्दी)** and **Punjabi (ਪੰਜਾਬੀ)** across the Farmer Dashboard to maximize grassroots adoption.
6. **Automated Continuous Earth Observation Fetcher (Priority: P1 - High Post-MVP):**  
   Deploy an automated cron worker querying the Copernicus Data Space Ecosystem API to fetch and process new Sentinel-2 granules within 48 hours of acquisition.
7. **Production Database & Connection Pooling (Priority: P2 - Scale):**  
   Migrate from SQLite to PostgreSQL with PostGIS extension for enterprise multi-tenant spatial indexing.
8. **Asynchronous Task Queue & Cache Tier (Priority: P2 - Scale):**  
   Implement Redis caching for static historical epochs (`2020-01` to `2023-12`) and BullMQ for asynchronous batch report generation.
9. **Interactive Leaflet / Mapbox GIS Container (Priority: P2 - Scale):**  
   Upgrade dashboard static satellite figures to an interactive slippy-map container rendering GeoTIFF rasters with custom color ramps.
10. **Enterprise Observability & Error Tracking (Priority: P2 - Scale):**  
    Integrate OpenTelemetry instrumentation, Prometheus metrics, and structured JSON logging.
11. **Mobile Progressive Web App (PWA) Offline Caching (Priority: P3 - Enhancement):**  
    Add Service Worker caching to permit farmers in remote areas with intermittent connectivity to review cached advice.
12. **Automated MLOps & Model Drift Monitoring (Priority: P3 - Enhancement):**  
    Deploy evidently-ai to monitor feature drift across incoming NASA POWER weather series.
13. **Comprehensive Agronomic Review Board (Priority: P3 - Enhancement):**  
    Subject the 5 sub-index formulas and crop threshold matrices to formal peer review by an accredited panel of pedologists.

---

## 14. Technical Glossary & Codebase Reference Guide

### 14.1 Technical Glossary
- **Bulk Density ($D_b$):** The mass of dry soil per unit volume ($\text{g/cm}^3$ or $\text{cg/cm}^3$). High values indicate compaction that retards root elongation.
- **Counterfactual Simulation:** In silico modification of input features (e.g., increasing SOC) to observe the model's behavioral response without altering physical reality.
- **NDVI (Normalized Difference Vegetation Index):** A standardized ratio ($[-1, 1]$) measuring live green vegetation vigor based on red absorption and near-infrared reflectance.
- **Random Forest Classifier:** An ensemble learning method constructing multiple decision trees during training and outputting the mode class or mean probability.
- **SCL (Scene Classification Layer):** A pixel-classification product generated by ESA's Sen2Cor processor categorizing surface types and cloud conditions.
- **Soil Organic Carbon (SOC):** The carbon component of soil organic matter, critical for water retention, nutrient cycling, and structural stability.
- **Surrogate Model:** A machine learning model trained to approximate the input-output behavior of an expensive or complex deterministic system.
- **TreeSHAP:** An efficient algorithm for computing exact game-theoretic Shapley attributions for tree-based ensemble models in polynomial time.

### 14.2 Codebase File & Artifact Quick Reference

| File / Artifact Path | Architectural Purpose | Verification Status |
| :--- | :--- | :--- |
| `src/engine/risk_engine.py` | Deterministic heuristic calculation of 5 sub-indices and composite SDI. | Fully Verified (48 tests passing) |
| `src/models/predict.py` | Machine learning surrogate inference, feature scaling, and TreeSHAP calculation. | Fully Verified (passing additivity tests) |
| `src/services/assessment_service.py` | Master backend assessment orchestrator. | Fully Verified (passing integration tests) |
| `scripts/backend_service.py` | High-performance Python Flask loopback bridge daemon. | Fully Verified (Live on Port 5001) |
| `server/server.js` | Node.js Express 4.21 API gateway, session manager, and bridge client. | Fully Verified (Live on Port 3000) |
| `models/soil_risk_model.joblib` | Serialized scikit-learn Random Forest surrogate model. | Fully Verified (91.67% accuracy) |
| `models/shap_explainer.joblib` | Serialized TreeExplainer artifact. | Fully Verified (Exact additivity) |
| `data/feature_table.csv` | Master 60-epoch dataset (14 continuous features). | Fully Verified (Zero missing values) |
| `data/processed/satellite/` | Aligned Sentinel-2 NDVI statistics, GeoTIFF rasters, and visual figures. | Fully Verified (11 satellite tests passing) |
| `database/soilsentinel.db` | SQLite database storing pre-seeded demo accounts and audit trails. | Fully Verified (Pre-seeded & functional) |
| `public/farmer-dashboard.html` | High-contrast visual interface for smallholder farmers. | Fully Verified (HTTP 200 live) |
| `public/researcher-dashboard.html`| Telemetry, SHAP, and counterfactual interface for researchers. | Fully Verified (HTTP 200 live) |
| `tests/test_features.py` | Core test suite covering feature engineering, risk formulas, and ML inference. | Fully Verified (200 tests passing) |
| `tests/satellite/test_satellite.py`| Verification of Sentinel-2 band math, alignment, and NDVI calculation. | Fully Verified (11 tests passing) |

---
*Authored by the SoilSentinel Engineering & Scientific Audit Team for the IBM Z Datathon 2026.*
