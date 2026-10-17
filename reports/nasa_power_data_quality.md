# SoilSentinel — NASA POWER Data Quality & Reanalysis Audit Report

**Audit Date:** October 2026  
**Analyst:** Data Engineering & Remote Sensing Research Team  
**Dataset Reference:** [`sireesha/processed/climate_data.csv`](../sireesha/processed/climate_data.csv)  
**Raw Source Payload:** [`sireesha/raw/climate/nasa_power_monthly_2020_2024_30.73_76.77.json`](../sireesha/raw/climate/nasa_power_monthly_2020_2024_30.73_76.77.json)  
**Pipeline Source Code:** [`sireesha/data_collection/nasa_power.py`](../sireesha/data_collection/nasa_power.py)  

---

## 1. Executive Summary

A comprehensive forensic and data-quality inspection was executed on the raw NASA POWER API payload and the downstream processed climate dataset. The dataset comprises **60 continuous monthly records** spanning a 5-year observation period from January 2020 through December 2024 (`2020-01` to `2024-12`).

Every raw parameter value in the original JSON was verified against the processed CSV table. **Zero discrepancies, zero temporal gaps, and zero unexpected missing values** were identified. All values fall within scientifically realistic physical boundaries for the sub-tropical agro-climatic region of Punjab, India.

---

## 2. Source Provenance & Extraction Metadata

| Metadata Field | Verified Value | Documentation & Source Context |
| :--- | :--- | :--- |
| **API Provider** | NASA Langley Research Center (LaRC) | NASA Prediction of Worldwide Energy Resources (POWER) Project |
| **Service Endpoint** | `https://power.larc.nasa.gov/api/temporal/monthly/point` | Native Resolution Monthly and Annual Point API (v2.10.0) |
| **User Community** | `AG` (Agroclimatology) | Calibrated for agricultural and hydrological modeling |
| **Underlying Models** | MERRA-2 & GEOS-5 CLSM | Modern-Era Retrospective analysis for Research and Applications, Version 2; Catchment Land Surface Model |
| **Nominal Query Coordinates**| Latitude: `30.7300° N`, Longitude: `76.7700° E` | Chandigarh / Punjab agricultural transition boundary |
| **Elevation** | `423.74 m` | Extracted directly from MERRA-2 topography model |
| **Time Standard** | Local Solar Time (`LST`) | Standardized solar noon temporal reference |
| **Observation Horizon** | January 1, 2020 to December 31, 2024 | Exact 60-month chronological series |
| **Fill Value Convention** | `-999.0` | NASA POWER standard indicator for unobserved/missing pixels |
| **Payload Format** | GeoJSON / Feature format | Sourced natively via HTTPS request |

---

## 3. Parameter Verification & Physical Range Audit

The 6 collected parameters were audited for units, definitions, scientific meaning, and empirical observed distributions:

| Raw Code | Processed Column Name | Physical Quantity | Official Units | Scientific Interpretation & Definition | Obs. Min | Obs. Max | Obs. Mean | Missing Count |
| :--- | :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| `T2M` | `air_temperature_c` | Ambient Air Temperature | °C | Dry bulb temperature at 2 meters above ground level. | 10.96 | 36.15 | 23.51 | 0 (0.0%) |
| `RH2M` | `air_humidity_percent` | Atmospheric Humidity | % | Ratio of actual vapor pressure to saturation vapor pressure at 2 m. | 22.39 | 86.94 | 56.26 | 0 (0.0%) |
| `PRECTOTCORR` | `precipitation_mm_day` | Surface Precipitation Rate | mm/day | Bias-corrected total precipitation flux reaching the surface. | 0.00 | 18.70 | 3.62 | 0 (0.0%) |
| `GWETTOP` | `soil_moisture_surface_fraction` | Surface Soil Wetness | Fraction $[0, 1]$ | Degree of saturation of the top layer (~0–5 cm) simulated by CLSM. | 0.19 | 0.88 | 0.51 | 0 (0.0%) |
| `GWETROOT` | `soil_moisture_rootzone_fraction`| Root-Zone Soil Wetness | Fraction $[0, 1]$ | Degree of saturation across the active root zone (~0–100 cm). | 0.34 | 0.91 | 0.53 | 0 (0.0%) |
| `TSOIL1` | `soil_temperature_layer1_c` | Soil Temperature Layer 1 | °C | Thermal state of topsoil layer (0–10 cm). | 10.37 | 37.31 | 23.18 | 0 (0.0%) |

---

## 4. Scientific Rigor & Critical Distinctions

### 4.1 Single Coordinate Point Sample vs. State of Punjab
* **Grid Cell Extent:** NASA POWER agroclimatology data is resolved on a global atmospheric grid of $0.5^\circ \times 0.625^\circ$ (approx. $50\text{ km} \times 60\text{ km}$ at latitude 30° N).
* **Geographic Reality:** The coordinate `(30.73, 76.77)` samples a single atmospheric and hydrological grid cell centered on the Chandigarh/Mohali agricultural fringe in eastern Punjab.
* **Non-Representativeness Warning:** The state of Punjab encompasses $50,362\text{ km}^2$ across five distinct agro-climatic zones:
  1. *Sub-Mountain Undulating Zone* (Rupnagar, Hoshiarpur)
  2. *Undulating Plain Zone* (Gurdaspur, SBS Nagar)
  3. *Central Plain Zone* (Ludhiana, Jalandhar, Patiala)
  4. *Western Plain Zone* (Firozpur, Faridkot)
  5. *Western Semi-Arid Zone* (Bathinda, Mansa, Fazilka)
* Under no circumstances should this single grid point be claimed to represent soil or climate conditions across the entire state of Punjab.

### 4.2 Distinguishing Reanalysis Estimates from In-Situ Measurements
* **Atmospheric Variables (`T2M`, `RH2M`, `PRECTOTCORR`):** These values represent spatially assimilated outputs from the MERRA-2 atmospheric model, incorporating satellite radiances, radar observations, and surface station reports. They are **spatially interpolated simulations**, not dedicated on-farm automated weather station (AWS) measurements.
* **Hydrological Variables (`GWETTOP`, `GWETROOT`):** These parameters are produced by the Catchment Land Surface Model (CLSM). They quantify dimensionless **relative soil wetness fractions** (from 0 = dry limit to 1 = full saturation). They are **NOT**:
  - In-situ volumetric water content ($\text{VWC}, \text{m}^3/\text{m}^3$) measured by TDR, FDR, or neutron probe.
  - Gravimetric soil moisture ($g\text{ water} / g\text{ dry soil}$).
  - Direct field sensor readings.
* **Thermal Coupling (`TSOIL1` vs. `T2M`):** Surface soil temperature (`TSOIL1`) responds dynamically to solar radiation and surface wetness. Observed summer peaks reached 37.31°C (June 2024), closely tracking ambient temperature peaks (36.15°C).

---

## 5. Temporal Consistency & Missing Values Audit

1. **Chronological Continuity:** Verified strictly sequential month-by-month progression without skips from `2020-01` to `2024-12`.
2. **Missing Fill Value Handling:** NASA POWER denotes missing months or failed grid cells with `-999.0`. In the retrieved dataset, **zero instances of -999.0 were detected**. All 60 months feature complete, valid numbers.
3. **Annual Aggregation Artifact Exclusion:** NASA POWER monthly payloads include a 13th month key (`YYYY13`) representing the annual mean. The extraction script [`NasaPowerCollector.process_and_validate()`](../sireesha/data_collection/nasa_power.py#L190-L195) correctly ignores `YYYY13`, preventing artificial spikes or duplicate records.
4. **Reproducibility Test:** An automated extraction loop recreated the dataframe directly from the raw JSON payload and matched [`climate_data.csv`](../sireesha/processed/climate_data.csv) with **0 bit-level discrepancies**.

---

## 6. Recommendations & Unresolved Limitations

1. **Spatial Aggregation Caveat:** For farm-level advisory, downstream risk tools must clearly state that precipitation and soil wetness reflect regional $50\text{ km}$ grid averages. Local convective thunderstorm events or canal-irrigation inputs are unrepresented in MERRA-2.
2. **Irrigation Uncoupling:** While NASA POWER CLSM captures large-scale atmospheric precipitation-evaporation balances, it does not simulate localized tube-well irrigation flooding typical of Punjab's paddy-wheat rotation. Thus, real root-zone moisture on irrigated fields may be substantially higher during May–June than the model's simulated minimum of $0.34$.
3. **Data Quality Status:** **PASSED AND FULLY VERIFIED.**
