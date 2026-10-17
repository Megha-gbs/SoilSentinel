# SoilSentinel — Existing Project & Data Asset Inventory

**Audit Date:** October 2026  
**Workspace:** Repository Root (`.`)  
**Git Baseline Commit:** `6905aa3` (Branch: `main`, Active Development Branch: `satellite-research`)  
**Data Custodian:** Sireesha / Data Engineering Team  
**Backend & Risk Engine Custodian:** Mohit  

---

## 1. Executive Summary

A comprehensive forensic audit of the `SoilSentinel` workspace was conducted prior to executing any satellite research, feature extraction, or reporting activities. All existing data assets, configuration files, preprocessing scripts, and schemas have been inventoried, classified, and protected under Git version control.

Every file in the baseline `sireesha/` directory has been verified for SHA-256 integrity to ensure zero unintentional modification, deletion, or corruption during downstream tasks.

---

## 2. Master Asset Inventory Table

| Asset Path | Asset Category | File Type | Size (Bytes) | SHA-256 Checksum | Dimensions / Contents | Provenance & Role |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `sireesha/settings.yaml` | Configuration | YAML | 1,634 | `bf0d8db62cc4adbe6f8ed379a109eafb4d0c2a3fd18f9ac086f9129a3f9b535c` | 49 lines | Project configuration defining study region (30.73° N, 76.77° E, 2020–2024), API endpoints, parameters, and paths. |
| `sireesha/data_dictionary.md` | Documentation | Markdown | 33,942 | `998948ba3c4646118348556f9261312fc47fce668323e25afdf9550f2073ec35` | 509 lines | Authoritative schema definition for 53 feature table columns, physical bounds, NaN policies, and provenance definitions. |
| `sireesha/raw/climate/nasa_power_monthly_2020_2024_30.73_76.77.json` | Raw Data | JSON | 11,302 | `1b5bdb290bf9f85856ef7db4723549ead6a3bc9c92dd52377d205dea7b599973` | 60 monthly steps + annual summary | Original untouched API payload from NASA POWER Agroclimatology API (`T2M`, `RH2M`, `PRECTOTCORR`, `GWETTOP`, `GWETROOT`, `TSOIL1`). |
| `sireesha/raw/soil/soilgrids_raw_metadata.json` | Raw Metadata | JSON | 7,710 | `1ad9867748ad62dcb47f72ff198d35cddcd4ec0796275aa74ae03aafa7514941` | 15 layer records (5 properties × 3 depths) | Original query metadata and sampled DN values from ISRIC SoilGrids v2.0 VRT streaming service, including radial search result. |
| `sireesha/processed/climate_data.csv` | Processed Data | CSV | 8,620 | `1717a03b81ce8f70b8250f16d7e9ae4dd628f3147f039c098377306f0daa89f7` | 60 rows × 15 cols | Validated monthly time series (2020-01 to 2024-12) of air and soil climate parameters with physical unit conversions. |
| `sireesha/processed/soil_data.csv` | Processed Data | CSV | 532 | `5520ec2d1fe46496eebebae39885226897087597d91455a17db419a87cf1cdb0` | 3 rows × 12 cols | Validated layer-specific soil baseline measurements (0-5cm, 5-15cm, 15-30cm) for pH, clay, sand, silt, and SOC in physical units. |
| `sireesha/processed/combined_features.csv` | Processed Data | CSV | 17,260 | `c86e71ac076eb712f72c78d0c151187c4a61fb836a3b45438520d474a498bc16` | 60 rows × 38 cols | Aligned dataset merging monthly climate observations with repeated depth-weighted topsoil baseline features and layer features. |
| `sireesha/feature_table.csv` | Final Processed | CSV | 24,705 | `d3119908e43680d8482b2df6d5dccc1389ab0f1ad91b59e8c8a058f2a867215a` | 60 rows × 53 cols | Master feature table ready for ML / risk scoring. Includes seasonal encodings, lag features, aridity indices, and texture ratios. |
| `sireesha/features.py` | Pipeline Script | Python | 9,905 | `27f84497f3c4707db030cdac2802b32935a4a4073187e9897a475d4325d0216a` | 241 lines | Feature engineering module: chronological checks, seasonal mappings, lag calculations, interaction indices, and validation. |
| `sireesha/data_collection/nasa_power.py` | Pipeline Script | Python | 12,704 | `bb604dedd867ed1e30f78e96b73488da40a339b73b11f7cf62e8cdac1b796d60` | 270 lines | NASA POWER data ingestion client with automatic retry logic, -999 fill value handling, and physical bounds validation. |
| `sireesha/data_collection/soilgrids.py` | Pipeline Script | Python | 13,730 | `72e62a82f04288088a52c4bff0a99c35e9c299536bbd3a6071ee6df393b8b309` | 315 lines | ISRIC SoilGrids client with VRT streaming over HTTP (/vsicurl/), Goode Homolosine reprojection, and radial search for urban masking. |
| `sireesha/data_collection/download_all.py` | Pipeline Script | Python | 7,824 | `8e5052dcec4c16f775f4b2c276c0c20616d850526cdcf7348b07a09c3ca78cee` | 196 lines | End-to-end orchestration runner executing data collection, preprocessing, and feature engineering. |
| `sireesha/Preprocessing/clean_data.py` | Pipeline Script | Python | 2,564 | `fff0a94f73428430d75ae978b101cfccd4a3a2cbb38424848847fc983e6ce3ff` | 57 lines | Standardizes types, date formats, precision, and deduplicates records. |
| `sireesha/Preprocessing/merge_data.py` | Pipeline Script | Python | 9,314 | `ea137a766938b3e303638d6c5325647f6e1780d042716c1cfd96bc9987d4ea6a` | 224 lines | Merges climate time series and soil baselines; computes depth-weighted topsoil averages (0-30cm). |
| `sireesha/Preprocessing/validate_data.py` | Pipeline Script | Python | 9,892 | `7257264c5495cbf112a4ebc245e0a71ee6f001bb5e5de83c9c74b03d76bb11de` | 213 lines | Schema validation, physical bounds checks, and exact NaN boundary audits. |

---

## 3. Supplementary External Team Assets Audited

The Datathon project archive (`Datathon IBM`) was also inspected to understand the complete end-to-end system context:

1. **Backend & Risk Scoring Module (`Datathon/src/Model/`):**
   - `risk_scoring.py`: Implements the *Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index* ($0–100$ scale). Uses 5 weighted indicators: Moisture Deficit (0.30), Precipitation Deficit (0.25), Thermal Stress (0.15), SOC Depletion (0.15), and pH Deviation (0.15).
   - `predict.py`: Evaluates feature table in permissive vs strict modes.
   - `audit_log.py`: Generates regulatory audit trails for predictions.
   - `outlook.py`: Provides 3-month rolling agricultural risk projections.
2. **Model Artifacts (`Datathon/models/`):**
   - `soil_risk_model.joblib`: Persisted rule-based risk model artifact.
3. **Hardware Deployment Docs (`Datathon/docs/`):**
   - `linuxone_deployment.md`: Guidelines for running pure Python/NumPy on IBM LinuxONE (s390x) mainframe architecture.
4. **Concept Document:**
   - `Soil_Intelligence_Crop_Advisor_Concept_Document.docx` (in `Downloads`, text extracted to [`concept_document.txt`](../concept_document.txt)).

---

## 4. Geographic & Spatial Context Audit

* **Nominal Study Point:** Latitude `30.7300° N`, Longitude `76.7700° E` (Chandigarh / Punjab border).
* **Sampled Soil Pixel:** Latitude `30.7392° N`, Longitude `76.7764° E` (1.0 km northeast of nominal point).
* **Rationale for Coordinate Shift:** The nominal coordinate falls in an urbanized built-up zone masked as `NODATA` (`-32768`) in ISRIC SoilGrids v2.0. The automated radial search algorithm relocated the sample to the nearest valid agricultural soil pixel at 1.0 km distance.
* **Spatial Compatibility with NASA POWER:** NASA POWER MERRA-2 and CLSM grids operate on a $0.5^\circ \times 0.625^\circ$ and $0.5^\circ \times 0.5^\circ$ resolution (~$50 \times 50\text{ km}$). Both the nominal and sampled coordinates occupy the exact same reanalysis grid cell.

---

## 5. Data Protection Policy & Working Boundaries

1. **Read-Only Status of Baseline Assets:** No file inside `sireesha/` shall be modified, renamed, or deleted.
2. **Isolated Research Directories:**
   - Research reports: `reports/`
   - Satellite acquisition: `data/raw/satellite/`
   - Satellite processing: `data/processed/satellite/`
   - Satellite scripts: `scripts/satellite/`
   - Visual figures: `figures/satellite/`
   - Automated tests: `tests/satellite/`
3. **Version Control:** All new files are staged and committed to the `satellite-research` Git branch.
