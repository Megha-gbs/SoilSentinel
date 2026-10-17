"""
Soil Sentinel - Feature Engineering Module.

Constructs the standardized, validated `data/feature_table.csv` from processed
climate observations and soil baseline properties.

Key Principles:
1. Soil properties (pH, Clay, Sand, Silt, SOC) are static regional baselines from
   ISRIC SoilGrids v2.0, explicitly documented as static baseline measurements.
2. Climate variables (Temperature, Humidity, Precipitation) and dynamic soil
   indicators (Soil Moisture fractions, Soil Temperature) are monthly time series
   from NASA POWER.
3. Lag and rolling features (e.g., previous-month precipitation, rolling 3-month
   precipitation) are computed with strict temporal ordering. The initial months
   carry unobserved (NaN) values rather than fabricated historical estimates.
4. Air humidity (%) and soil moisture fractions (0-1) are preserved as distinct
   physical quantities with explicit column names.
5. No EC values or artificial labels are invented.
"""

import sys
import logging
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

import numpy as np
import pandas as pd
import yaml

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Preprocessing.clean_data import clean_climate_dataframe, clean_soil_dataframe
from src.Preprocessing.validate_data import validate_feature_table

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("feature_engineering")


def load_config(config_path: str = "config/settings.yaml") -> Dict[str, Any]:
    """Load settings from YAML file."""
    path = Path(config_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / config_path
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_feature_table(
    combined_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    config_path: str = "config/settings.yaml"
) -> pd.DataFrame:
    """
    Generate feature_table.csv from processed combined features.
    
    Returns:
        pd.DataFrame containing the engineered feature table.
    """
    config = load_config(config_path)

    if combined_path is None:
        p_comb = Path(config["pipeline"]["combined_output_path"])
        combined_path = p_comb if p_comb.is_absolute() else PROJECT_ROOT / p_comb
    else:
        p_comb = Path(combined_path)
        combined_path = p_comb if p_comb.is_absolute() else PROJECT_ROOT / p_comb

    if output_path is None:
        p_out = Path(config.get("pipeline", {}).get("feature_table_output_path", "data/feature_table.csv"))
        output_path = p_out if p_out.is_absolute() else PROJECT_ROOT / p_out
    else:
        p_out = Path(output_path)
        output_path = p_out if p_out.is_absolute() else PROJECT_ROOT / p_out


    if not combined_path.exists():
        raise FileNotFoundError(
            f"Input dataset not found at {combined_path}. "
            "Please run data collection and preprocessing first."
        )

    logger.info("Loading base combined dataset from %s", combined_path)
    df = pd.read_csv(combined_path)

    # 1. Enforce strict temporal ordering, continuity, and validity
    logger.info("Validating temporal ordering and chronological sequence...")
    if "date" not in df.columns:
        raise ValueError("Input dataset missing required 'date' column.")

    if df.empty:
        raise ValueError("Input dataset is empty (0 rows).")

    # Validate month range if month column is present
    if "month" in df.columns:
        invalid_months = df["month"][~df["month"].between(1, 12)].tolist()
        if invalid_months:
            raise ValueError(f"Invalid calendar month values detected: {invalid_months}. Months must be between 1 and 12.")

    # Check for duplicate dates
    if df["date"].duplicated().any():
        dups = df["date"][df["date"].duplicated()].unique().tolist()
        raise ValueError(f"Duplicate monthly records detected in input data: {dups}")

    # Parse dates
    try:
        df["date_dt"] = pd.to_datetime(df["date"], format="%Y-%m")
    except Exception as e:
        raise ValueError(f"Invalid date format in 'date' column: {e}") from e

    # Check chronological ordering (records must be strictly sorted)
    if not df["date_dt"].is_monotonic_increasing:
        raise ValueError("Input records are out of chronological order. Records must be strictly sorted by date.")

    # Check monthly continuity without gaps across calendar months and year boundaries
    expected_dates = pd.date_range(start=df["date_dt"].iloc[0], end=df["date_dt"].iloc[-1], freq="MS")
    if len(df) != len(expected_dates):
        missing_dates = expected_dates.difference(df["date_dt"])
        missing_str = [d.strftime("%Y-%m") for d in missing_dates]
        raise ValueError(f"Temporal gap detected in monthly time series. Missing {len(missing_str)} month(s): {missing_str}")

    df = df.reset_index(drop=True)


    # 2. Add Temporal and Seasonal Context Features
    logger.info("Generating temporal and seasonal context features...")
    df["year"] = df["date_dt"].dt.year.astype("int64")
    df["month"] = df["date_dt"].dt.month.astype("int64")
    df["quarter"] = df["date_dt"].dt.quarter.astype("int64")

    # Season mapping for the Indo-Gangetic Plains / Sub-tropical Agro-climatic zone:
    # Dec-Feb: Winter (Rabi)
    # Mar-May: Pre-Monsoon / Summer (Zaid)
    # Jun-Sep: Monsoon (Kharif)
    # Oct-Nov: Post-Monsoon (Autumn transition)
    def map_season(month: int) -> str:
        if month in [12, 1, 2]:
            return "Winter"
        elif month in [3, 4, 5]:
            return "Summer_PreMonsoon"
        elif month in [6, 7, 8, 9]:
            return "Monsoon"
        else:
            return "PostMonsoon_Autumn"

    df["season"] = df["month"].apply(map_season)

    # Cyclic month encoding for cyclical ML representations
    df["month_sin"] = np.round(np.sin(2 * np.pi * df["month"] / 12), 4)
    df["month_cos"] = np.round(np.cos(2 * np.pi * df["month"] / 12), 4)

    # 3. Add Dynamic Climate & Hydrological Lag / Rolling Features
    logger.info("Computing scientifically interpretable lag and rolling precipitation features...")
    # Previous-month precipitation: shift by 1 month. Month 1 (2020-01) is correctly NaN (not fabricated).
    df["precipitation_lag1_mm_day"] = df["precipitation_mm_day"].shift(1)

    # Rolling 3-month precipitation average (window=3, min_periods=3):
    # Months 1 and 2 are correctly NaN (no fabricated historical data).
    df["precipitation_rolling_3m_mean_mm_day"] = np.round(
        df["precipitation_mm_day"].rolling(window=3, min_periods=3).mean(), 2
    )

    # Rolling 3-month precipitation sum (cumulative rainfall rate across quarter)
    df["precipitation_rolling_3m_sum_mm_day"] = np.round(
        df["precipitation_mm_day"].rolling(window=3, min_periods=3).sum(), 2
    )

    # Previous-month air temperature
    df["air_temperature_lag1_c"] = df["air_temperature_c"].shift(1)

    # 4. Thermal & Hydrological Coupling Indicators
    logger.info("Generating soil-climate interaction indicators...")
    # Temperature difference between topsoil (0-10cm) and ambient 2m air
    # Positive: soil surface warmer than air (high insolation/low canopy); Negative: soil cooler than air
    df["temp_soil_air_diff_c"] = np.round(
        df["soil_temperature_layer1_c"] - df["air_temperature_c"], 2
    )

    # Soil moisture vertical gradient: Root-zone wetness vs. surface wetness
    # Positive: drying surface with buffered moisture below; Negative: surface ponding / rapid infiltration
    df["soil_moisture_depth_gradient"] = np.round(
        df["soil_moisture_rootzone_fraction"] - df["soil_moisture_surface_fraction"], 4
    )

    # Monthly De Martonne Aridity Index proxy: P / (T + 10)
    # Reflects moisture availability relative to thermal evaporative potential
    df["monthly_aridity_index"] = np.round(
        (df["precipitation_mm_day"] * 30.0) / (df["air_temperature_c"] + 10.0), 2
    )

    # 5. Soil Physical Texture & Structure Ratios (Static Baseline)
    logger.info("Computing soil texture ratios...")
    # Cohesiveness / retention ratio: Clay % / Sand %
    df["clay_to_sand_ratio"] = np.round(
        df["topsoil_clay_percent"] / df["topsoil_sand_percent"], 3
    )

    # Structural stability index (Dexter et al.): SOC (g/kg) / Clay (g/kg)
    # Clay is in %, so clay in g/kg = clay_percent * 10
    df["soc_to_clay_ratio"] = np.round(
        df["topsoil_soc_g_kg"] / (df["topsoil_clay_percent"] * 10.0), 4
    )

    # 6. Explicit Spatial-Temporal Baseline Metadata
    # Document that soil properties repeated across months represent static regional baseline
    # measurements from ISRIC SoilGrids v2.0, NOT 60 independent geographic soil samples.
    df["soil_measurement_type"] = "static_regional_baseline"
    df["climate_measurement_type"] = "monthly_time_series"

    # Drop temporary datetime sorting column
    df = df.drop(columns=["date_dt"])

    # 7. Validate Final Feature Table
    is_valid, validation_msg = validate_feature_table(df)
    if not is_valid:
        raise ValueError(f"Feature table validation failed: {validation_msg}")
    logger.info("Feature table validation passed: %s", validation_msg)

    # Save to data/feature_table.csv
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.info("Successfully generated feature table: %s (shape: %s)", output_path, df.shape)

    return df





if __name__ == "__main__":
    df_features = build_feature_table()
    print("\nFeature Table Preview:")
    print(df_features.head())
    print(f"\nFinal Shape: {df_features.shape}")
    print(f"Columns ({len(df_features.columns)} total): {list(df_features.columns)}")
