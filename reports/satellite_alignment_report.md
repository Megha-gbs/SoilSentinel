# SoilSentinel — Satellite & In-Situ Feature Alignment Report

**Document Date:** October 2026  
**Module Name:** [`scripts/satellite/align_satellite_data.py`](../scripts/satellite/align_satellite_data.py)  
**Input Datasets:**  
- Baseline Feature Table: [`sireesha/feature_table.csv`](../sireesha/feature_table.csv) (60 rows $\times$ 53 cols)  
- Processed Satellite Dataset: [`data/processed/satellite/satellite_ndvi_monthly_2020_2024.csv`](../data/processed/satellite/satellite_ndvi_monthly_2020_2024.csv) (60 rows $\times$ 20 cols)  
**Aligned Output:** [`data/processed/satellite/aligned_feature_table_with_satellite.csv`](../data/processed/satellite/aligned_feature_table_with_satellite.csv) (60 rows $\times$ 61 cols)  
**Author:** Data Engineering & Remote Sensing Research Team  

---

## 1. Executive Summary & Verification

A mathematically rigorous alignment was performed between the 60-month SoilSentinel feature table and genuine spaceborne Copernicus Sentinel-2 MSI observations.

Both datasets represent the exact same geographic point in the agricultural plains of Punjab (Nominal: $30.7300^\circ\text{ N}, 76.7700^\circ\text{ E}$; Sampled: $30.7392^\circ\text{ N}, 76.7764^\circ\text{ E}$) over the identical 5-year monitoring horizon from January 2020 through December 2024 (`2020-01` to `2024-12`).

All 53 baseline features—including engineered seasonal encodings, lag indicators, aridity indices, and repeated SoilGrids soil properties—were preserved with zero modification. Boundary NaNs in lag and rolling precipitation features were strictly protected against accidental zero-imputation.

---

## 2. Multi-Scale Spatial & Temporal Compatibility Audit

| Compatibility Dimension | Baseline Feature Table | Processed Satellite Dataset | Harmonization & Alignment Protocol |
| :--- | :--- | :--- | :--- |
| **Geographic Focus** | Nominal: `30.73, 76.77`<br>Sampled: `30.7392, 76.7764` | Centered on `30.7392, 76.7764`<br>(Bbox: `[76.770, 30.735, 76.785, 30.745]`) | **Exact Spatial Coincidence:** Bounding box encapsulates the sampled agricultural parcel within MGRS Tile `43RFQ`. |
| **Coordinate Reference** | WGS84 (`EPSG:4326`) | UTM Zone 43N (`EPSG:32643`) projected to WGS84 GeoJSON | Coordinates reprojected to EPSG:4326 decimal degrees. |
| **Spatial Ground Resolution**| NASA POWER: $\sim 50\text{ km}$ grid<br>SoilGrids: $250\text{ m}$ pixel | Sentinel-2 MSI: **$10\text{ m}$** pixel<br>(SCL: $20\text{ m}$) | **Multi-Scale Hierarchy:** High-resolution 10 m satellite observations capture parcel-level canopy vigour nested inside the regional 50 km climate cell. |
| **Temporal Frequency** | Monthly aggregated time steps | Minimum cloud monthly clear-sky capture | **1-to-1 Chronological Alignment:** Single representative cloud-filtered scene selected per calendar month. |
| **Observation Span** | 60 months (`2020-01` to `2024-12`) | 60 months (`2020-01` to `2024-12`) | **Perfect 60-Row Continuity:** Zero gaps, zero duplicate dates, monotonic chronological ordering. |
| **Missing Values Policy** | Lag NaNs preserved at row 0 and rows 0–1 | Complete series (0 NaNs across all 60 satellite records) | **Zero-Imputation Prohibited:** Lag NaNs preserved; satellite data complete. |

---

## 3. Preservation of Baseline Integrity & Schema Evolution

The baseline schema was expanded by appending 8 dedicated satellite observation attributes, resulting in a 61-column aligned schema:

```
Baseline Feature Table: 53 Columns
+ 8 Satellite Columns:
  1. satellite_ndvi (Float64, [-1.0, 1.0])
  2. satellite_vegetation_fraction (Float64, [0.0, 1.0])
  3. satellite_cloud_cover_percent (Float64, [0.0, 100.0])
  4. satellite_quality_flag (String: PRISTINE, GOOD, ACCEPTABLE, MARGINAL)
  5. satellite_scene_id (String: Granule identifier)
  6. satellite_observation_date (String: UTC timestamp)
  7. satellite_platform (String: sentinel-2a / sentinel-2b)
  8. satellite_data_source (String: Copernicus Sentinel-2 L2A)
-----------------------------------------------------------
Total Aligned Dataset Schema: 60 rows × 61 columns
```

### Boundary NaN Preservation Verification
* `precipitation_lag1_mm_day`: **Exactly 1 NaN** at index 0 (`2020-01`).
* `air_temperature_lag1_c`: **Exactly 1 NaN** at index 0 (`2020-01`).
* `precipitation_rolling_3m_mean_mm_day`: **Exactly 2 NaNs** at indices 0 and 1 (`2020-01`, `2020-02`).
* `precipitation_rolling_3m_sum_mm_day`: **Exactly 2 NaNs** at indices 0 and 1 (`2020-01`, `2020-02`).
* All other 57 columns (including all 8 new satellite features) contain **0 missing values (100% complete)**.

---

## 4. Agronomic Redundancy & Double-Counting Safeguards

1. **Separation from Backend Scoring Weights:** The aligned satellite indicators are categorized under observational monitoring. They have **NOT** been inserted into Mohit's backend `Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index` formula.
2. **Avoiding Atmospheric-Canopy Conflation:**
   - Precipitation (`PRECTOTCORR`) measures atmospheric moisture flux (mm/day).
   - Soil moisture (`GWETROOT`) measures land-surface simulated moisture saturation.
   - Satellite NDVI measures green photosynthetic leaf biomass.
   - While correlated during vegetative growth stages, they represent distinct physical processes. Keeping them distinct prevents double-counting drought stress against crop vigour.

---

## 5. Audit Conclusion

The aligned dataset at [`data/processed/satellite/aligned_feature_table_with_satellite.csv`](../data/processed/satellite/aligned_feature_table_with_satellite.csv) has been validated for schema conformity, row-level temporal matching, spatial precision, and boundary condition preservation.
