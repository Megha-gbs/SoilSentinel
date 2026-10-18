# SoilSentinel V6 Global Soil Assessment Product — Phase 1 Project Audit Report

**Date:** 2026-10-18  
**Project:** `SoilSentinel` (Datathon 8 Merged Production Application)  
**Auditor:** Senior ML Engineer, Geospatial Scientist, Computer Vision Engineer & Software Reliability Engineer  
**Audit Purpose:** Comprehensive system audit before data acquisition, camera AI development, multi-task training, and global product integration.  
**Absolute Rules Compliance:** 0 Git operations executed; all historical models (v1–v5, v6_audited) and all 180 original Sentinel-2 GeoTIFF files intact.

---

## 1. Application Architecture & Tech Stack Inventory

### 1.1 Web Frontend & Dashboards
- **Static Frontend Pages:**
  - `index.html`: Public landing page with product overview, architecture diagram, and call-to-actions.
  - `auth.html`: User authentication interface supporting registration and login for two roles: **Farmer** and **Researcher**.
  - `farmer-dashboard.html` / `farmer.html`: Interactive farmer dashboard featuring field assessments, risk indicators, meteorological graphs, and crop recommendations. Currently lacks native camera capture, photo upload, and interactive GPS/map picking workflows.
  - `researcher-dashboard.html`: Advanced scientific dashboard for researchers. Currently displays date-driven evaluations and observations, but lacks direct soil-test upload, multi-task model drill-down, and spatial/temporal validation explorer.
- **Client Scripts & Visuals:**
  - `script.js` (main interaction handling, auth session checks, API calls).
  - `dashboard-visuals.js` (Canvas/SVG chart rendering for rainfall, temperature, and risk metrics).
  - `styles.css` (custom design system, responsive layouts, alert banners, role-tailored color accents).

### 1.2 Backend, APIs & Data Persistence
- **Node.js Web Server (`server.js`):**
  - Framework: Express.js (HTTP port 3000).
  - Security: `helmet`, express-session with secure SQLite session store (`NativeSqliteSessionStore`), bcrypt password hashing (work factor 10–12), `express-rate-limit` on auth endpoints (20 attempts / 15 min), origin validation on mutation routes.
  - Database: SQLite database at `data/soilsentinel.sqlite` (using `better-sqlite3` or `node:sqlite` WAL mode). Stores `users` and `sessions` tables.
  - Python Bridge Interop: Spawns Python bridge service on port 5001 (`python -m src.Model.bridge serve --port 5001`) with automatic fallback to CLI execution (`python -m src.Model.bridge <command>`) if HTTP communication times out.
- **Python ML Backend Service (`src/Model/`):**
  - `src/Model/service.py`: `SoilSentinelService` class providing data ingestion (`data/feature_table.csv`), legacy heuristic scoring (`soil_risk_model.joblib`), SHAP explanation, scenario stress-testing, crop eligibility, and the newly added `get_v6_audited_assessment()`.
  - `src/Model/v6_inference.py`: `SoilSentinelV6AuditedEngine` handling multi-task inference (SOC regression, Salinity classification, Acidity classification, Proxy surrogate) with texture mass conservation and `IsolationForest` domain detection.
  - `src/Model/bridge.py`: CLI and HTTP bridge server (`BridgeHTTPRequestHandler`) exposing `/dates`, `/assessment`, `/scenario`, `/observations`, and `/v6-assessment`.
  - Canonical vs. Duplicate Directories:
    - Canonical backend: `src/` and `src/Model/`.
    - Mirrored/Legacy folders: `backend/Model/` mirrors `src/Model/`; `backend/features.py` mirrors `src/features.py`; `models/bridge.py` mirrors `src/Model/bridge.py`.

---

## 2. Investigation: Are Historical v5 Models Actually Loaded?

**Finding: NO.**
Prior to the V6 audit, inspection of `src/Model/service.py`, `src/Model/model.py`, and `server.js` revealed:
- Historical v5 models in `models/v5_ground_truth/` were **never loaded or invoked** by the active web application.
- The web application strictly loaded legacy v1 models (`models/soil_risk_model.joblib`).
- In Phase 6 of our previous audit, we created `src/Model/v6_inference.py` and bridged `v6_audited_assessment` into `service.py`, but the farmer and researcher frontend pages still do not expose the full multi-task predictions, camera scanning, or GPS retrieval.
- For this next major release, we will package the complete global product in **`models/v6_global_product/`** and connect the full multi-task and computer vision pipeline directly into the web application.

---

## 3. Dataset Inventory, Licenses & Data Integrity

### 3.1 Raw and Processed Datasets
| Dataset | Location | Rows / Horizons | Unique Profiles | Spatial Coordinates | Documented License & Commercial Conditions |
|---|---|---|---|---|---|
| **Global Measured Soil Properties** | `data/processed/global_measured_soil_properties.csv` | 360 | 88 | 84 | WoSIS Snapshot: **CC BY-NC 4.0 (Non-Commercial Flag)**. Lab-measured SOC and pH. |
| **Salinity & Sodicity Ground Truth** | `data/processed/soil_degradation_salinity_alkalinity_ground_truth.csv` | 245 | 44 | 43 | WoSIS Electrical Conductivity ($EC_{e}$): **CC BY-NC 4.0 (Non-Commercial Flag)**. |
| **Climate Time Series** | `data/processed/climate_data.csv` | 60 | N/A (Monthly) | Anantapur (14.68°N, 77.60°E) | NASA POWER: **U.S. Public Domain (Free & Unrestricted Commercial Use)**. |
| **Satellite Integrated Risk** | `data/processed/satellite_integrated_risk_dataset.csv` | 60 | N/A (Monthly) | Anantapur | Combined Sentinel-2 + NASA POWER. Proxy target: `risk_class`. |
| **HWSD2 Global Soil Context** | `data/raw/fao_hwsd/HWSD2.mdb` | Database | Global 1km | Global | FAO / IIASA: **Free for non-commercial research & education**. |
| **SoilGrids Context** | `data/raw/global_soil/global_soilgrids_benchmarks.json` | Raster stats | Global 250m | Global | ISRIC SoilGrids: **CC BY 4.0 (Commercial use permitted with attribution)**. |
| **LUCAS Soil Specifications** | `data/raw/lucas_esdac/` | Specs & metadata | European union | Europe | European Commission: **Free reuse under Decision 2011/833/EU**. |

### 3.2 Sentinel-2 GeoTIFF Imagery Inventory (Blessi's Original Datasets)
- **Directory:** `data/raw/satellite/spectral_subsets/`
- **Total Rasters:** Exactly **180 GeoTIFF files** (60 B04 red band, 60 B08 near-infrared band, 60 SCL scene classification layer).
- **Date Coverage:** 2020-01 to 2024-12 (monthly 5-year chronological sequence).
- **Integrity Status:** 100% verified intact. Zero files modified, moved, renamed, or deleted.

---

## 4. Current Gaps & Implementation Roadmap for V6 Global Product

1. **Global Data Acquisition (Phase 2 & 3):**
   - Incorporate open global soil observations, SoilGrids context, and NASA POWER climate data into reproducible acquisition and preprocessing pipelines.
   - Formulate clean manifest records with explicit license categorization (distinguishing CC BY, CC BY-NC, Public Domain, ODbL).
2. **Multi-Task Model Suite (Phase 4):**
   - Retrain and package versioned models in `models/v6_global_product/` for:
     - Task A: Soil Organic Carbon regression ($g\text{ }C/kg$).
     - Task B: Soil Salinity classification ($EC \ge 2.0\text{ dS/m}$).
     - Task C: Soil Acidity classification ($pH < 5.5$).
     - Task D: Soil Sodicity ($ESP \ge 15\%$) or erosion risk screening where data exists.
     - Task E: Climate-satellite environmental stress proxy surrogate.
3. **One-Click Camera Workflow (Phase 5):**
   - Implement a lightweight, responsive crop disease and soil surface screening engine in Python (`src/Vision/`).
   - Support image capture / file upload in `farmer-dashboard.html`.
   - Provide clear agronomical explanations: crop symptom detection is biological screening; soil photograph analysis detects surface erosion/crusting/color, and **never** fabricates underground chemical $pH$, $EC$, or $SOC$ values.
4. **GPS Field-Assessment Workflow (Phase 6):**
   - Browser Geolocation API integration + interactive map coordinates picker in `farmer-dashboard.html`.
   - Dynamic location-based retrieval of climatic context (NASA POWER API / Open-Meteo) and soil context (SoilGrids / HWSD).
5. **Full Product Integration & Explainability (Phases 7, 8, 9 & 10):**
   - Real-time endpoints in `server.js` and `src/Model/bridge.py`.
   - Multi-language accessibility (English, Telugu, Hindi) and voice-prompt support.
   - Researcher workspace in `researcher-dashboard.html` with soil-test upload, validation metrics, and SHAP explainability.
   - Geographic applicability and domain boundaries layer.
6. **Testing & Deliverables (Phases 11 & 12):**
   - Full regression and end-to-end test suite (`pytest`) verifying all components.
