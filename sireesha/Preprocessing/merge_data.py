"""
Data Merging Module.

Combines validated climate/environmental time-series observations and SoilGrids soil properties,
aligning by study region and coordinates, and preserving temporal features, units,
and authoritative source attributions.
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional

import pandas as pd
import yaml

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Preprocessing.clean_data import clean_climate_dataframe, clean_soil_dataframe
from src.Preprocessing.validate_data import (
    validate_climate_data,
    validate_soil_data,
    validate_combined_features
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("merge_data")


def load_config(config_path: str = "config/settings.yaml") -> Dict[str, Any]:
    """Load settings from YAML file."""
    path = Path(config_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / config_path
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def calculate_topsoil_weighted_averages(df_soil: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate depth-weighted topsoil (0-30cm) baseline features from layer data.
    Depths:
      - 0-5cm: thickness 5cm
      - 5-15cm: thickness 10cm
      - 15-30cm: thickness 15cm
      Total: 30cm
    """
    weights = {
        "0-5cm": 5.0,
        "5-15cm": 10.0,
        "15-30cm": 15.0
    }

    soil_dict = {}
    first_row = df_soil.iloc[0]
    soil_dict["nominal_latitude"] = first_row["nominal_latitude"]
    soil_dict["nominal_longitude"] = first_row["nominal_longitude"]
    soil_dict["sampled_latitude"] = first_row["sampled_latitude"]
    soil_dict["sampled_longitude"] = first_row["sampled_longitude"]
    soil_dict["soil_source"] = first_row["data_source"]

    # Pivot layer specific columns
    for _, row in df_soil.iterrows():
        depth_tag = row["depth_interval"].replace("-", "_").replace("cm", "")
        soil_dict[f"ph_{depth_tag}cm"] = row["soil_ph"]
        soil_dict[f"clay_{depth_tag}cm_percent"] = row["clay_percent"]
        soil_dict[f"sand_{depth_tag}cm_percent"] = row["sand_percent"]
        soil_dict[f"silt_{depth_tag}cm_percent"] = row["silt_percent"]
        soil_dict[f"soc_{depth_tag}cm_g_kg"] = row["soc_g_kg"]

    # Weighted mean across 0-30cm
    total_weight = 0.0
    weighted_ph = 0.0
    weighted_clay = 0.0
    weighted_sand = 0.0
    weighted_silt = 0.0
    weighted_soc = 0.0

    for _, row in df_soil.iterrows():
        depth = row["depth_interval"]
        w = weights.get(depth, 1.0)
        total_weight += w
        weighted_ph += row["soil_ph"] * w
        weighted_clay += row["clay_percent"] * w
        weighted_sand += row["sand_percent"] * w
        weighted_silt += row["silt_percent"] * w
        weighted_soc += row["soc_g_kg"] * w

    if total_weight > 0:
        soil_dict["topsoil_ph_mean"] = round(weighted_ph / total_weight, 2)
        soil_dict["topsoil_clay_percent"] = round(weighted_clay / total_weight, 2)
        soil_dict["topsoil_sand_percent"] = round(weighted_sand / total_weight, 2)
        soil_dict["topsoil_silt_percent"] = round(weighted_silt / total_weight, 2)
        soil_dict["topsoil_soc_g_kg"] = round(weighted_soc / total_weight, 2)

    return soil_dict


def merge_datasets(config_path: str = "config/settings.yaml") -> pd.DataFrame:
    """
    Merge climate, soil moisture/temperature observations, and SoilGrids soil properties
    into data/processed/combined_features.csv.
    """
    config = load_config(config_path)

    climate_path = PROJECT_ROOT / config["climate"]["processed_output_path"]
    soil_path = PROJECT_ROOT / config["soil"]["processed_output_path"]
    combined_path = PROJECT_ROOT / config["pipeline"]["combined_output_path"]

    if not climate_path.exists():
        raise FileNotFoundError(f"Climate data file not found at {climate_path}. Run climate collection first.")
    if not soil_path.exists():
        raise FileNotFoundError(f"Soil data file not found at {soil_path}. Run soil collection first.")

    logger.info("Loading processed climate/environmental data from %s", climate_path)
    df_climate = pd.read_csv(climate_path)
    logger.info("Loading processed soil data from %s", soil_path)
    df_soil = pd.read_csv(soil_path)

    # Clean and validate input datasets
    df_climate = clean_climate_dataframe(df_climate)
    is_clim_valid, clim_msg = validate_climate_data(df_climate)
    if not is_clim_valid:
        raise ValueError(f"Climate data validation failed: {clim_msg}")
    logger.info(clim_msg)

    df_soil = clean_soil_dataframe(df_soil)
    is_soil_valid, soil_msg = validate_soil_data(df_soil)
    if not is_soil_valid:
        raise ValueError(f"Soil data validation failed: {soil_msg}")
    logger.info(soil_msg)

    # Verify region compatibility
    clim_region = df_climate["region"].iloc[0]
    soil_region = df_soil["region"].iloc[0]
    if clim_region != soil_region:
        raise ValueError(f"Region mismatch! Climate region '{clim_region}' != Soil region '{soil_region}'")

    # Calculate soil baseline summary features
    soil_features = calculate_topsoil_weighted_averages(df_soil)

    # Combine soil baseline and monthly environmental records
    combined_rows = []
    for _, clim_row in df_climate.iterrows():
        row_data = {
            "region": clim_row["region"],
            "nominal_latitude": soil_features["nominal_latitude"],
            "nominal_longitude": soil_features["nominal_longitude"],
            "sampled_latitude": soil_features["sampled_latitude"],
            "sampled_longitude": soil_features["sampled_longitude"],
            "year": int(clim_row["year"]),
            "month": int(clim_row["month"]),
            "date": clim_row["date"],

            # Atmospheric Climate Observations
            "air_temperature_c": clim_row.get("air_temperature_c", clim_row.get("temperature_c")),
            "temperature_c": clim_row.get("temperature_c", clim_row.get("air_temperature_c")),
            "air_humidity_percent": clim_row.get("air_humidity_percent", clim_row.get("humidity_percent")),
            "humidity_percent": clim_row.get("humidity_percent", clim_row.get("air_humidity_percent")),
            "precipitation_mm_day": clim_row["precipitation_mm_day"],

            # Soil Environmental Observations (NASA POWER)
            "soil_temperature_layer1_c": clim_row.get("soil_temperature_layer1_c"),
            "soil_moisture_surface_fraction": clim_row.get("soil_moisture_surface_fraction"),
            "soil_moisture_rootzone_fraction": clim_row.get("soil_moisture_rootzone_fraction"),

            # Baseline Topsoil Features (0-30cm Depth-Weighted Averages from SoilGrids)
            "topsoil_ph_mean": soil_features["topsoil_ph_mean"],
            "topsoil_clay_percent": soil_features["topsoil_clay_percent"],
            "topsoil_sand_percent": soil_features["topsoil_sand_percent"],
            "topsoil_silt_percent": soil_features["topsoil_silt_percent"],
            "topsoil_soc_g_kg": soil_features["topsoil_soc_g_kg"],

            # Layer-Specific Soil Features
            "ph_0_5cm": soil_features.get("ph_0_5cm"),
            "ph_5_15cm": soil_features.get("ph_5_15cm"),
            "ph_15_30cm": soil_features.get("ph_15_30cm"),
            "clay_0_5cm_percent": soil_features.get("clay_0_5cm_percent"),
            "clay_5_15cm_percent": soil_features.get("clay_5_15cm_percent"),
            "clay_15_30cm_percent": soil_features.get("clay_15_30cm_percent"),
            "sand_0_5cm_percent": soil_features.get("sand_0_5cm_percent"),
            "sand_5_15cm_percent": soil_features.get("sand_5_15cm_percent"),
            "sand_15_30cm_percent": soil_features.get("sand_15_30cm_percent"),
            "silt_0_5cm_percent": soil_features.get("silt_0_5cm_percent"),
            "silt_5_15cm_percent": soil_features.get("silt_5_15cm_percent"),
            "silt_15_30cm_percent": soil_features.get("silt_15_30cm_percent"),
            "soc_0_5cm_g_kg": soil_features.get("soc_0_5cm_g_kg"),
            "soc_5_15cm_g_kg": soil_features.get("soc_5_15cm_g_kg"),
            "soc_15_30cm_g_kg": soil_features.get("soc_15_30cm_g_kg"),

            # Provenance / Source Attribution
            "climate_source": clim_row["data_source"],
            "soil_source": soil_features["soil_source"]
        }
        combined_rows.append(row_data)

    df_combined = pd.DataFrame(combined_rows)

    # Validate combined features
    is_comb_valid, comb_msg = validate_combined_features(df_combined)
    if not is_comb_valid:
        raise ValueError(f"Combined features validation failed: {comb_msg}")
    logger.info(comb_msg)

    # Save to file
    combined_path.parent.mkdir(parents=True, exist_ok=True)
    df_combined.to_csv(combined_path, index=False)
    logger.info("Successfully created combined dataset at: %s", combined_path)
    return df_combined


if __name__ == "__main__":
    df = merge_datasets()
    print("\nCombined Features Preview:")
    print(df.head())
    print(f"\nTotal Records: {len(df)}")
    print(f"Columns: {list(df.columns)}")
