"""
Soil Sentinel - Automated Data Collection & Pipeline Orchestrator.

Orchestrates automated collection and engineering of:
1. NASA POWER Climate Data (Temperature, Humidity, Precipitation)
2. ISRIC SoilGrids Soil Data (pH, Clay, Sand, Silt, Soil Organic Carbon)
3. Data Cleaning, Validation, and Feature Alignment (combined_features.csv)
4. Engineered Feature Table Generation (feature_table.csv)

Usage:
    python src/data_collection/download_all.py
    python src/data_collection/download_all.py --force
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Support both folder naming conventions
from src.Preprocessing.merge_data import merge_datasets, load_config
from src.Preprocessing.validate_data import (
    validate_climate_data,
    validate_soil_data,
    validate_combined_features
)

# Canonical imports from src.data_collection
from src.data_collection.nasa_power import NasaPowerCollector
from src.data_collection.soilgrids import SoilGridsCollector
from src.features import build_feature_table

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("download_all")


def run_pipeline(force: bool = False, config_path: str = "config/settings.yaml", feature_table_output_path: Optional[Path] = None):
    """
    Execute full data collection and feature generation pipeline.
    """
    logger.info("=================================================================")
    logger.info("         SOIL SENTINEL - AUTOMATED DATA COLLECTION PIPELINE      ")
    logger.info("=================================================================")

    config = load_config(config_path)
    region = config["study_region"]["name"]
    lat = config["study_region"]["latitude"]
    lon = config["study_region"]["longitude"]
    start_year = config["study_region"]["start_year"]
    end_year = config["study_region"]["end_year"]

    logger.info("Study Region : %s", region)
    logger.info("Coordinates  : Latitude %.4f, Longitude %.4f", lat, lon)
    logger.info("Time Range   : %s - %s", start_year, end_year)
    logger.info("Force Reload : %s", force)

    # 1. Collect NASA POWER Climate Data
    logger.info("\n--- STEP 1/4: NASA POWER Climate Data Collection ---")
    climate_collector = NasaPowerCollector(config_path=config_path)
    df_climate = climate_collector.run(force=force)

    # Validate Climate Data
    is_valid_clim, msg_clim = validate_climate_data(df_climate)
    if not is_valid_clim:
        raise ValueError(f"Climate data validation failed: {msg_clim}")
    logger.info("Climate Validation Passed: %s", msg_clim)

    # 2. Collect ISRIC SoilGrids Soil Data
    logger.info("\n--- STEP 2/4: ISRIC SoilGrids Soil Data Collection ---")
    soil_collector = SoilGridsCollector(config_path=config_path)
    df_soil = soil_collector.run(force=force)

    # Validate Soil Data
    is_valid_soil, msg_soil = validate_soil_data(df_soil)
    if not is_valid_soil:
        raise ValueError(f"Soil data validation failed: {msg_soil}")
    logger.info("Soil Validation Passed: %s", msg_soil)

    # 3. Combine Features
    logger.info("\n--- STEP 3/4: Feature Alignment and Dataset Combination ---")
    df_combined = merge_datasets(config_path=config_path)

    # Validate Combined Features
    is_valid_comb, msg_comb = validate_combined_features(df_combined)
    if not is_valid_comb:
        raise ValueError(f"Combined features validation failed: {msg_comb}")
    logger.info("Combined Features Validation Passed: %s", msg_comb)

    # 4. Generate Engineered Feature Table
    logger.info("\n--- STEP 4/4: Feature Engineering & Master Feature Table Generation ---")
    combined_file = PROJECT_ROOT / config["pipeline"]["combined_output_path"]
    if feature_table_output_path is not None:
        feature_file = Path(feature_table_output_path)
    else:
        feature_cfg_path = Path(config.get("pipeline", {}).get("feature_table_output_path", "data/feature_table.csv"))
        feature_file = feature_cfg_path if feature_cfg_path.is_absolute() else PROJECT_ROOT / feature_cfg_path

    df_features = build_feature_table(
        combined_path=combined_file,
        output_path=feature_file,
        config_path=config_path
    )

    # Final Summary Report
    climate_file = PROJECT_ROOT / config["climate"]["processed_output_path"]
    soil_file = PROJECT_ROOT / config["soil"]["processed_output_path"]

    logger.info("\n=================================================================")
    logger.info("                   COLLECTION PIPELINE REPORT                    ")
    logger.info("=================================================================")
    logger.info("1. Climate & Environmental Dataset:")
    logger.info("   - File Path    : %s", climate_file)
    logger.info("   - Record Count : %d rows, %d columns", len(df_climate), len(df_climate.columns))
    logger.info("   - Date Range   : %s to %s", df_climate['date'].min(), df_climate['date'].max())
    logger.info("   - Location     : %s (Lat: %.4f, Lon: %.4f)", region, lat, lon)
    logger.info("   - Data Source  : NASA POWER AG Community API")
    logger.info("   - Columns      : %s", list(df_climate.columns))

    logger.info("\n2. Soil Dataset:")
    logger.info("   - File Path    : %s", soil_file)
    logger.info("   - Record Count : %d depth intervals", len(df_soil))
    logger.info("   - Depths       : %s", list(df_soil['depth_interval'].unique()))
    logger.info("   - Sampled Loc  : Lat %.4f, Lon %.4f", df_soil['sampled_latitude'].iloc[0], df_soil['sampled_longitude'].iloc[0])
    logger.info("   - Data Source  : ISRIC SoilGrids v2.0 (Official Files Service)")
    logger.info("   - Properties   : Soil pH, Clay (%), Sand (%), Silt (%), SOC (g/kg)")
    logger.info("   - Columns      : %s", list(df_soil.columns))

    logger.info("\n3. Combined Features Dataset:")
    logger.info("   - File Path    : %s", combined_file)
    logger.info("   - Record Count : %d aligned monthly records", len(df_combined))
    logger.info("   - Columns      : %d features", len(df_combined.columns))
    logger.info("   - Date Range   : %s to %s", df_combined['date'].min(), df_combined['date'].max())
    logger.info("   - Location     : %s", region)
    logger.info("   - Status       : Complete, validated, reproducible")

    logger.info("\n4. Engineered Master Feature Table:")
    logger.info("   - File Path    : %s", feature_file)
    logger.info("   - Record Count : %d monthly records", len(df_features))
    logger.info("   - Columns      : %d validated features", len(df_features.columns))
    logger.info("   - Date Range   : %s to %s", df_features['date'].min(), df_features['date'].max())
    logger.info("   - Location     : %s", region)
    logger.info("   - Status       : Complete, schema-validated, reproducible")
    logger.info("=================================================================\n")

    return {
        "climate": df_climate,
        "soil": df_soil,
        "combined": df_combined,
        "feature_table": df_features,
        "feature_table_path": feature_file
    }



def main():
    parser = argparse.ArgumentParser(description="Soil Sentinel Data Collection Automation")
    parser.add_argument("--force", action="store_true", help="Force re-download of raw datasets from API/VRT")
    parser.add_argument("--config", default="config/settings.yaml", help="Path to settings.yaml configuration")
    args = parser.parse_args()

    run_pipeline(force=args.force, config_path=args.config)


if __name__ == "__main__":
    main()

