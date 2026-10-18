"""
SoilSentinel - Multi-District Feature Table Engineering for Punjab.

Constructs the standardized multi-district spatial-temporal ML feature dataset:
data/processed/punjab_multidistrict_features.csv

Integrates:
1. Monthly Climate & Hydrology from NASA POWER (2020-01 to 2024-12, 60 months per district):
   - T2M (air temperature)
   - RH2M (relative humidity)
   - PRECTOTCORR (precipitation)
   - GWETTOP (surface soil wetness)
   - GWETROOT (root-zone soil wetness)
   - TSOIL1 (topsoil temperature)
2. Static Pedological Baseline from ISRIC SoilGrids v2.0:
   - pH (0-30cm mean)
   - Clay, Sand, Silt mass fractions (0-30cm mean %)
   - Soil Organic Carbon (0-30cm mean g/kg)
3. Dynamic Lag and Interaction Features (calculated per district with zero future leakage):
   - precipitation_lag1_mm_day
   - air_temperature_lag1_c
   - precipitation_rolling_3m_mean_mm_day
   - temp_soil_air_diff_c
   - soil_moisture_depth_gradient
   - monthly_aridity_index
   - month_sin, month_cos
4. Deterministic Heuristic Risk Scoring & Surrogate Labels:
   - Evaluated via src.Model.risk_scoring to generate composite score & risk_category.

Covers 7 representative districts across all agro-climatic zones of Punjab:
Total Samples: 7 districts x 60 months = 420 spatial-temporal observations.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Model.predict import predict_record

RAW_CLIMATE_DIR = PROJECT_ROOT / "data" / "raw" / "climate"
RAW_SOIL_DIR = PROJECT_ROOT / "data" / "raw" / "soil"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
LOGS_DIR = PROJECT_ROOT / "data" / "logs"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging
log_file = LOGS_DIR / "multidistrict_feature_build.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("multidistrict_features")

PUNJAB_DISTRICTS = [
    {
        "district_id": "sas_nagar_chandigarh",
        "district_name": "SAS Nagar / Mohali (Baseline Parcel)",
        "zone": "Eastern Plain / Foothill Margin",
        "latitude": 30.73,
        "longitude": 76.77,
        "climate_file": "nasa_power_monthly_2020_2024_30.73_76.77.json",
    },
    {
        "district_id": "ludhiana",
        "district_name": "Ludhiana (Central Agricultural Hub)",
        "zone": "Central Plain Zone",
        "latitude": 30.90,
        "longitude": 75.85,
        "climate_file": "nasa_power_monthly_2020_2024_30.90_75.85_ludhiana.json",
    },
    {
        "district_id": "bathinda",
        "district_name": "Bathinda (Cotton / Semi-Arid / Saline Belt)",
        "zone": "South-Western Semi-Arid Zone",
        "latitude": 30.21,
        "longitude": 74.95,
        "climate_file": "nasa_power_monthly_2020_2024_30.21_74.95_bathinda.json",
    },
    {
        "district_id": "jalandhar",
        "district_name": "Jalandhar (Doaba Cereal / Vegetable Belt)",
        "zone": "Central Plain Zone",
        "latitude": 31.33,
        "longitude": 75.58,
        "climate_file": "nasa_power_monthly_2020_2024_31.33_75.58_jalandhar.json",
    },
    {
        "district_id": "patiala",
        "district_name": "Patiala (Southern Intensive Plain)",
        "zone": "Central Plain Zone",
        "latitude": 30.34,
        "longitude": 76.38,
        "climate_file": "nasa_power_monthly_2020_2024_30.34_76.38_patiala.json",
    },
    {
        "district_id": "amritsar",
        "district_name": "Amritsar (Western Plain / Border Belt)",
        "zone": "Western Plain Zone",
        "latitude": 31.63,
        "longitude": 74.87,
        "climate_file": "nasa_power_monthly_2020_2024_31.63_74.87_amritsar.json",
    },
    {
        "district_id": "hoshiarpur",
        "district_name": "Hoshiarpur (Sub-Mountainous Kandi / Erosion Belt)",
        "zone": "Sub-Mountainous Undulating Kandi Zone",
        "latitude": 31.53,
        "longitude": 75.92,
        "climate_file": "nasa_power_monthly_2020_2024_31.53_75.92_hoshiarpur.json",
    },
]


def load_soilgrids_district_properties() -> Dict[str, Dict[str, float]]:
    soilgrids_file = RAW_SOIL_DIR / "soilgrids_punjab_districts_metadata.json"
    dist_props = {}

    if soilgrids_file.exists():
        with open(soilgrids_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        for dist_id, info in data.get("districts", {}).items():
            props = info.get("properties", {})
            # Compute topsoil mean (0-30cm across the 3 depths)
            ph_vals = [props.get(f"ph_{d.replace('-', '_')}") for d in ["0-5cm", "5-15cm", "15-30cm"]]
            clay_vals = [props.get(f"clay_{d.replace('-', '_')}") for d in ["0-5cm", "5-15cm", "15-30cm"]]
            sand_vals = [props.get(f"sand_{d.replace('-', '_')}") for d in ["0-5cm", "5-15cm", "15-30cm"]]
            silt_vals = [props.get(f"silt_{d.replace('-', '_')}") for d in ["0-5cm", "5-15cm", "15-30cm"]]
            soc_vals = [props.get(f"soc_{d.replace('-', '_')}") for d in ["0-5cm", "5-15cm", "15-30cm"]]

            dist_props[dist_id] = {
                "topsoil_ph_mean": round(float(np.nanmean([v for v in ph_vals if v is not None])), 2),
                "topsoil_clay_percent": round(float(np.nanmean([v for v in clay_vals if v is not None])), 2),
                "topsoil_sand_percent": round(float(np.nanmean([v for v in sand_vals if v is not None])), 2),
                "topsoil_silt_percent": round(float(np.nanmean([v for v in silt_vals if v is not None])), 2),
                "topsoil_soc_g_kg": round(float(np.nanmean([v for v in soc_vals if v is not None])), 2),
            }

    # If sas_nagar is not in dist_props or needs fallback, use existing baseline feature_table values
    baseline_ft = PROJECT_ROOT / "data" / "feature_table.csv"
    if baseline_ft.exists():
        df_base = pd.read_csv(baseline_ft)
        if "sas_nagar_chandigarh" not in dist_props:
            dist_props["sas_nagar_chandigarh"] = {
                "topsoil_ph_mean": float(df_base["topsoil_ph_mean"].iloc[0]),
                "topsoil_clay_percent": float(df_base["topsoil_clay_percent"].iloc[0]),
                "topsoil_sand_percent": float(df_base["topsoil_sand_percent"].iloc[0]),
                "topsoil_silt_percent": float(df_base["topsoil_silt_percent"].iloc[0]),
                "topsoil_soc_g_kg": float(df_base["topsoil_soc_g_kg"].iloc[0]),
            }

    return dist_props


def parse_nasa_power_file(filepath: Path) -> pd.DataFrame:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    params = data.get("properties", {}).get("parameter", {})
    records_by_date = {}

    param_map = {
        "T2M": "air_temperature_c",
        "RH2M": "air_humidity_percent",
        "PRECTOTCORR": "precipitation_mm_day",
        "TSOIL1": "soil_temperature_layer1_c",
        "GWETTOP": "soil_moisture_surface_fraction",
        "GWETROOT": "soil_moisture_rootzone_fraction",
    }

    for nasa_param, col_name in param_map.items():
        if nasa_param not in params:
            continue
        for date_key, val in params[nasa_param].items():
            # Skip annual 13th month entry e.g. '202013'
            if date_key.endswith("13"):
                continue
            year_str = date_key[:4]
            month_str = date_key[4:]
            date_formatted = f"{year_str}-{month_str}"

            if date_formatted not in records_by_date:
                records_by_date[date_formatted] = {
                    "date": date_formatted,
                    "year": int(year_str),
                    "month": int(month_str),
                }

            val_float = float(val) if val is not None and val != -999.0 else np.nan
            records_by_date[date_formatted][col_name] = val_float

    df = pd.DataFrame(list(records_by_date.values())).sort_values("date").reset_index(drop=True)
    return df


def build_multidistrict_features() -> pd.DataFrame:
    logger.info("=== Building Punjab Multi-District Feature Table ===")
    soil_props = load_soilgrids_district_properties()

    all_district_dfs = []

    for dist in PUNJAB_DISTRICTS:
        dist_id = dist["district_id"]
        climate_path = RAW_CLIMATE_DIR / dist["climate_file"]

        if not climate_path.exists():
            logger.error(f"Missing climate file for {dist_id} at {climate_path}")
            continue

        df_clim = parse_nasa_power_file(climate_path)
        logger.info(f"Loaded {len(df_clim)} climate months for {dist_id}")

        # Attach spatial context
        df_clim["district_id"] = dist_id
        df_clim["district_name"] = dist["district_name"]
        df_clim["agro_climatic_zone"] = dist["zone"]
        df_clim["latitude"] = dist["latitude"]
        df_clim["longitude"] = dist["longitude"]

        # Attach soil properties
        sp = soil_props.get(dist_id, soil_props.get("sas_nagar_chandigarh", {}))
        df_clim["topsoil_ph_mean"] = sp.get("topsoil_ph_mean", 7.6)
        df_clim["topsoil_clay_percent"] = sp.get("topsoil_clay_percent", 24.6)
        df_clim["topsoil_sand_percent"] = sp.get("topsoil_sand_percent", 38.8)
        df_clim["topsoil_silt_percent"] = sp.get("topsoil_silt_percent", 36.6)
        df_clim["topsoil_soc_g_kg"] = sp.get("topsoil_soc_g_kg", 4.2)

        # Cyclic calendar features
        df_clim["month_sin"] = np.round(np.sin(2 * np.pi * df_clim["month"] / 12), 4)
        df_clim["month_cos"] = np.round(np.cos(2 * np.pi * df_clim["month"] / 12), 4)

        # Dynamic Lags and Rolling Windows (computed within each district series)
        df_clim["precipitation_lag1_mm_day"] = df_clim["precipitation_mm_day"].shift(1)
        df_clim["air_temperature_lag1_c"] = df_clim["air_temperature_c"].shift(1)
        df_clim["precipitation_rolling_3m_mean_mm_day"] = np.round(
            df_clim["precipitation_mm_day"].rolling(window=3, min_periods=3).mean(), 2
        )

        # Thermal and Hydrological Interactions
        df_clim["temp_soil_air_diff_c"] = np.round(
            df_clim["soil_temperature_layer1_c"] - df_clim["air_temperature_c"], 2
        )
        df_clim["soil_moisture_depth_gradient"] = np.round(
            df_clim["soil_moisture_rootzone_fraction"] - df_clim["soil_moisture_surface_fraction"], 4
        )
        df_clim["monthly_aridity_index"] = np.round(
            (df_clim["precipitation_mm_day"] * 30.0) / (df_clim["air_temperature_c"] + 10.0), 2
        )

        # Compute Rule-Engine Risk Score and Category for Each Record
        scores = []
        categories = []
        for _, row in df_clim.iterrows():
            rec_dict = row.to_dict()
            try:
                res = predict_record(rec_dict)
                scores.append(res.get("score"))
                categories.append(res.get("risk_category"))
            except Exception as e:
                scores.append(np.nan)
                categories.append(None)

        df_clim["score"] = scores
        df_clim["risk_category"] = categories

        all_district_dfs.append(df_clim)

    final_df = pd.concat(all_district_dfs, ignore_index=True)

    out_csv = PROCESSED_DIR / "punjab_multidistrict_features.csv"
    final_df.to_csv(out_csv, index=False)
    logger.info(
        f"Saved Multi-District Feature Table: {out_csv.name} "
        f"(Shape: {final_df.shape}, Districts: {final_df['district_id'].nunique()}, "
        f"Size: {out_csv.stat().st_size} bytes)"
    )

    return final_df


if __name__ == "__main__":
    df = build_multidistrict_features()
    print("\nMulti-District Feature Table Summary:")
    print(f"Shape: {df.shape}")
    print(f"Districts: {df['district_id'].value_counts().to_dict()}")
    print(f"Risk Categories: {df['risk_category'].value_counts().to_dict()}")
    print("\nSample Preview:")
    print(df[["district_id", "date", "air_temperature_c", "precipitation_mm_day", "score", "risk_category"]].head())
