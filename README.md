# Soil Sentinel — Automated Data Collection Pipeline

Soil Sentinel is an automated data collection and preprocessing pipeline for agricultural risk monitoring and soil health intelligence. It automatically queries authoritative environmental data sources without requiring manual browser downloads.

## Data Sources

1. **NASA POWER API (Agroclimatology Community)**
   - **Service Endpoint:** `https://power.larc.nasa.gov/api/temporal/monthly/point`
   - **Temporal Resolution:** Monthly (2020–2024, 60 records)
   - **Parameters Collected:**
     - `T2M`: Air Temperature at 2 Meters (°C)
     - `RH2M`: Air Relative Humidity at 2 Meters (%)
     - `PRECTOTCORR`: Precipitation Corrected (mm/day)
     - `GWETTOP`: Surface Soil Wetness (0 to 1 fraction)
     - `GWETROOT`: Root Zone Soil Wetness (0 to 1 fraction)
     - `TSOIL1`: Soil Temperature Layer 1 0–10 cm (°C)
   - **Raw Storage:** `data/raw/climate/nasa_power_monthly_2020_2024_30.73_76.77.json`
   - **Processed Storage:** `data/processed/climate_data.csv`

2. **ISRIC SoilGrids v2.0**
   - **Service Endpoint:** `https://files.isric.org/soilgrids/latest/data/` (Official VRT Streaming Service)
   - **Depth Intervals:** `0-5cm`, `5-15cm`, `15-30cm`
   - **Properties Collected:**
     - `phh2o`: Soil pH in H₂O solution (raw DN / 10 = standard pH)
     - `clay`: Clay mass fraction (raw DN / 10 = %)
     - `sand`: Sand mass fraction (raw DN / 10 = %)
     - `silt`: Silt mass fraction (raw DN / 10 = %)
     - `soc`: Soil Organic Carbon (raw DN / 10 = g/kg)
   - **Raw Storage:** `data/raw/soil/soilgrids_raw_metadata.json`
   - **Processed Storage:** `data/processed/soil_data.csv`

3. **Combined Features**
   - **Processed Storage:** `data/processed/combined_features.csv`
   - Aligns monthly climate time series with regional depth-weighted topsoil baseline features (0–30 cm).

4. **Standardized Feature Table**
   - **Generated Storage:** `data/feature_table.csv`
   - Engineered feature table containing 53 validated features including temporal context, lag/rolling precipitation, thermal coupling, moisture gradients, and soil texture ratios.
   - **Data Dictionary:** Complete feature-by-feature definitions, units, formulas, provenance, and limitations are documented in [`docs/data_dictionary.md`](docs/data_dictionary.md).

---

## Study Region Configuration

Configured in `config/settings.yaml`:
- **Region:** Indo-Gangetic Agricultural Plains / Punjab
- **Nominal Coordinates:** Latitude `30.7300° N`, Longitude `76.7700° E`
- **Sampled Agricultural Coordinates:** Latitude `30.7392° N`, Longitude `76.7764° E` (1.0 km distance from urban center, avoiding NODATA urban masking)
- **Time Window:** 2020–2024 (Monthly)

---

## Execution Instructions

From the project root in the Windows terminal or VS Code terminal:

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the automated data collection pipeline
python src/data_collection/download_all.py

# 3. Generate the engineered feature table
python src/features.py
```

### Optional Flags
- `--force`: Force re-download and bypass cached raw API responses:
  ```powershell
  python src/data_collection/download_all.py --force
  ```
- Or run through the project entrypoint:
  ```powershell
  python main.py
  ```

---

## Risk Scoring & Prediction Engine (Member 2)

Soil Sentinel implements a transparent, deterministic **Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index** ([`src/Model/risk_scoring.py`](src/Model/risk_scoring.py)).

> [!NOTE]
> **Heuristic Agronomic Index (Not a Trained ML Model):**  
> The engine is a deterministic, rule-based screening index calibrated to agronomic baselines in the Indo-Gangetic Plains. It does **not** employ a trained machine learning model, statistical regression, or neural network.

### Exact Component Scores, Normalization, and Weights

| Sub-Index Group | Contributing Indicator | Feature Source & Unit | Scaling & Normalization Range | Weight |
| :--- | :--- | :--- | :--- | :---: |
| **Dynamic Environmental Stress (70%)** | Root-zone Soil Moisture Deficit | NASA POWER `GWETROOT` (fraction) | Inverted: $[0.75 \rightarrow 0.0, 0.25 \rightarrow 100.0]$ | **30%** (`0.30`) |
| | Meteorological Recharge Deficit | NASA POWER rolling 3m mean ($\text{mm/day}$) | Inverted: $[6.0 \rightarrow 0.0, 0.5 \rightarrow 100.0]$, damped by Moisture Buffering Factor $\beta \in [0.50, 1.00]$ | **25%** (`0.25`) |
| | Topsoil Thermal Stress | NASA POWER `TSOIL1` ($^\circ\text{C}$) | Direct: $[24.0 \rightarrow 0.0, 38.0 \rightarrow 100.0]$ | **15%** (`0.15`) |
| **Static Baseline Soil Vulnerability (30%)** | Topsoil SOC Depletion | SoilGrids `soc` ($0–30\,\text{cm}$, $\text{g/kg}$) | Inverted: $[25.0 \rightarrow 0.0, 5.0 \rightarrow 100.0]$ | **15%** (`0.15`) |
| | Topsoil pH Deviation | SoilGrids `phh2o` ($0–30\,\text{cm}$) | Piecewise: $0.0$ for $[6.5, 7.5]$, linear deviation up to $\pm 2.0$ units $\rightarrow 100.0$ | **15%** (`0.15`) |
| **Total** | | | **All 5 Component Weights Sum to Exactly 1.00** | **100%** (`1.00`) |

### Moisture Buffering Formula
Precipitation deficit penalty is adjusted by the rootzone moisture buffering factor $\beta$:
$$\text{Score}_{\text{precip}} = \text{round}(\text{RawScore} \times \beta, 2)$$
$$\beta = \begin{cases} 1.00 & \text{if } \text{moisture} \le 0.35 \text{ (depleted root-zone; 100% penalty retained)} \\ 0.50 & \text{if } \text{moisture} \ge 0.65 \text{ (ample root-zone; 50% maximum relief)} \\ 1.0 - 0.5 \times \frac{\text{moisture} - 0.35}{0.65 - 0.35} & \text{if } 0.35 < \text{moisture} < 0.65 \text{ (intermediate buffering)} \end{cases}$$

### Composite Score and Risk Categories
$$\text{Composite Score} = \operatorname{round}\left(\sum_{i=1}^{5} \text{Weight}_i \times \text{Score}_i, 2\right) \in [0.0, 100.0]$$
- **Low Risk:** $[0.0, 35.0)$
- **Medium Risk:** $[35.0, 65.0)$
- **High Risk:** $[65.0, 100.0]$

---

## Prediction & Inference Execution

```powershell
# 1. Permissive Prediction (Default: single-month fallback for boundary records 2020-01 and 2020-02)
python src/Model/predict.py --input data/feature_table.csv --output outputs/predictions.csv --audit-log logs/audit_log.csv

# 2. Strict Prediction (Rejects unobserved rolling history with INSUFFICIENT_HISTORY)
python src/Model/predict.py --input data/feature_table.csv --output outputs/predictions_strict.csv --strict --audit-log logs/audit_log.csv
```

---

## Validation & Integrity

- **Missing Values:** Zero unexpected nulls or fabricated records. Exactly 1 boundary NaN in 1-month lags and 2 boundary NaNs in 3-month rolling windows reflecting unobserved historical start values.
- **Physical Bounds:** Temperature (-50°C to 60°C), Humidity (0% to 100%), Precipitation (0 to 500 mm/day), Soil pH (3.0 to 11.0), Texture sum (clay + sand + silt ≈ 100%).
- **Audit Trail:** Cumulative, append-only CSV audit logger (`logs/audit_log.csv`) recording timestamped ISO 8601 UTC entries without storing raw features or credentials.
- **Data Dictionary:** Detailed feature catalog and operational limitations are documented in [`docs/data_dictionary.md`](docs/data_dictionary.md).
