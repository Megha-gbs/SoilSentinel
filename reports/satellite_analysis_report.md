# SoilSentinel — Exploratory Climate & Satellite Vegetation Analysis Report

**Document Date:** October 2026  
**Investigator:** Data Engineering & Remote Sensing Research Team  
**Dataset Reference:** [`data/processed/satellite/aligned_feature_table_with_satellite.csv`](../data/processed/satellite/aligned_feature_table_with_satellite.csv)  
**Study Horizon:** January 2020 through December 2024 (60 consecutive monthly steps)  
**Spatial Coordinates:** Nominal: `30.7300° N, 76.7700° E` | Sampled: `30.7392° N, 76.7764° E` (Punjab, India)  

---

## 1. Executive Summary & Core Statistical Findings

An exploratory empirical comparison was performed between spaceborne Normalized Difference Vegetation Index (Copernicus Sentinel-2 MSI NDVI) and atmospheric/hydrological climate variables (NASA POWER MERRA-2 and Catchment Land Surface Model).

The analysis reveals three major scientific insights:
1. **Pronounced Hydrological Lag Coupling ($p < 0.0001$):** Same-month precipitation shows virtually no linear correlation with NDVI ($r = 0.088, p = 0.503$). In contrast, **1-month lagged precipitation** ($r = 0.478, p = 0.0001$) and **3-month rolling precipitation** ($r = 0.469, p = 0.0002$) exhibit strong, highly significant positive relationships with vegetation vigour.
2. **Robust Moisture Storage Coupling ($r > 0.51, p < 10^{-4}$):** Simulated root-zone soil wetness fraction (`GWETROOT`) and surface soil wetness (`GWETTOP`) correlate strongly with NDVI ($r = 0.510$ and $r = 0.535$ respectively).
3. **Bi-Modal Cropping Phenology:** Satellite NDVI captures the dual-crop annual cycle characteristic of the Indo-Gangetic Plains (winter Rabi wheat peak in February/March, summer post-harvest stubble minimum in May/June, and monsoon Kharif paddy peak in August/September).

---

## 2. Statistical Correlation Matrix

The table below summarizes both parametric (Pearson $r$) and non-parametric rank (Spearman $\rho$) correlation coefficients against `satellite_ndvi` across the 60-month time series:

| Climate / Hydrological Variable | Physical Units | Sample Size ($n$) | Pearson $r$ | Pearson $p$-value | Spearman $\rho$ | Spearman $p$-value | Statistical Significance |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Surface Soil Wetness (`GWETTOP`)** | Fraction $[0, 1]$ | 60 | **$+0.535$** | **$< 0.0001$** | **$+0.548$** | **$< 0.0001$** | Statistically Highly Significant ($p < 0.001$) |
| **Root-Zone Soil Wetness (`GWETROOT`)** | Fraction $[0, 1]$ | 60 | **$+0.510$** | **$< 0.0001$** | **$+0.560$** | **$< 0.0001$** | Statistically Highly Significant ($p < 0.001$) |
| **1-Month Lagged Precipitation** | mm/day | 59 | **$+0.478$** | **$0.0001$** | **$+0.512$** | **$< 0.0001$** | Statistically Highly Significant ($p < 0.001$) |
| **3-Month Rolling Mean Precipitation** | mm/day | 58 | **$+0.469$** | **$0.0002$** | **$+0.459$** | **$0.0003$** | Statistically Highly Significant ($p < 0.001$) |
| **Soil-Air Temperature Gradient** | °C | 60 | **$-0.279$** | **$0.0308$** | $-0.212$ | $0.1039$ | Significant at 5% level ($p < 0.05$) |
| **Monthly De Martonne Aridity** | Dimensionless | 60 | $+0.123$ | $0.3486$ | $+0.148$ | $0.2589$ | Not Significant ($p > 0.05$) |
| **Air Temperature (`T2M`)** | °C | 60 | $-0.121$ | $0.3567$ | $-0.179$ | $0.1722$ | Not Significant ($p > 0.05$) |
| **Topsoil Temperature Layer 1 (`TSOIL1`)**| °C | 60 | $-0.136$ | $0.2989$ | $-0.182$ | $0.1645$ | Not Significant ($p > 0.05$) |
| **Same-Month Precipitation** | mm/day | 60 | $+0.088$ | $0.5029$ | $+0.125$ | $0.3398$ | Not Significant ($p > 0.05$) |

---

## 3. Agronomic Interpretation of Observed Patterns

### 3.1 The 1-to-3 Month Precipitation Response Lag
In the semi-arid, canal- and tube-well-irrigated wheat-paddy cropping system of Punjab:
* An instantaneous rainfall event does not produce immediate vegetative canopy expansion. Crops require time to absorb infiltrated root-zone water, stimulate cell elongation, and expand photosynthetic leaf area index (LAI).
* During the pre-monsoon dry season (May–June), sporadic thunderstorms occur, but fields remain mostly fallow or in early nursery preparation.
* As monsoon rains saturate the regional Catchment Land Surface Model hydrology across July and August, the Kharif paddy crop reaches maximum vegetative canopy in late August and September ($r = 0.478, p = 0.0001$).

### 3.2 Seasonal Dynamics Across the Punjab Agro-Climatic Calendar

| Agro-Climatic Season | Months Included | Observation Count | Mean NDVI | Min NDVI | Max NDVI | Agronomic Stage Description |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Monsoon (Kharif)** | Jun, Jul, Aug, Sep | 20 | **0.603** ($\pm 0.188$) | 0.235 | **0.822** | Paddy transplanting in June/July; maximum canopy vigour in August/September. |
| **Post-Monsoon (Autumn)**| Oct, Nov | 10 | **0.614** ($\pm 0.090$) | 0.508 | 0.754 | Paddy harvest, stubble clearing/burning transition, early Rabi sowing. |
| **Winter (Rabi)** | Dec, Jan, Feb | 15 | **0.556** ($\pm 0.116$) | 0.261 | 0.654 | Wheat tillering, crown root initiation, and jointing under cooler winter temperatures. |
| **Summer / Pre-Monsoon** | Mar, Apr, May | 15 | **0.540** ($\pm 0.112$) | 0.370 | 0.727 | Wheat heading in March, ripening and harvest in April; bare fallow in May. |

---

## 4. Annual Trajectory & Drought Stress Signal Audit (2020–2024)

* **2020 (Favorable Hydrology):** Mean NDVI = **$0.629$**. Supported by consistent winter and monsoon precipitation (annual mean precipitation: $3.94\text{ mm/day}$).
* **2021 (Stable Baseline):** Mean NDVI = **$0.580$**. Standard dual-peak phenology.
* **2022 (Severe Summer Heatwave):** Mean NDVI = **$0.574$**. March 2022 experienced unprecedented pre-monsoon heatwave ($T2M$ reached $26.8^\circ\text{C}$, $+4.5^\circ\text{C}$ above normal), triggering premature wheat senescence and an early summer NDVI plunge to $0.267$ in June 2022.
* **2023 (Monsoon Flood Event):** Mean NDVI = **$0.583$**. July 2023 recorded extreme flooding in Punjab (precipitation peak: $18.70\text{ mm/day}$); satellite observations captured subsequent peak paddy expansion in September ($0.806$).
* **2024 (Late Monsoon Vigour):** Mean NDVI = **$0.520$** (range: $0.235$ in July to $0.822$ in September). Strong late Kharif greening.

---

## 5. Critical Scientific Safeguards & Prohibitions

1. **Correlation Does Not Establish Causation:** A high correlation ($r = 0.535$) between satellite NDVI and root-zone moisture reflects coupled seasonal co-variation, NOT proof that higher NDVI directly increased soil moisture or that moisture was the sole driver of growth (irrigation and fertilizer applications were also primary drivers).
2. **NDVI Is Not a Direct Soil Health Measurement:** Spaceborne NDVI measures photosynthetic activity of the vegetative canopy. It does **NOT** measure soil organic carbon, soil texture, microbial activity, or chemical cation exchange capacity. Treating NDVI as a soil test would be scientifically invalid.
3. **No Unsubstantiated Predictive Claims:** While satellite NDVI provides valuable retrospective monitoring evidence, it has not been validated as a predictive risk indicator. It should remain an independent observational layer unless approved by Mohit for backend scoring.
