# SoilSentinel — Dataset & Repository ML Audit Report

**Date of Audit:** October 2026  
**Auditor:** Senior ML Engineer & Backend Architect  
**Project:** SoilSentinel (IBM Z Datathon 2026)  
**Dataset Reference:** [`data/feature_table.csv`](../data/feature_table.csv)  

---

## Executive Summary

This audit assesses the readiness of the SoilSentinel dataset and backend codebase for machine learning model training and evaluation. SoilSentinel currently uses an empirical, rule-based **Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index** calibrated to agronomic ranges in the Indo-Gangetic Plains of Punjab.

To meet datathon requirements while preserving scientific integrity, this audit evaluates dataset dimensions, temporal and spatial structure, feature provenance, label availability, target leakage risks, artifact states, and frontend interface contracts.

---

## 1. Dataset Dimensions, Spatial Context & Data Types

* **Dimensions:** 60 rows × 53 columns.
* **Temporal Span:** January 2020 through December 2024 (`2020-01` to `2024-12`). Continuous monthly time steps ($N = 60$).
* **Spatial Configuration:** 
  * Single representative agricultural location in Punjab, India (Indo-Gangetic Agricultural Plains).
  * Nominal Reference: Latitude `30.7300° N`, Longitude `76.7700° E` (Chandigarh regional reference point).
  * Sampled Coordinate: Latitude `30.7392° N`, Longitude `76.7764° E` (1.0 km radius offset to sample valid agricultural land outside urban `NODATA` masks).
  * **Critical Spatial Property:** The 60 observations represent a single temporal sequence at **one location**, not 60 distinct geographic farms.
* **Duplicates:** 0 duplicate records.
* **Data Types Breakdown:**
  * `float64` (43 columns): Continuous climate measurements, soil depth intervals, texture percentages, moisture gradients, aridity indices.
  * `int64` (3 columns): Temporal calendar markers (`year`, `month`, `quarter`).
  * `object / string` (7 columns): `region`, `date`, `season`, `climate_source`, `soil_source`, `soil_measurement_type`, `climate_measurement_type`.

---

## 2. Missing Values & Boundary NaNs Analysis

* **Total Matrix Cells:** $60 \times 53 = 3,180$ cells.
* **Total Missing Values:** Exactly 6 cells (0.19% missingness across the dataset).
* **Missing Value Locations:**
  1. `precipitation_lag1_mm_day`: Exactly 1 NaN at row 0 (`2020-01`).
  2. `air_temperature_lag1_c`: Exactly 1 NaN at row 0 (`2020-01`).
  3. `precipitation_rolling_3m_mean_mm_day`: Exactly 2 NaNs at rows 0 and 1 (`2020-01`, `2020-02`).
  4. `precipitation_rolling_3m_sum_mm_day`: Exactly 2 NaNs at rows 0 and 1 (`2020-01`, `2020-02`).
* **Root Cause & Scientific Meaning:**
  These NaNs are **boundary limits of antecedent rolling history** at the start of the 5-year observation window. They do **not** represent 0.0 mm rainfall or 0°C temperature. Zero-filling would falsely invent severe drought/freeze events.
* **Zero-Missingness Columns:** All other 49 columns have **0 NaNs (100% complete)**.

---

## 3. Ground Truth vs. Proxy Label Availability

* **Independent Observed Soil Degradation Labels:** **NONE AVAILABLE.**
  * Atmospheric and land-surface data originate from **NASA POWER MERRA-2 / GEOS Catchment Land Surface Model** simulations.
  * Soil chemical and textural properties originate from **ISRIC SoilGrids v2.0 Quantile Random Forest** spatial predictions.
  * No in-situ ground sensors, soil loss runoff plots, physical lysimeters, or laboratory core degradation assays exist.
* **Proxy Target Formulation:**
  * The dataset does not contain an intrinsic target column.
  * The existing rule-based engine (`src/Model/risk_scoring.py`) calculates a continuous index $[0.0, 100.0]$ and categorizes records into `Low`, `Medium`, or `High`.
  * **Proxy Label Distribution ($N = 60$):**
    * `Medium`: 33 records (55.0%)
    * `Low`: 24 records (40.0%)
    * `High`: 3 records (5.0%) — observed exclusively in May and June (2022-05, 2024-05, 2024-06) under extreme thermal and hydrological stress.
* **Proxy-Learning Disclaimer:**
  Any model trained on these labels is a **surrogate approximation model** learning the heuristic decision boundary of the rule-based engine. It must **not** be presented as a validated, independently measured soil degradation forecasting model.

---

## 4. Current Rule-Based Scoring Engine Architecture

The rule-based index in `src/Model/risk_scoring.py` computes:
$$\text{Composite Score} = 0.70 \times \text{Dynamic Environmental Stress} + 0.30 \times \text{Baseline Soil Vulnerability}$$

Comprising 5 normalized indicators summing to weight 1.00:
1. **Root-zone Soil Moisture Deficit (Weight: 0.30):** Inverted piecewise mapping of `soil_moisture_rootzone_fraction` from $[0.75 \rightarrow 0.0, 0.25 \rightarrow 100.0]$.
2. **Precipitation Deficit (Weight: 0.25):** Inverted mapping of 3-month rolling mean precipitation from $[6.0 \rightarrow 0.0, 0.5 \rightarrow 100.0]$, modulated by root-zone moisture buffering factor $\beta \in [0.50, 1.00]$.
3. **Topsoil Thermal Stress (Weight: 0.15):** Direct mapping of `soil_temperature_layer1_c` from $[24.0^\circ\text{C} \rightarrow 0.0, 38.0^\circ\text{C} \rightarrow 100.0]$.
4. **Static SOC Depletion Vulnerability (Weight: 0.15):** Inverted mapping of `topsoil_soc_g_kg` from $[25.0\,\text{g/kg} \rightarrow 0.0, 5.0\,\text{g/kg} \rightarrow 100.0]$.
5. **Static pH Neutrality Deviation (Weight: 0.15):** Absolute piecewise deviation from neutral range $[6.5, 7.5]$, mapped up to $\pm 2.0$ units $\rightarrow 100.0$.

**Thresholds:**
* `Low Risk`: $[0.0, 35.0)$
* `Medium Risk`: $[35.0, 65.0)$
* `High Risk`: $[65.0, 100.0]$

---

## 5. Target Leakage & Feature Selection Analysis

To train a defensible surrogate model without circular reasoning or target leakage:

### Prohibited Input Features (Direct Target Leakage)
* `score` (Composite risk score)
* `risk_category` (Classification target)
* `dynamic_environmental_stress` (Sub-index)
* `baseline_soil_vulnerability` (Sub-index)
* `moisture_deficit_sub_score`
* `precipitation_deficit_sub_score`
* `precipitation_deficit_raw_unbuffered`
* `moisture_buffering_factor`
* `thermal_stress_sub_score`
* `soc_vulnerability_sub_score`
* `ph_deviation_sub_score`
* `explanation`
* `status`

### Zero-Variance Features in the Punjab Site Record
Because this dataset tracks 60 monthly timesteps at a single location:
* Static soil baseline properties (`topsoil_ph_mean`, `topsoil_soc_g_kg`, `topsoil_clay_percent`, `topsoil_sand_percent`, `topsoil_silt_percent`, `ph_0_5cm`, etc.) have `nunique=1`.
* Identifiers and metadata (`region`, `nominal_latitude`, `nominal_longitude`, `sampled_latitude`, `sampled_longitude`, `climate_source`, `soil_source`) have `nunique=1`.
* These columns provide zero predictive variance across time and should be excluded from temporal model fitting or handled via automated variance filtering.

### Permissible Predictive Input Features ($X$)
Dynamic physical, meteorological, and agro-climatic covariates:
1. `air_temperature_c`: Ambient 2-meter air temperature (°C).
2. `air_humidity_percent`: Relative air humidity (%).
3. `precipitation_mm_day`: Monthly precipitation rate (mm/day).
4. `soil_temperature_layer1_c`: Topsoil (0–10 cm) temperature (°C).
5. `soil_moisture_surface_fraction`: Surface wetness fraction (0–1).
6. `soil_moisture_rootzone_fraction`: Root-zone wetness fraction (0–1).
7. `precipitation_lag1_mm_day`: Prior month precipitation rate (mm/day).
8. `air_temperature_lag1_c`: Prior month air temperature (°C).
9. `precipitation_rolling_3m_mean_mm_day`: 3-month rolling mean precipitation (mm/day).
10. `temp_soil_air_diff_c`: Thermal coupling gradient (`soil_temp - air_temp`).
11. `soil_moisture_depth_gradient`: Vertical water gradient (`rootzone_wetness - surface_wetness`).
12. `monthly_aridity_index`: De Martonne aridity index (`precip / (temp + 10)`).
13. `month_sin`, `month_cos`: Cyclical seasonal components.

---

## 6. Model Artifact & Safety Guard Audit

* **File:** `models/soil_risk_model.joblib`.
* **Current State:** 0-byte unpopulated placeholder.
* **Code Implementation:** `src/Model/model.py` provides `load_trained_model()`, which raises `RuntimeError("SoilSentinel does not load or execute trained ML model binaries...")`.
* **Existing Tests:** `tests/test_predict.py` contains `TestModelArtifactSafetyGuard`, checking that `load_trained_model()` raises `RuntimeError` and `soil_risk_model.joblib` is 0 bytes.
* **Refactoring Requirement:**
  * Train and serialize a real, validated model pipeline (`models/soil_risk_model.joblib`).
  * Save preprocessor separately or within the unified pipeline, along with `models/model_metadata.json`.
  * Update `src/Model/model.py` to securely load, inspect, and validate the model binary against corrupt or zero-byte files.
  * Update the test suite so that safety guards verify genuine validation while asserting the trained model executes accurately on real feature rows.

---

## 7. Frontend Integration Contract & Shared Fields

* **Shared Interface Contract:** [`docs/dashboard_handoff_contract.md`](../docs/dashboard_handoff_contract.md).
* **Teammates Consuming Backend:** Blessi (Streamlit dashboard / Farmer UI) and Smruthi (Researcher UI / Member 2 outlook engine).
* **Consolidated Payload Keys:**
  1. `metadata`
  2. `risk_assessment`
  3. `recommendations`
  4. `recovery_tracking`
  5. `crop_eligibility`
  6. `scenario_comparison`
  7. `historical_series`
  8. `audit_reference`
* **Non-Breaking Integration Strategy:**
  Add a dedicated `ml_prediction` key to `SoilSentinelService.get_dashboard_payload()` without modifying or deleting any of the existing 7 blocks or modifying rule-based calculations.
