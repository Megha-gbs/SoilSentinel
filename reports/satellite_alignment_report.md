# SoilSentinel — Satellite & In-Situ Feature Alignment Report

**Document Date:** October 2026  
**Module Name:** [`scripts/satellite/align_satellite_data.py`](../scripts/satellite/align_satellite_data.py)  
**Input Datasets:**  
- Baseline Feature Table: [`sireesha/feature_table.csv`](../sireesha/feature_table.csv) (60 rows $\times$ 53 cols)  
- Processed Satellite Dataset: [`data/processed/satellite/satellite_ndvi_monthly_2020_2024.csv`](../data/processed/satellite/satellite_ndvi_monthly_2020_2024.csv) (60 rows $\times$ 35 cols)  
**Aligned Output:** [`data/processed/satellite/aligned_feature_table_with_satellite.csv`](../data/processed/satellite/aligned_feature_table_with_satellite.csv) (60 rows $\times$ 66 cols)  
**Author:** Data Engineering & Remote Sensing Research Team  

---

## 1. Executive Summary & Verification

A mathematically rigorous alignment was performed between the 60-month SoilSentinel feature table and genuine spaceborne Copernicus Sentinel-2 MSI observations.

Both datasets represent the exact same geographic point in the agricultural plains of Punjab (Nominal: $30.7300^\circ\text{ N}, 76.7700^\circ\text{ E}$; Sampled: $30.7392^\circ\text{ N}, 76.7764^\circ\text{ E}$) over the identical 5-year monitoring horizon from January 2020 through December 2024 (`2020-01` to `2024-12`).

All 53 baseline features—including engineered seasonal encodings, lag indicators, aridity indices, and repeated SoilGrids soil properties—were preserved with zero modification. Boundary NaNs in lag and rolling precipitation features were strictly protected against accidental zero-imputation. In addition, missing satellite observations for 5 heavily cloud-contaminated months are preserved strictly as `NaN`, prohibiting synthetic value injection.

---

## 2. Multi-Scale Spatial & Temporal Compatibility Audit

| Compatibility Dimension | Baseline Feature Table | Processed Satellite Dataset | Harmonization & Alignment Protocol |
| :--- | :--- | :--- | :--- |
| **Geographic Focus** | Nominal: `30.73, 76.77`<br>Sampled: `30.7392, 76.7764` | Centered on `30.7392, 76.7764`<br>(Bbox: `[76.770, 30.735, 76.785, 30.745]`) | **Exact Spatial Coincidence:** Bounding box encapsulates the sampled agricultural parcel within MGRS Tile `43RFQ`. |
| **Coordinate Reference** | WGS84 (`EPSG:4326`) | UTM Zone 43N (`EPSG:32643`) projected to WGS84 GeoJSON | Coordinates reprojected to EPSG:4326 decimal degrees. |
| **Spatial Ground Resolution**| NASA POWER: $\sim 50\text{ km}$ grid<br>SoilGrids: $250\text{ m}$ pixel | Sentinel-2 MSI: **$10\text{ m}$** pixel<br>(SCL: $20\text{ m}$) | **Multi-Scale Hierarchy:** High-resolution 10 m satellite observations capture parcel-level canopy vigour nested inside the regional 50 km climate cell. |
| **Temporal Frequency** | Monthly aggregated time steps | Minimum cloud monthly clear-sky capture | **1-to-1 Chronological Alignment:** Single representative cloud-filtered scene selected per calendar month. |
| **Observation Span** | 60 months (`2020-01` to `2024-12`) | 60 months (`2020-01` to `2024-12`) | **Perfect 60-Row Continuity:** Zero gaps, zero duplicate dates, monotonic chronological ordering. |
| **Missing Values Policy** | Lag NaNs preserved at row 0 and rows 0–1 | 5 cloudy months marked as NaN | **Zero-Imputation Prohibited:** Lag NaNs and cloudy satellite NaNs strictly preserved. |

---

## 3. Preservation of Baseline Integrity & Schema Evolution

The baseline schema was expanded by appending 13 dedicated satellite observation attributes, resulting in a **66-column aligned schema**:

```
Baseline Feature Table: 53 Columns
+ 13 Satellite Columns:
  1. satellite_ndvi (Float64, [-1.0, 1.0], NaN for unusable cloudy months)
  2. satellite_ndvi_median (Float64, [-1.0, 1.0])
  3. satellite_ndvi_std (Float64, parcel-level spatial variation)
  4. satellite_valid_pixel_fraction (Float64, [0.0, 1.0])
  5. satellite_cloud_shadow_pixel_fraction (Float64, [0.0, 1.0])
  6. satellite_scl_vegetation_fraction (Float64, [0.0, 1.0])
  7. satellite_scl_bare_soil_fraction (Float64, [0.0, 1.0])
  8. satellite_quality_flag (String: PRISTINE, GOOD, ACCEPTABLE, MARGINAL, UNUSABLE_CLOUDY)
  9. satellite_scene_id (String: Granule identifier, e.g., S2B_43RFQ_20200110_1_L2A)
  10. satellite_observation_date (String: UTC timestamp)
  11. satellite_platform (String: Sentinel-2A / Sentinel-2B)
  12. satellite_processing_method (String: GENUINE_SPECTRAL_L2A_SCL_MASKED_RATIO)
  13. satellite_data_source (String: Copernicus Sentinel-2 Level-2A (ESA))
-----------------------------------------------------------
Total Aligned Dataset Schema: 60 rows × 66 columns
```

### Boundary NaN and Cloudy NaN Preservation Verification
* `precipitation_lag1_mm_day`: **Exactly 1 NaN** at index 0 (`2020-01`).
* `air_temperature_lag1_c`: **Exactly 1 NaN** at index 0 (`2020-01`).
* `precipitation_rolling_3m_mean_mm_day`: **Exactly 2 NaNs** at indices 0 and 1 (`2020-01`, `2020-02`).
* `precipitation_rolling_3m_sum_mm_day`: **Exactly 2 NaNs** at indices 0 and 1 (`2020-01`, `2020-02`).
* `satellite_ndvi`: **Exactly 5 NaNs** corresponding to severe cloud contamination events (`2020-08`, `2022-09`, `2023-01`, `2023-07`, `2024-07`).

---

## 4. Agronomic Redundancy & Double-Counting Safeguards

1. **Separation from Backend Scoring Weights:** The aligned satellite indicators are categorized under observational monitoring. They have **NOT** been inserted into Mohit's backend risk-scoring formula.
2. **Avoiding Atmospheric-Canopy Conflation:**
   - Precipitation (`PRECTOTCORR`) measures atmospheric moisture flux (mm/day).
   - Soil moisture (`GWETROOT`) measures land-surface simulated moisture saturation.
   - Satellite NDVI measures green photosynthetic leaf biomass.
   - While correlated during vegetative growth stages, they represent distinct physical processes. Keeping them distinct prevents double-counting drought stress against crop vigour.

---

## 5. Audit Conclusion

The aligned dataset at [`data/processed/satellite/aligned_feature_table_with_satellite.csv`](../data/processed/satellite/aligned_feature_table_with_satellite.csv) has been validated for schema conformity, row-level temporal matching, spatial precision, and boundary condition preservation.
