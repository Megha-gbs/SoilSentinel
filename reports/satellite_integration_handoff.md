# SoilSentinel — Backend Integration & Technical Handoff Contract

**Document Date:** October 2026  
**Author / Data Engineering Lead:** Data Engineering & Satellite Remote Sensing Team  
**Recipient / Backend & Model Architect:** Mohit (Owner: Risk Engine, Predictive Models, IBM LinuxONE Deployment)  
**Deliverable CSV Reference:** [`data/processed/satellite/aligned_feature_table_with_satellite.csv`](../data/processed/satellite/aligned_feature_table_with_satellite.csv)  
**Status:** Submitted for Architecture Review & Integration Approval  

---

## 1. Executive Summary & Working Boundaries

This handoff contract establishes a formal technical bridge between the Data Engineering / Remote Sensing stream and Mohit's backend risk-scoring engine.

In strict adherence to team boundary protocols:
1. **Zero Modifications to Backend Logic:** The existing risk-scoring engine ([`Datathon/src/Model/risk_scoring.py`](../Datathon/src/Model/risk_scoring.py)), prediction routines ([`predict.py`](../Datathon/src/Model/predict.py)), outlook projections ([`outlook.py`](../Datathon/src/Model/outlook.py)), and regulatory audit trails ([`audit_log.py`](../Datathon/src/Model/audit_log.py)) **have not been modified**.
2. **Zero Modification to Scoring Weights:** The 5 calibrated indicator weights (Moisture Deficit: 0.30, Precipitation Deficit: 0.25, Thermal Stress: 0.15, SOC Depletion: 0.15, pH Deviation: 0.15) remain 100% untouched.
3. **No False Claims of Risk Engine Integration:** Satellite data has been cleaned, validated from genuine spectral rasters, and aligned into a production-ready CSV table. It is **NOT** integrated into the live risk scoring engine until Mohit evaluates and approves an architectural integration option.

---

## 2. Satellite Data Asset Specification

| Specification Field | Technical Asset Detail |
| :--- | :--- |
| **Product Identifier** | Copernicus Sentinel-2 MSI Level-2A (Bottom-of-Atmosphere Surface Reflectance) |
| **Data Provider & Licence**| European Space Agency (ESA) / Copernicus Programme; Open Access (CC BY 4.0) |
| **Primary Variable** | Genuine Spectral Parcel NDVI (`satellite_ndvi`), computed as $(B08 - B04)/(B08 + B04)$ |
| **Supporting Variables** | `satellite_ndvi_median`, `satellite_ndvi_std`, `satellite_valid_pixel_fraction`, `satellite_cloud_shadow_pixel_fraction`, `satellite_scl_vegetation_fraction`, `satellite_scl_bare_soil_fraction`, `satellite_quality_flag` |
| **Observation Dates** | January 2020 through December 2024 (60 consecutive monthly steps) |
| **Spatial Resolution** | **10 metres** (Band 4 Red: 665 nm, Band 8 NIR: 842 nm; SCL: 20 m) |
| **Target Coordinates** | Nominal: Latitude `30.7300° N`, Longitude `76.7700° E`<br>Sampled: Latitude `30.7392° N`, Longitude `76.7764° E` (Offset: 1020m NE, reason: urban mask) |
| **MGRS Tile** | `43RFQ` (Punjab / Indo-Gangetic Plains) |
| **Local Rasters on Disk** | 180 GeoTIFFs stored in `data/raw/satellite/spectral_subsets/` |
| **Missing Values / NaNs** | Exactly **5 cloudy months** (`2020-08`, `2022-09`, `2023-01`, `2023-07`, `2024-07`) have `NaN` due to $>92\%$ cloud cover; 55 months have valid numerical observations. |
| **Data Quality Profile** | 44 months PRISTINE, 7 months GOOD, 3 months ACCEPTABLE, 1 month MARGINAL, 5 months UNUSABLE_CLOUDY |

---

## 3. Schema Interface & Aligned Table Layout

The delivered table [`data/processed/satellite/aligned_feature_table_with_satellite.csv`](../data/processed/satellite/aligned_feature_table_with_satellite.csv) has dimensions **60 rows $\times$ 66 columns**. It seamlessly extends Mohit's 53-column input schema:

### 3.1 Preserved Baseline Columns (Columns 1–53)
* Columns 1–53 contain the identical column names, physical units, and values as [`sireesha/feature_table.csv`](../sireesha/feature_table.csv).
* **Boundary NaNs Preserved:**
  - `precipitation_lag1_mm_day`: Exactly 1 NaN at index 0.
  - `air_temperature_lag1_c`: Exactly 1 NaN at index 0.
  - `precipitation_rolling_3m_mean_mm_day`: Exactly 2 NaNs at indices 0 and 1.
  - `precipitation_rolling_3m_sum_mm_day`: Exactly 2 NaNs at indices 0 and 1.
  - Mohit's `partial_history_fallback=True` permissive mode and `INSUFFICIENT_HISTORY` strict mode will behave identically as tested.

### 3.2 Appended Satellite Columns (Columns 54–66)
* Column 54: `satellite_ndvi` (`float64`, min: $0.235$, max: $0.822$, mean: $0.518$, exactly 5 NaNs for cloudy months)
* Column 55: `satellite_ndvi_median` (`float64`, parcel median NDVI)
* Column 56: `satellite_ndvi_std` (`float64`, parcel spatial standard deviation)
* Column 57: `satellite_valid_pixel_fraction` (`float64`, $[0.0, 1.0]$)
* Column 58: `satellite_cloud_shadow_pixel_fraction` (`float64`, $[0.0, 1.0]$)
* Column 59: `satellite_scl_vegetation_fraction` (`float64`, $[0.0, 1.0]$)
* Column 60: `satellite_scl_bare_soil_fraction` (`float64`, $[0.0, 1.0]$)
* Column 61: `satellite_quality_flag` (`string`: `QUALITY_PRISTINE`, `QUALITY_GOOD`, etc.)
* Column 62: `satellite_scene_id` (`string`: e.g., `S2B_43RFQ_20200110_1_L2A`)
* Column 63: `satellite_observation_date` (`string`: ISO 8601 UTC timestamp)
* Column 64: `satellite_platform` (`string`: `Sentinel-2A` or `Sentinel-2B`)
* Column 65: `satellite_processing_method` (`string`: `GENUINE_SPECTRAL_L2A_SCL_MASKED_RATIO`)
* Column 66: `satellite_data_source` (`string`: `Copernicus Sentinel-2 Level-2A (ESA)`)

---

## 4. Agronomic Analysis & Risk of Redundancy / Double-Counting

Before Mohit considers modifying the risk engine, he should evaluate the correlation findings from our statistical audit:

1. **Moisture Storage Coupling:**  
   $$\text{Corr}(\text{satellite\_ndvi}, \text{soil\_moisture\_rootzone\_fraction}) = +0.2851 \quad (p = 0.035, \text{Spearman } \rho = 0.3823, p = 0.004)$$
   - In Mohit's current scoring engine, root-zone moisture deficit carries a weight of **0.30**.
   - If satellite NDVI is naively added as a "Vegetation Stress" penalty without reducing the moisture weight, the combined hydro-vegetative penalty will overweight drought conditions by double-counting the underlying physical water deficit.
2. **Delayed Response vs. Atmospheric Rainfall:**  
   $$\text{Corr}(\text{satellite\_ndvi}, \text{precipitation\_mm_day}) = +0.1288 \quad (p = 0.35, \text{not significant})$$
   $$\text{Corr}(\text{satellite\_ndvi}, \text{precipitation\_lag1\_mm_day}) = +0.2988 \quad (p = 0.028)$$
   $$\text{Corr}(\text{satellite\_ndvi}, \text{precipitation\_rolling\_3m_mean}) = +0.3840 \quad (p = 0.0045)$$
   - Same-month rainfall deficit does not immediately lower NDVI because canal irrigation and antecedent moisture buffer the crop.
   - Penalizing both instantaneous precipitation deficit and low NDVI in the same month would create artificial volatility during dry spells.

---

## 5. Architectural Integration Options for Mohit's Review

We propose three integration architectures for Mohit's evaluation:

### Option A (Recommended): Independent Observational Validation Layer
* **Architecture:** Leave `risk_scoring.py` scoring weights completely unchanged.
* **Mechanism:** Use `satellite_ndvi` as an independent observational cross-check in model audit logs and dashboards:
  - If Risk Score is **HIGH** (e.g., > 65) but Satellite NDVI remains **HIGH** (> 0.65), flag audit log: `STRESS_MITIGATED_BY_CANAL_IRRIGATION`.
  - If Risk Score is **HIGH** and Satellite NDVI is **LOW** (< 0.35), flag audit log: `CONFIRMED_CANOPY_SENESCENCE`.
  - If Satellite NDVI is **NaN** (`QUALITY_UNUSABLE_CLOUDY`), flag audit log: `OBSERVATION_CLOUD_MASKED_PASSIVE_CLIMATE_ONLY`.
* **Advantage:** Preserves existing pure-NumPy mainframe performance and zero risk of double-counting.

### Option B: Calibrated Canopy Stress Sub-Index with Re-Weighted Engine
* **Architecture:** Add a 6th sub-score: `score_canopy_stress = 100 * (1.0 - normalize(ndvi))`.
* **Proposed Re-Weighting (Sum = 1.00):**
  - Dynamic Moisture Deficit: $0.30 \rightarrow \mathbf{0.25}$
  - Dynamic Precipitation Deficit: $0.25 \rightarrow \mathbf{0.20}$
  - Dynamic Canopy Vigour Deficit (NDVI): $\mathbf{0.15}$
  - Dynamic Thermal Stress: $0.15 \rightarrow \mathbf{0.10}$
  - Static Soil Baseline (SOC + pH): $\mathbf{0.30}$ (unchanged at 0.15 each)
* **Advantage:** Directly integrates spaceborne observations into composite score while maintaining 1.00 sum balance.
* **Requirement:** Must include fallback handling for the 5 cloudy months where `satellite_ndvi` is NaN.

### Option C: Passive REST API Output Layer
* **Architecture:** Retain scoring engine unchanged; append satellite metrics into the FastAPI JSON response (`/api/v1/predict` and `/api/v1/outlook`) as supplementary context for farmers and agronomists.
* **Advantage:** Zero changes to scoring math; immediate visual enrichment in web dashboard.

---

## 6. Decisions Submitted for Mohit's Approval

| Decision Item | Proposed Default | Alternative Option | Status |
| :--- | :--- | :--- | :---: |
| **Integration Architecture** | **Option A (Independent Layer)** | Option B (Re-Weighting) or Option C (API-Only) | **PENDING MOHIT APPROVAL** |
| **Cloudy Month Fallback** | NaN preservation | Climatological monthly normal | **CONFIRMED (NaN)** |
| **Backend Code Edits** | None in current PR | Modify `risk_scoring.py` upon approval | **PROTECTED (NO EDITS)** |
