# SoilSentinel — Comprehensive Data Dictionary

**Dataset Reference:** [`data/feature_table.csv`](../data/feature_table.csv)  
**Pipeline Module:** [`src/features.py`](../src/features.py)  
**Schema Dimensions:** 60 monthly records × 53 feature columns  
**Temporal Coverage:** January 2020 through December 2024 (`2020-01` to `2024-12`)  
**Spatial Context:** Indo-Gangetic Agricultural Plains / Punjab  

---

## 1. Dataset Overview & Spatial Configuration

### 1.1 Study Scope & Temporal Structure
The SoilSentinel feature table consists of **60 chronologically ordered monthly observations** representing a 5-year monitoring horizon (2020–2024) for a representative agricultural site in the Indo-Gangetic Plains of Punjab, India.

> [!IMPORTANT]
> **Single Study Location — Static Soil Baseline Repetition:**  
> The 60 rows represent **60 consecutive monthly time steps at one single geographic site**, NOT 60 independent geographic soil sampling locations. Soil baseline properties (pH, texture fractions, SOC) derived from digital soil mapping are static characteristics for this location and are repeated across all 60 monthly rows to provide baseline context for dynamic climate and hydrological stress scoring.

### 1.2 Coordinate Configuration & Radial Sampling Adjustment
* **Nominal Target Coordinates:** Latitude `30.7300° N`, Longitude `76.7700° E` (Chandigarh regional reference point).
* **Sampled Agricultural Coordinates:** Latitude `30.7392° N`, Longitude `76.7764° E` (adjustment distance: 1.0 km).
* **Rationale for Coordinate Adjustment:**  
  In the official ISRIC SoilGrids v2.0 global digital soil model, built-up urban centers and non-soil land surfaces are masked out as `NODATA` (pixel value `-32768`). The nominal coordinate (`30.7300, 76.7700`) fell inside the urban boundary of Chandigarh. To ensure valid, uncorrupted agricultural soil baseline data, [`SoilGridsCollector._sample_from_vrt()`](../src/data_collection/soilgrids.py) performed an automatic radial search outward up to 10 km, locating the nearest valid agricultural soil pixel at **1.0 km distance** (`30.7392° N, 76.7764° E`).
* **Climate Resolution Compatibility:**  
  NASA POWER agroclimatology data is provided on a global $0.5^\circ \times 0.625^\circ$ (MERRA-2) and $0.5^\circ \times 0.5^\circ$ spatial grid (~50 km cell width). Both the nominal coordinate and the sampled agricultural soil pixel reside within the **exact same climate grid cell**.

---

## 2. Provenance Architecture & Scientific Data Integrity

Every feature in the dataset is categorized into one of the following authoritative provenance classes:

### 2.1 Model-Derived Atmospheric & Land-Surface Reanalysis (NASA POWER)
Variables including air temperature, relative humidity, precipitation, soil surface temperature, and soil moisture fractions are sourced from the **NASA POWER Agroclimatology API**.
* **Scientific Reality:** These data are produced by the NASA Global Modeling and Assimilation Office (GMAO) **MERRA-2 reanalysis model** and the **GEOS Catchment Land Surface Model (CLSM)**.
* **Limitation:** These values represent **spatially assimilated atmospheric and land-surface simulations**, NOT local physical weather stations or in-situ electronic soil capacitance/TDR probes.

### 2.2 Digital Spatial Soil Mapping (ISRIC SoilGrids v2.0)
Variables including layer-specific pH, clay, sand, silt, and soil organic carbon are sourced from the **ISRIC SoilGrids v2.0 Global Soil Information System**.
* **Scientific Reality:** These data represent **machine-learning predictions (Quantile Random Forest)** generated at 250 m spatial resolution by ISRIC, trained on global soil profile databases (WoSIS) and environmental remote sensing covariates.
* **Limitation:** These values represent **statistical spatial estimates**, NOT physical laboratory core samplings from this specific farm field.

### 2.3 Derived Features
Temporal features, cyclic calendar transformations, shifted lag indicators, multi-month rolling aggregates, soil-climate coupling indices, and soil texture ratios are mathematically derived within [`src/features.py`](../src/features.py).

### 2.4 Absolute Prohibition of Fabricated & Synthetic Data
* **No In-Situ Sensor Data:** There are **zero in-situ ground sensors** present in this project.
* **No Synthetic Data:** There are **zero synthetic, simulated, or hallucinated records**. All records originate from authoritative reanalysis and digital mapping APIs.

---

## 3. Absence of Electrical Conductivity (EC) & Agronomic Standards

* **Electrical Conductivity (EC) Status:** EC is **completely unavailable** in both NASA POWER and ISRIC SoilGrids v2.0.
* **Non-Substitution Rule:** The codebase **strictly does not substitute Cation Exchange Capacity (CEC) for EC**.
* **Scientific Distinction Between CEC and EC:**
  * **Cation Exchange Capacity (CEC):** Measured in $\text{cmol}_c/\text{kg}$, CEC quantifies the total capacity of soil clay minerals and organic matter to hold exchangeable cations ($\text{Ca}^{2+}, \text{Mg}^{2+}, \text{K}^{+}, \text{Na}^{+}, \text{NH}_4^{+}$). It measures soil nutrient buffering and structural retention.
  * **Electrical Conductivity (EC):** Measured in $\text{dS/m}$ (or $\mu\text{S/cm}$), EC measures the concentration of soluble electrolytes and dissolved salts in the soil solution. It indicates soil salinization and osmotic stress.
  * Conflating CEC with EC is scientifically invalid. Because SoilGrids produces a `cec` layer but no calibrated `ec` layer, SoilSentinel correctly excludes salinity from baseline scoring rather than substituting an unrelated chemical parameter.

---

## 4. Missing Values & Boundary NaNs Policy

The dataset enforces a strict, transparent missing-value policy:

1. **Expected Boundary NaNs (Historical Start Limits):**
   * `precipitation_lag1_mm_day`: Exactly **1 NaN** at row 0 (`2020-01`).
   * `air_temperature_lag1_c`: Exactly **1 NaN** at row 0 (`2020-01`).
   * `precipitation_rolling_3m_mean_mm_day`: Exactly **2 NaNs** at rows 0 and 1 (`2020-01`, `2020-02`).
   * `precipitation_rolling_3m_sum_mm_day`: Exactly **2 NaNs** at rows 0 and 1 (`2020-01`, `2020-02`).
2. **Missing History vs. Zero Rainfall:**  
   `NaN` at the sequence start indicates that observations prior to January 2020 were not collected in the 5-year window. **It does NOT indicate 0.0 mm of rainfall or 0°C temperature.** Replacing boundary NaNs with zeros would falsely introduce extreme drought or freezing signals.
3. **No Synthetic Imputation in Feature Table:**  
   Boundary NaNs are intentionally preserved in [`data/feature_table.csv`](../data/feature_table.csv). Downstream prediction engines handle boundary conditions explicitly via dual-mode evaluation:
   * *Permissive Mode:* Falls back to single-month precipitation with an audit log flag (`partial_history_fallback=True`).
   * *Strict Mode:* Rejects records with insufficient antecedent history (`status=INSUFFICIENT_HISTORY`, score=`None`).
4. **Zero Missing Values Elsewhere:**  
   All other 49 columns have **0 NaNs (100% complete)** across all 60 months.

---

## 5. Master Index of the 53 Feature Table Columns

The 53 columns in [`data/feature_table.csv`](../data/feature_table.csv) appear in the exact order documented below:

| # | Column Name | Data Type | Physical Unit | Provenance Category | Missing NaNs | Observed Range [Min, Max] |
| :-: | :--- | :--- | :--- | :--- | :-: | :-: |
| 1 | `region` | `string` | Text | Spatial Metadata | 0 | `Indo-Gangetic Agricultural Plains / Punjab` |
| 2 | `nominal_latitude` | `float64` | Decimal Degrees | Spatial Metadata | 0 | $[30.73, 30.73]$ |
| 3 | `nominal_longitude` | `float64` | Decimal Degrees | Spatial Metadata | 0 | $[76.77, 76.77]$ |
| 4 | `sampled_latitude` | `float64` | Decimal Degrees | Spatial Metadata | 0 | $[30.7392, 30.7392]$ |
| 5 | `sampled_longitude` | `float64` | Decimal Degrees | Spatial Metadata | 0 | $[76.7764, 76.7764]$ |
| 6 | `year` | `int64` | Calendar Year | Temporal Identifier | 0 | $[2020, 2024]$ |
| 7 | `month` | `int64` | Calendar Month | Temporal Identifier | 0 | $[1, 12]$ |
| 8 | `date` | `string` | YYYY-MM | Temporal Identifier | 0 | `2020-01` to `2024-12` |
| 9 | `air_temperature_c` | `float64` | °C | Atmospheric Reanalysis | 0 | $[10.96, 36.15]$ |
| 10 | `temperature_c` | `float64` | °C | Atmospheric Reanalysis | 0 | $[10.96, 36.15]$ |
| 11 | `air_humidity_percent` | `float64` | % | Atmospheric Reanalysis | 0 | $[22.39, 86.94]$ |
| 12 | `humidity_percent` | `float64` | % | Atmospheric Reanalysis | 0 | $[22.39, 86.94]$ |
| 13 | `precipitation_mm_day` | `float64` | mm/day | Atmospheric Reanalysis | 0 | $[0.00, 18.70]$ |
| 14 | `soil_temperature_layer1_c` | `float64` | °C | Land Surface Reanalysis | 0 | $[10.37, 37.31]$ |
| 15 | `soil_moisture_surface_fraction` | `float64` | Fraction (0–1) | Land Surface Reanalysis | 0 | $[0.1900, 0.8800]$ |
| 16 | `soil_moisture_rootzone_fraction` | `float64` | Fraction (0–1) | Land Surface Reanalysis | 0 | $[0.3400, 0.9100]$ |
| 17 | `topsoil_ph_mean` | `float64` | pH units | Static Soil Baseline | 0 | $[6.55, 6.55]$ |
| 18 | `topsoil_clay_percent` | `float64` | % mass fraction | Static Soil Baseline | 0 | $[25.78, 25.78]$ |
| 19 | `topsoil_sand_percent` | `float64` | % mass fraction | Static Soil Baseline | 0 | $[41.17, 41.17]$ |
| 20 | `topsoil_silt_percent` | `float64` | % mass fraction | Static Soil Baseline | 0 | $[33.05, 33.05]$ |
| 21 | `topsoil_soc_g_kg` | `float64` | g/kg | Static Soil Baseline | 0 | $[12.95, 12.95]$ |
| 22 | `ph_0_5cm` | `float64` | pH units | Static Soil Layer | 0 | $[6.60, 6.60]$ |
| 23 | `ph_5_15cm` | `float64` | pH units | Static Soil Layer | 0 | $[6.60, 6.60]$ |
| 24 | `ph_15_30cm` | `float64` | pH units | Static Soil Layer | 0 | $[6.50, 6.50]$ |
| 25 | `clay_0_5cm_percent` | `float64` | % mass fraction | Static Soil Layer | 0 | $[21.50, 21.50]$ |
| 26 | `clay_5_15cm_percent` | `float64` | % mass fraction | Static Soil Layer | 0 | $[23.70, 23.70]$ |
| 27 | `clay_15_30cm_percent` | `float64` | % mass fraction | Static Soil Layer | 0 | $[28.60, 28.60]$ |
| 28 | `sand_0_5cm_percent` | `float64` | % mass fraction | Static Soil Layer | 0 | $[43.90, 43.90]$ |
| 29 | `sand_5_15cm_percent` | `float64` | % mass fraction | Static Soil Layer | 0 | $[42.60, 42.60]$ |
| 30 | `sand_15_30cm_percent` | `float64` | % mass fraction | Static Soil Layer | 0 | $[39.30, 39.30]$ |
| 31 | `silt_0_5cm_percent` | `float64` | % mass fraction | Static Soil Layer | 0 | $[34.60, 34.60]$ |
| 32 | `silt_5_15cm_percent` | `float64` | % mass fraction | Static Soil Layer | 0 | $[33.70, 33.70]$ |
| 33 | `silt_15_30cm_percent` | `float64` | % mass fraction | Static Soil Layer | 0 | $[32.10, 32.10]$ |
| 34 | `soc_0_5cm_g_kg` | `float64` | g/kg | Static Soil Layer | 0 | $[23.90, 23.90]$ |
| 35 | `soc_5_15cm_g_kg` | `float64` | g/kg | Static Soil Layer | 0 | $[14.60, 14.60]$ |
| 36 | `soc_15_30cm_g_kg` | `float64` | g/kg | Static Soil Layer | 0 | $[8.20, 8.20]$ |
| 37 | `climate_source` | `string` | Text | Source Attribution | 0 | `NASA POWER AG Community` |
| 38 | `soil_source` | `string` | Text | Source Attribution | 0 | `ISRIC SoilGrids v2.0` |
| 39 | `quarter` | `int64` | Quarter (1–4) | Derived Temporal | 0 | $[1, 4]$ |
| 40 | `season` | `string` | Text | Derived Temporal | 0 | 4 agro-climatic categories |
| 41 | `month_sin` | `float64` | Dimensionless | Cyclical Encoding | 0 | $[-1.0000, 1.0000]$ |
| 42 | `month_cos` | `float64` | Dimensionless | Cyclical Encoding | 0 | $[-1.0000, 1.0000]$ |
| 43 | `precipitation_lag1_mm_day` | `float64` | mm/day | Derived Dynamic Lag | **1** | $[0.00, 18.70]$ |
| 44 | `precipitation_rolling_3m_mean_mm_day` | `float64` | mm/day | Derived Rolling Agg | **2** | $[0.17, 12.35]$ |
| 45 | `precipitation_rolling_3m_sum_mm_day` | `float64` | mm/day | Derived Rolling Agg | **2** | $[0.52, 37.04]$ |
| 46 | `air_temperature_lag1_c` | `float64` | °C | Derived Dynamic Lag | **1** | $[10.96, 36.15]$ |
| 47 | `temp_soil_air_diff_c` | `float64` | °C | Derived Interaction | 0 | $[-1.36, 1.16]$ |
| 48 | `soil_moisture_depth_gradient` | `float64` | Dimensionless | Derived Interaction | 0 | $[-0.0400, 0.1500]$ |
| 49 | `monthly_aridity_index` | `float64` | Index units | Derived Interaction | 0 | $[0.00, 14.61]$ |
| 50 | `clay_to_sand_ratio` | `float64` | Dimensionless | Derived Soil Ratio | 0 | $[0.626, 0.626]$ |
| 51 | `soc_to_clay_ratio` | `float64` | Dimensionless | Derived Soil Ratio | 0 | $[0.0502, 0.0502]$ |
| 52 | `soil_measurement_type` | `string` | Text | Metadata Tag | 0 | `static_regional_baseline` |
| 53 | `climate_measurement_type` | `string` | Text | Metadata Tag | 0 | `monthly_time_series` |

---

## 6. Detailed Feature-by-Feature Specifications

### 6.1 Spatial Identifiers & Metadata (Columns 1–5, 37–38, 52–53)

#### Column 1: `region`
* **Data Type:** `string` (`object`)
* **Physical Unit:** Text label (non-numeric)
* **Source:** Configured in [`config/settings.yaml`](../config/settings.yaml) under `study_region.name`.
* **Description:** Identifies the target agro-ecological study domain.
* **Observed Value:** `"Indo-Gangetic Agricultural Plains / Punjab"` across all 60 rows.
* **Missing Values:** None.

#### Column 2: `nominal_latitude`
* **Data Type:** `float64`
* **Physical Unit:** Decimal degrees North
* **Source:** Target geographical coordinate requested in [`config/settings.yaml`](../config/settings.yaml).
* **Observed Value:** `30.73` across all 60 rows.
* **Physical Bounds:** $[-90.0, 90.0]^\circ\text{N}$.

#### Column 3: `nominal_longitude`
* **Data Type:** `float64`
* **Physical Unit:** Decimal degrees East
* **Source:** Target geographical coordinate requested in [`config/settings.yaml`](../config/settings.yaml).
* **Observed Value:** `76.77` across all 60 rows.
* **Physical Bounds:** $[-180.0, 180.0]^\circ\text{E}$.

#### Column 4: `sampled_latitude`
* **Data Type:** `float64`
* **Physical Unit:** Decimal degrees North
* **Source:** ISRIC SoilGrids v2.0 raster query via [`SoilGridsCollector`](../src/data_collection/soilgrids.py).
* **Description:** Actual geographic latitude where SoilGrids properties were extracted after radial search resolved the urban `NODATA` mask.
* **Observed Value:** `30.7392` across all 60 rows.

#### Column 5: `sampled_longitude`
* **Data Type:** `float64`
* **Physical Unit:** Decimal degrees East
* **Source:** ISRIC SoilGrids v2.0 raster query via [`SoilGridsCollector`](../src/data_collection/soilgrids.py).
* **Description:** Actual geographic longitude where SoilGrids properties were extracted after radial search resolved the urban `NODATA` mask.
* **Observed Value:** `76.7764` across all 60 rows.

#### Column 37: `climate_source`
* **Data Type:** `string`
* **Physical Unit:** Text label
* **Description:** Authoritative attribution for the climate reanalysis stream.
* **Observed Value:** `"NASA POWER AG Community"` across all 60 rows.

#### Column 38: `soil_source`
* **Data Type:** `string`
* **Physical Unit:** Text label
* **Description:** Authoritative attribution for the static digital soil baseline.
* **Observed Value:** `"ISRIC SoilGrids v2.0"` across all 60 rows.

#### Column 52: `soil_measurement_type`
* **Data Type:** `string`
* **Physical Unit:** Text label
* **Description:** Explicitly documents that soil attributes represent a static spatial baseline repeated across months, preventing machine learning models or auditors from mistaking repeated rows for longitudinal temporal soil samples.
* **Observed Value:** `"static_regional_baseline"` across all 60 rows.

#### Column 53: `climate_measurement_type`
* **Data Type:** `string`
* **Physical Unit:** Text label
* **Description:** Explicitly documents that climate attributes represent dynamic monthly reanalysis observations.
* **Observed Value:** `"monthly_time_series"` across all 60 rows.

---

### 6.2 Temporal Identifiers & Cyclic Calendar Encodings (Columns 6–8, 39–42)

#### Column 6: `year`
* **Data Type:** `int64`
* **Physical Unit:** Calendar year
* **Observed Range:** $[2020, 2024]$ (5 years, 12 months each).

#### Column 7: `month`
* **Data Type:** `int64`
* **Physical Unit:** Calendar month number
* **Observed Range:** $[1, 12]$.

#### Column 8: `date`
* **Data Type:** `string`
* **Physical Unit:** ISO year-month string (`YYYY-MM`)
* **Observed Range:** `"2020-01"` through `"2024-12"` (60 strictly consecutive monthly records).

#### Column 39: `quarter`
* **Data Type:** `int64`
* **Physical Unit:** Calendar quarter ($1, 2, 3, 4$)
* **Transformation:** `df['date_dt'].dt.quarter`
* **Observed Range:** $[1, 4]$.

#### Column 40: `season`
* **Data Type:** `string`
* **Physical Unit:** Categorical agro-climatic season label
* **Transformation:** Sub-tropical agricultural season mapping defined in [`src/features.py:L110-L120`](../src/features.py#L110-L120):
  * Months 12, 1, 2: `"Winter"` (Rabi crop season)
  * Months 3, 4, 5: `"Summer_PreMonsoon"` (Zaid crop season, high thermal stress)
  * Months 6, 7, 8, 9: `"Monsoon"` (Kharif crop season, intense rainfall)
  * Months 10, 11: `"PostMonsoon_Autumn"` (Post-monsoon transition)
* **Observed Values:** Exactly 4 discrete categories.

#### Column 41: `month_sin`
* **Data Type:** `float64`
* **Physical Unit:** Dimensionless cyclical coordinate
* **Mathematical Formula:**
  $$\text{month\_sin} = \operatorname{round}\left(\sin\left(\frac{2\pi \cdot \text{month}}{12}\right), 4\right)$$
* **Physical Bounds:** $[-1.0, 1.0]$.
* **Observed Range:** $[-1.0000, 1.0000]$ (mean: $0.0000$).
* **Significance:** Maps month 12 (December, $\sin=0$) and month 1 (January, $\sin=0.5$) continuously, preventing artificial numerical boundary jumps in machine learning models.

#### Column 42: `month_cos`
* **Data Type:** `float64`
* **Physical Unit:** Dimensionless cyclical coordinate
* **Mathematical Formula:**
  $$\text{month\_cos} = \operatorname{round}\left(\cos\left(\frac{2\pi \cdot \text{month}}{12}\right), 4\right)$$
* **Physical Bounds:** $[-1.0, 1.0]$.
* **Observed Range:** $[-1.0000, 1.0000]$ (mean: $0.0000$).

---

### 6.3 Dynamic Atmospheric & Land-Surface Reanalysis Features (Columns 9–16)

#### Columns 9 & 10: `air_temperature_c` and `temperature_c`
* **Data Type:** `float64`
* **Physical Unit:** Degrees Celsius (°C)
* **Source:** NASA POWER parameter `T2M` (Temperature at 2 Meters).
* **Physical Validity Bounds:** $[-50.0, 60.0]^\circ\text{C}$.
* **Observed Range:** $[10.96, 36.15]^\circ\text{C}$ (mean: $23.51^\circ\text{C}$).
* **Note on Dual Columns:** `temperature_c` is an exact, unrounded clone of `air_temperature_c`, maintained for backward compatibility with legacy scripts.

#### Columns 11 & 12: `air_humidity_percent` and `humidity_percent`
* **Data Type:** `float64`
* **Physical Unit:** Percentage (%)
* **Source:** NASA POWER parameter `RH2M` (Relative Humidity at 2 Meters).
* **Physical Validity Bounds:** $[0.0, 100.0]\%$.
* **Observed Range:** $[22.39, 86.94]\%$ (mean: $56.26\%$).
* **Note on Dual Columns:** `humidity_percent` is an exact clone of `air_humidity_percent`, maintained for backward compatibility.

#### Column 13: `precipitation_mm_day`
* **Data Type:** `float64`
* **Physical Unit:** Millimeters per day ($\text{mm/day}$)
* **Source:** NASA POWER parameter `PRECTOTCORR` (Precipitation Corrected).
* **Meaning:** Average daily precipitation rate across the calendar month.
* **Physical Validity Bounds:** $[0.0, \infty)\text{ mm/day}$.
* **Observed Range:** $[0.00, 18.70]\text{ mm/day}$ (mean: $3.62\text{ mm/day}$).
* **Important Interpretation Note:** Sourced as a **daily rate** ($\text{mm/day}$), not total cumulative monthly rainfall. Multiplying by ~30 days yields monthly cumulative rainfall ($0.0\text{ mm}$ to $561\text{ mm}$).

#### Column 14: `soil_temperature_layer1_c`
* **Data Type:** `float64`
* **Physical Unit:** Degrees Celsius (°C)
* **Source:** NASA POWER parameter `TSOIL1` (Soil Temperature Layer 1, 0–10 cm depth).
* **Physical Validity Bounds:** $[-50.0, 60.0]^\circ\text{C}$.
* **Observed Range:** $[10.37, 37.31]^\circ\text{C}$ (mean: $23.18^\circ\text{C}$).
* **Provenance Note:** Derived from the GEOS Land Surface Model simulation of topsoil energy balance, not an inserted physical thermocouple.

#### Column 15: `soil_moisture_surface_fraction`
* **Data Type:** `float64`
* **Physical Unit:** Dimensionless wetness fraction ($0.0$ to $1.0$)
* **Source:** NASA POWER parameter `GWETTOP` (Surface Soil Wetness, 0–5 cm depth).
* **Physical Validity Bounds:** $[0.0, 1.0]$ where $0.0$ is completely desiccated and $1.0$ is full saturation.
* **Observed Range:** $[0.1900, 0.8800]$ (mean: $0.5062$).
* **Agronomic Note:** Distinct from volumetric water content ($\text{m}^3/\text{m}^3$). Represents relative saturation fraction of pore space in the top 5 cm.

#### Column 16: `soil_moisture_rootzone_fraction`
* **Data Type:** `float64`
* **Physical Unit:** Dimensionless wetness fraction ($0.0$ to $1.0$)
* **Source:** NASA POWER parameter `GWETROOT` (Root-Zone Soil Wetness, 0–100 cm profile).
* **Physical Validity Bounds:** $[0.0, 1.0]$.
* **Observed Range:** $[0.3400, 0.9100]$ (mean: $0.5260$).
* **Agronomic Note:** Represents deep moisture reserves buffering crops against short-term surface desiccation.

---

### 6.4 Static Topsoil Baseline Features (Columns 17–21)

These 5 features represent the **depth-weighted average across 0–30 cm topsoil**, computed from the 3 SoilGrids depth intervals in [`src/Preprocessing/merge_data.py:L45-L102`](../src/Preprocessing/merge_data.py#L45-L102):
$$\text{Topsoil Property} = \frac{5 \cdot P_{0-5\text{cm}} + 10 \cdot P_{5-15\text{cm}} + 15 \cdot P_{15-30\text{cm}}}{30}$$

#### Column 17: `topsoil_ph_mean`
* **Data Type:** `float64`
* **Physical Unit:** Standard pH units
* **Formula:** $\frac{5(6.60) + 10(6.60) + 15(6.50)}{30} = 6.55$
* **Physical Bounds:** $[3.0, 11.0]$.
* **Observed Value:** Constant $6.55$ across all 60 rows.
* **Agronomic Class:** Near-neutral to slightly acidic, optimal for cereal agriculture.

#### Column 18: `topsoil_clay_percent`
* **Data Type:** `float64`
* **Physical Unit:** Percentage (%) by weight of mineral soil particles $< 2\,\mu\text{m}$
* **Formula:** $\frac{5(21.50) + 10(23.70) + 15(28.60)}{30} = 25.783 \to 25.78\%$
* **Physical Bounds:** $[0.0, 100.0]\%$.
* **Observed Value:** Constant $25.78\%$ across all 60 rows.

#### Column 19: `topsoil_sand_percent`
* **Data Type:** `float64`
* **Physical Unit:** Percentage (%) by weight of mineral soil particles $50–2000\,\mu\text{m}$
* **Formula:** $\frac{5(43.90) + 10(42.60) + 15(39.30)}{30} = 41.166 \to 41.17\%$
* **Physical Bounds:** $[0.0, 100.0]\%$.
* **Observed Value:** Constant $41.17\%$ across all 60 rows.

#### Column 20: `topsoil_silt_percent`
* **Data Type:** `float64`
* **Physical Unit:** Percentage (%) by weight of mineral soil particles $2–50\,\mu\text{m}$
* **Formula:** $\frac{5(34.60) + 10(33.70) + 15(32.10)}{30} = 33.05\%$
* **Physical Bounds:** $[0.0, 100.0]\%$.
* **Observed Value:** Constant $33.05\%$ across all 60 rows.
* **Texture Sum Verification:** $25.78\% + 41.17\% + 33.05\% = 100.00\%$ (USDA Texture Class: **Loam** to **Clay Loam**).

#### Column 21: `topsoil_soc_g_kg`
* **Data Type:** `float64`
* **Physical Unit:** Grams of organic carbon per kilogram of fine earth ($\text{g/kg}$)
* **Formula:** $\frac{5(23.90) + 10(14.60) + 15(8.20)}{30} = 12.95\text{ g/kg}$
* **Physical Bounds:** $[0.0, \infty)\text{ g/kg}$.
* **Observed Value:** Constant $12.95\text{ g/kg}$ ($1.295\%$ SOC) across all 60 rows.

---

### 6.5 Layer-Specific Soil Baseline Properties (Columns 22–36)

Extracted from official SoilGrids v2.0 GeoTIFF/VRT maps across 3 standard depth intervals:
* **Layer 1 (`0_5cm`):** Uppermost surface crust ($0–5\text{ cm}$, thickness $5\text{ cm}$).
* **Layer 2 (`5_15cm`):** Main shallow tillage layer ($5–15\text{ cm}$, thickness $10\text{ cm}$).
* **Layer 3 (`15_30cm`):** Sub-surface root transition layer ($15–30\text{ cm}$, thickness $15\text{ cm}$).

#### Columns 22–24: `ph_0_5cm`, `ph_5_15cm`, `ph_15_30cm`
* **Data Type:** `float64`
* **Physical Unit:** Standard pH in $\text{H}_2\text{O}$ solution
* **Scaling:** $\text{Raw DN} \times 0.1$
* **Observed Values:** `6.60`, `6.60`, `6.50` (all constant across 60 rows).

#### Columns 25–27: `clay_0_5cm_percent`, `clay_5_15cm_percent`, `clay_15_30cm_percent`
* **Data Type:** `float64`
* **Physical Unit:** Percentage (%)
* **Scaling:** $\text{Raw DN (g/kg)} \times 0.1$
* **Observed Values:** `21.50%`, `23.70%`, `28.60%` (demonstrating progressive clay illuviation with depth).

#### Columns 28–30: `sand_0_5cm_percent`, `sand_5_15cm_percent`, `sand_15_30cm_percent`
* **Data Type:** `float64`
* **Physical Unit:** Percentage (%)
* **Scaling:** $\text{Raw DN (g/kg)} \times 0.1$
* **Observed Values:** `43.90%`, `42.60%`, `39.30%`.

#### Columns 31–33: `silt_0_5cm_percent`, `silt_5_15cm_percent`, `silt_15_30cm_percent`
* **Data Type:** `float64`
* **Physical Unit:** Percentage (%)
* **Scaling:** $\text{Raw DN (g/kg)} \times 0.1$
* **Observed Values:** `34.60%`, `33.70%`, `32.10%`.

#### Columns 34–36: `soc_0_5cm_g_kg`, `soc_5_15cm_g_kg`, `soc_15_30cm_g_kg`
* **Data Type:** `float64`
* **Physical Unit:** Grams per kilogram ($\text{g/kg}$)
* **Scaling:** $\text{Raw DN (dg/kg)} \times 0.1$
* **Observed Values:** `23.90 g/kg`, `14.60 g/kg`, `8.20 g/kg` (reflecting rapid organic matter depletion below the biological surface layer).

---

### 6.6 Derived Lag and Rolling Climate Aggregates (Columns 43–46)

#### Column 43: `precipitation_lag1_mm_day`
* **Data Type:** `float64`
* **Physical Unit:** Millimeters per day ($\text{mm/day}$)
* **Transformation:** `df['precipitation_mm_day'].shift(1)`
* **Meaning:** Mean daily precipitation rate of the immediately preceding month ($t-1$).
* **Missing-Value Behavior:** **Exactly 1 NaN** at index 0 (`2020-01`), representing unobserved history prior to January 2020.
* **Observed Range:** $[0.00, 18.70]\text{ mm/day}$ (mean across 59 valid months: $3.66\text{ mm/day}$).

#### Column 44: `precipitation_rolling_3m_mean_mm_day`
* **Data Type:** `float64`
* **Physical Unit:** Millimeters per day ($\text{mm/day}$)
* **Transformation:**
  $$\text{precipitation\_rolling\_3m\_mean} = \operatorname{round}\left(\frac{P_{t} + P_{t-1} + P_{t-2}}{3}, 2\right)$$
  Implemented with `rolling(window=3, min_periods=3).mean()`.
* **Meaning:** 3-month trailing moving average of daily precipitation rate.
* **Missing-Value Behavior:** **Exactly 2 NaNs** at indices 0 and 1 (`2020-01`, `2020-02`).
* **Observed Range:** $[0.17, 12.35]\text{ mm/day}$ (mean across 58 valid months: $3.70\text{ mm/day}$).

#### Column 45: `precipitation_rolling_3m_sum_mm_day`
* **Data Type:** `float64`
* **Physical Unit:** Millimeters per day ($\text{mm/day}$, sum of 3 monthly mean daily rates)
* **Transformation:**
  $$\text{precipitation\_rolling\_3m\_sum} = \operatorname{round}\left(P_{t} + P_{t-1} + P_{t-2}, 2\right)$$
  Implemented with `rolling(window=3, min_periods=3).sum()`.
* **Meaning:** Sum of the 3 trailing monthly mean daily precipitation rates.
* **Critical Unit Clarification:**  
  Because `precipitation_mm_day` is a daily rate ($\text{mm/day}$), this rolling sum is the **sum of three daily rates** ($\sum_{i=0}^2 \text{mm/day}_{t-i}$), with unit $\text{mm/day}$. It is **not** total cumulative rainfall depth in millimeters over 90 days. To obtain cumulative millimeters, one would multiply each month's rate by its respective day count ($\approx 30 \times \text{sum}$).
* **Missing-Value Behavior:** **Exactly 2 NaNs** at indices 0 and 1 (`2020-01`, `2020-02`).
* **Observed Range:** $[0.52, 37.04]\text{ mm/day}$ (mean across 58 valid months: $11.09\text{ mm/day}$).

#### Column 46: `air_temperature_lag1_c`
* **Data Type:** `float64`
* **Physical Unit:** Degrees Celsius (°C)
* **Transformation:** `df['air_temperature_c'].shift(1)`
* **Meaning:** 2 m air temperature of the preceding month ($t-1$).
* **Missing-Value Behavior:** **Exactly 1 NaN** at index 0 (`2020-01`).
* **Observed Range:** $[10.96, 36.15]^\circ\text{C}$ (mean across 59 valid months: $23.67^\circ\text{C}$).

---

### 6.7 Derived Soil-Climate Interaction Indicators & Ratios (Columns 47–51)

#### Column 47: `temp_soil_air_diff_c`
* **Data Type:** `float64`
* **Physical Unit:** Degrees Celsius (°C)
* **Mathematical Formula:**
  $$\text{temp\_soil\_air\_diff\_c} = \operatorname{round}(\text{soil\_temperature\_layer1\_c} - \text{air\_temperature\_c}, 2)$$
* **Agronomic Meaning:** Thermal gradient between topsoil (0–10 cm) and 2 m ambient air.
  * *Positive values:* Soil surface is hotter than ambient air (high solar insolation, sparse vegetative canopy, sensible heat absorption).
  * *Negative values:* Soil surface is cooler than air (surface evaporative cooling, dense canopy shading, high soil moisture).
* **Observed Range:** $[-1.36, 1.16]^\circ\text{C}$ (mean: $-0.33^\circ\text{C}$).

#### Column 48: `soil_moisture_depth_gradient`
* **Data Type:** `float64`
* **Physical Unit:** Dimensionless wetness fraction difference
* **Mathematical Formula:**
  $$\text{soil\_moisture\_depth\_gradient} = \operatorname{round}(\text{soil\_moisture\_rootzone\_fraction} - \text{soil\_moisture\_surface\_fraction}, 4)$$
* **Agronomic Meaning:** Vertical hydrological profile gradient between root-zone and topsoil.
  * *Positive values:* Root-zone retains more moisture than the dried surface crust (typical of post-monsoon or dry summer drying where deep reserves buffer shallow drought).
  * *Negative values:* Surface is wetter than the root-zone (active monsoon rainfall infiltration or surface waterlogging).
* **Observed Range:** $[-0.0400, 0.1500]$ (mean: $+0.0198$).

#### Column 49: `monthly_aridity_index`
* **Data Type:** `float64`
* **Physical Unit:** Semi-empirical index units (dimensionally $\text{mm}/^\circ\text{C}$)
* **Mathematical Formula:**
  $$\text{monthly\_aridity\_index} = \operatorname{round}\left(\frac{\text{precipitation\_mm\_day} \cdot 30.0}{\text{air\_temperature\_c} + 10.0}, 2\right)$$
* **Scientific Basis:** Monthly adaptation of the **De Martonne Aridity Index** ($I = \frac{P}{T+10}$). The numerator approximates total monthly rainfall ($\text{mm/day} \times 30$), while the denominator $(T + 10)$ represents potential evapotranspiration demand.
* **Interpretation Thresholds:**
  * $< 5.0$: Severe Hyper-Aridity / Intense Drought Stress
  * $5.0 - 10.0$: Arid / Dry Seasonal Stress
  * $10.0 - 20.0$: Semi-Humid
  * $> 20.0$: Humid / Excess Moisture
* **Observed Range:** $[0.00, 14.61]$ (mean: $3.00$, indicating predominant semi-arid climate stress punctuated by monsoon pulses).

#### Column 50: `clay_to_sand_ratio`
* **Data Type:** `float64`
* **Physical Unit:** Dimensionless mass ratio
* **Mathematical Formula:**
  $$\text{clay\_to\_sand\_ratio} = \operatorname{round}\left(\frac{\text{topsoil\_clay\_percent}}{\text{topsoil\_sand\_percent}}, 3\right) = \operatorname{round}\left(\frac{25.78}{41.17}, 3\right) = 0.626$$
* **Agronomic Meaning:** Ratio of cohesive, moisture-retentive clay particles to porous, non-cohesive sand particles. Silt constitutes the remaining $33.05\%$.
* **Observed Value:** Constant $0.626$ across all 60 rows.

#### Column 51: `soc_to_clay_ratio`
* **Data Type:** `float64`
* **Physical Unit:** Dimensionless mass ratio ($\text{g C} / \text{g clay}$)
* **Mathematical Formula:**
  $$\text{soc\_to\_clay\_ratio} = \operatorname{round}\left(\frac{\text{topsoil\_soc\_g\_kg}}{\text{topsoil\_clay\_percent} \cdot 10.0}, 4\right) = \operatorname{round}\left(\frac{12.95}{25.78 \cdot 10}, 4\right) = \operatorname{round}\left(\frac{12.95}{257.8}, 4\right) = 0.0502$$
* **Scientific Basis:** **Dexter et al. (2008) Structural Vulnerability Index**. Soil Organic Carbon (SOC) acts as the biological binding agent stabilizing clay minerals into water-stable aggregates.
* **Interpretation Thresholds (Dexter et al.):**
  * $> 0.100$ ($1:10$): Structurally resilient, complexed clay, high aggregate stability.
  * $0.050 - 0.100$: Moderate structural stability.
  * $< 0.050$ ($1:20$): Degraded structural stability, prone to surface crusting, slaking, and erosion.
* **Observed Value:** Constant $0.0502$ across all 60 rows, indicating borderline structural vulnerability in the regional agricultural topsoil.

---

## 7. Operational Limitations & Generalization Safeguards

1. **Geographic Generalization Limitation:**  
   This dataset represents a single site in the Indo-Gangetic Plains of Punjab ($30.7392^\circ\text{N}, 76.7764^\circ\text{E}$). The statistical soil properties and calibrated climate dynamics cannot be generalized to other agro-climatic zones (e.g., peninsular black cotton soils, arid Rajasthan sands, or humid sub-tropical eastern plains) without acquiring new site-specific SoilGrids and NASA POWER coordinates.
2. **Field-Scale vs. Grid-Scale Spatial Disparity:**  
   NASA POWER data represents a ~50 km grid cell, and SoilGrids represents a 250 m pixel. This dataset is engineered for regional hydro-thermal vulnerability screening and regional early warning, **NOT for field-level agricultural diagnostics, precision variable-rate fertilization, or individual parcel title assessments**.
3. **Absence of Ground-Truth Validation Labels:**  
   No physical soil core degradation measurements or crop yield loss ground-truth labels are provided. Consequently, downstream risk scores produced from this table represent an **expert-calibrated, deterministic agronomic index**, NOT an empirical machine learning regression trained on historical land degradation outcomes.
4. **Temporal Soil Invariance:**  
   Soil properties are modeled as static regional baselines. While physical soil texture (sand, silt, clay) changes negligibly over 5-year periods, dynamic changes in soil organic carbon or seasonal pH fluctuations due to fertilizer application are not captured by static digital soil maps.
