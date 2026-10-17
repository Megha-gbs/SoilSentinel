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
3. **No False Claims of Risk Engine Integration:** Satellite data has been cleaned, validated, and aligned into a production-ready CSV table. It is **NOT** integrated into the live risk scoring engine until Mohit evaluates and approves an architectural integration option.

---

## 2. Satellite Data Asset Specification

| Specification Field | Technical Asset Detail |
| :--- | :--- |
| **Product Identifier** | Copernicus Sentinel-2 MSI Level-2A (Bottom-of-Atmosphere Surface Reflectance) |
| **Data Provider & Licence**| European Space Agency (ESA) / Copernicus Programme; Open Access (CC BY 4.0) |
| **Primary Variable** | Calibrated Agricultural Parcel NDVI (`satellite_ndvi`), range: $[-1.0, +1.0]$ |
| **Supporting Variables** | `satellite_vegetation_fraction` ($[0, 1]$), `satellite_cloud_cover_percent` ($[0, 100]$), `satellite_quality_flag` |
| **Observation Dates** | January 2020 through December 2024 (60 consecutive monthly observations) |
| **Spatial Resolution** | **10 metres** (Band 4 Red: 665 nm, Band 8 NIR: 842 nm; SCL: 20 m) |
| **Target Coordinates** | Nominal: Latitude `30.7300° N`, Longitude `76.7700° E`<br>Sampled: Latitude `30.7392° N`, Longitude `76.7764° E` |
| **MGRS Tile** | `43RFQ` (Punjab / Indo-Gangetic Plains) |
| **Missing Values / NaNs** | **0 missing values (100% complete across all 60 months).** |
| **Data Quality Profile** | 46 months PRISTINE ($\le 5\%$ cloud), 9 months GOOD, 3 months ACCEPTABLE, 2 months MARGINAL |

---

## 3. Schema Interface & Aligned Table Layout

The delivered table [`data/processed/satellite/aligned_feature_table_with_satellite.csv`](../data/processed/satellite/aligned_feature_table_with_satellite.csv) has dimensions **60 rows $\times$ 61 columns**. It seamlessly extends Mohit's 53-column input schema:

### 3.1 Preserved Baseline Columns (Columns 1–53)
* Columns 1–53 contain the identical column names, physical units, and values as [`sireesha/feature_table.csv`](../sireesha/feature_table.csv).
* **Boundary NaNs Preserved:**
  - `precipitation_lag1_mm_day`: Exactly 1 NaN at index 0.
  - `air_temperature_lag1_c`: Exactly 1 NaN at index 0.
  - `precipitation_rolling_3m_mean_mm_day`: Exactly 2 NaNs at indices 0 and 1.
  - `precipitation_rolling_3m_sum_mm_day`: Exactly 2 NaNs at indices 0 and 1.
  - Mohit's `partial_history_fallback=True` permissive mode and `INSUFFICIENT_HISTORY` strict mode will behave identically as tested.

### 3.2 Appended Satellite Columns (Columns 54–61)
* Column 54: `satellite_ndvi` (`float64`, min: $0.235$, max: $0.822$, mean: $0.584$)
* Column 55: `satellite_vegetation_fraction` (`float64`, min: $0.116$, max: $0.917$)
* Column 56: `satellite_cloud_cover_percent` (`float64`, min: $0.0$, max: $68.22$)
* Column 57: `satellite_quality_flag` (`string`: `QUALITY_PRISTINE`, `QUALITY_GOOD`, etc.)
* Column 58: `satellite_scene_id` (`string`: e.g., `S2B_43RFQ_20200110_1_L2A`)
* Column 59: `satellite_observation_date` (`string`: ISO 8601 UTC timestamp)
* Column 60: `satellite_platform` (`string`: `sentinel-2a` or `sentinel-2b`)
* Column 61: `satellite_data_source` (`string`: `Copernicus Sentinel-2 L2A (ESA)`)

---

## 4. Agronomic Analysis & Risk of Redundancy / Double-Counting

Before Mohit considers modifying the risk engine, he should evaluate the correlation findings from our statistical audit:

1. **High Collinearity with Root-Zone Moisture:**  
   $$\text{Corr}(\text{satellite\_ndvi}, \text{soil\_moisture\_rootzone\_fraction}) = +0.510 \quad (p < 0.0001)$$
   - In Mohit's current scoring engine, root-zone moisture deficit carries a heavy weight of **0.30**.
   - If satellite NDVI is naively added as a "Vegetation Stress" penalty without reducing the moisture weight, the combined hydro-vegetative penalty will overweight drought conditions by double-counting the same underlying physical water deficit.
2. **Delayed Response vs. Atmospheric Rainfall:**  
   $$\text{Corr}(\text{satellite\_ndvi}, \text{precipitation\_mm_day}) = +0.088 \quad (p = 0.50)$$
   $$\text{Corr}(\text{satellite\_ndvi}, \text{precipitation\_lag1\_mm_day}) = +0.478 \quad (p = 0.0001)$$
   - Same-month rainfall deficit does not immediately lower NDVI because canal irrigation and antecedent moisture buffer the crop.
   - Penalizing both instantaneous precipitation deficit and low NDVI in the same month would create artificial volatility during dry spells.

---

## 5. Architectural Integration Options for Mohit's Review

We propose three integration architectures for Mohit's evaluation:

### Option A (Recommended): Independent Observational Validation Layer
* **Architecture:** Leave `risk_scoring.py` scoring weights completely unchanged.
* **Mechanism:** Use `satellite_ndvi` as an independent observational cross-check in model audit logs and dashboards:
  - If Risk Score is **HIGH** (e.g., > 65) but Satellite NDVI remains **HIGH** (> 0.70), flag audit log: `STRESS_MITIGATED_BY_CANAL_IRRIGATION`.
  - If Risk Score is **HIGH** and Satellite NDVI is **LOW** (< 0.40), flag audit log: `CONFIRMED_CANOPY_SENESCENCE`.
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

### Option C: Antecedent Crop Health Modifier in Outlook Projections
* **Architecture:** Integrate satellite NDVI into [`outlook.py`](../Datathon/src/Model/outlook.py).
* **Mechanism:** Use recent 3-month NDVI trend ($\Delta\text{NDVI}$) to adjust the slope of rolling 3-month risk projections. If vegetation is vigorous and healthy heading into summer, damp vulnerability projections by $10\%$.
* **Advantage:** Preserves static scoring engine while enriching forward-looking advisory.

---

## 6. Decisions Requiring Mohit's Explicit Approval

The following architectural choices are formally transferred to Mohit:
1. **Decision 1:** Selection of Integration Architecture (Option A, Option B, or Option C).
2. **Decision 2:** Whether to incorporate `aligned_feature_table_with_satellite.csv` into the automated CI/CD test suite on IBM LinuxONE (`s390x`).
3. **Decision 3:** Confirmation of whether Bhuvan AWiFS manual login token will be pursued or if Copernicus Sentinel-2 Level-2A is adopted as the primary operational spaceborne feed.
