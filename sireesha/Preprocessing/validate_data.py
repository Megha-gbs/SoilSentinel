"""
Data Validation Module.

Validates climate, soil, combined datasets, and engineered feature tables for
schema conformity, physical value bounds, missing values, and data integrity.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Tuple
import pandas as pd

logger = logging.getLogger("validate_data")


def validate_climate_data(df: pd.DataFrame) -> Tuple[bool, str]:
    """Validate climate and soil environmental dataset structure and physical bounds."""
    expected_cols = [
        "region", "latitude", "longitude", "year", "month", "date",
        "air_temperature_c", "air_humidity_percent", "precipitation_mm_day",
        "soil_temperature_layer1_c", "soil_moisture_surface_fraction",
        "soil_moisture_rootzone_fraction", "data_source"
    ]
    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        return False, f"Missing columns in climate data: {missing}"

    if df.empty:
        return False, "Climate dataset has 0 rows."

    # Verify no nulls in required spatial-temporal metadata
    metadata_cols = ["region", "latitude", "longitude", "year", "month", "date"]
    if df[metadata_cols].isnull().any().any():
        return False, "Null values detected in climate metadata columns."

    # Physical bounds check on non-null values
    temp_col = "air_temperature_c" if "air_temperature_c" in df.columns else "temperature_c"
    valid_temp = df[temp_col].dropna()
    if not valid_temp.between(-50.0, 60.0).all():
        return False, "Air temperature values found outside realistic physical bounds [-50, 60] C."

    humid_col = "air_humidity_percent" if "air_humidity_percent" in df.columns else "humidity_percent"
    valid_humid = df[humid_col].dropna()
    if not valid_humid.between(0.0, 100.0).all():
        return False, "Air relative humidity values found outside [0, 100] %."

    valid_precip = df["precipitation_mm_day"].dropna()
    if (valid_precip < 0.0).any():
        return False, "Negative precipitation values detected."

    # Validate soil environmental parameters
    valid_soil_temp = df["soil_temperature_layer1_c"].dropna()
    if not valid_soil_temp.between(-50.0, 60.0).all():
        return False, "Soil temperature layer 1 values found outside [-50, 60] C."

    valid_gwettop = df["soil_moisture_surface_fraction"].dropna()
    if not valid_gwettop.between(0.0, 1.0).all():
        return False, "Surface soil wetness fraction found outside [0, 1]."

    valid_gwetroot = df["soil_moisture_rootzone_fraction"].dropna()
    if not valid_gwetroot.between(0.0, 1.0).all():
        return False, "Root zone soil wetness fraction found outside [0, 1]."

    return True, f"Environmental climate data valid: {len(df)} records from {df['date'].min()} to {df['date'].max()}."


def validate_soil_data(df: pd.DataFrame) -> Tuple[bool, str]:
    """Validate soil dataset structure, texture fractions, and physical bounds."""
    expected_cols = [
        "region", "nominal_latitude", "nominal_longitude",
        "sampled_latitude", "sampled_longitude", "depth_interval",
        "soil_ph", "clay_percent", "sand_percent", "silt_percent",
        "soc_g_kg", "data_source"
    ]
    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        return False, f"Missing columns in soil data: {missing}"

    if df.empty:
        return False, "Soil dataset has 0 rows."

    if df.isnull().any().any():
        null_counts = df.isnull().sum().to_dict()
        return False, f"Null values detected in soil data: {null_counts}"

    # Physical bounds check
    if not df["soil_ph"].between(3.0, 11.0).all():
        return False, "Soil pH outside realistic range [3.0, 11.0]."

    for col in ["clay_percent", "sand_percent", "silt_percent"]:
        if not df[col].between(0.0, 100.0).all():
            return False, f"{col} outside [0, 100] %."

    if (df["soc_g_kg"] < 0.0).any():
        return False, "Negative Soil Organic Carbon (soc_g_kg) detected."

    return True, f"Soil data valid: {len(df)} depth intervals."


def validate_combined_features(df: pd.DataFrame) -> Tuple[bool, str]:
    """Validate combined climate and soil features."""
    required_cols = [
        "region", "date", "year", "month",
        "air_temperature_c", "air_humidity_percent", "precipitation_mm_day",
        "soil_temperature_layer1_c", "soil_moisture_surface_fraction", "soil_moisture_rootzone_fraction",
        "topsoil_ph_mean", "topsoil_clay_percent", "topsoil_sand_percent",
        "topsoil_silt_percent", "topsoil_soc_g_kg",
        "climate_source", "soil_source"
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        return False, f"Missing columns in combined features: {missing}"

    if df.empty:
        return False, "Combined features dataset has 0 rows."

    return True, f"Combined features valid: {len(df)} records aligned by location and time."


def validate_feature_table(df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Validate feature_table.csv schema, types, physical ranges, and expected missing-value distribution.
    """
    required_cols = [
        "region", "nominal_latitude", "nominal_longitude",
        "sampled_latitude", "sampled_longitude",
        "year", "month", "date", "quarter", "season", "month_sin", "month_cos",
        # Atmospheric Climate
        "air_temperature_c", "air_humidity_percent", "precipitation_mm_day",
        # Soil Environmental
        "soil_temperature_layer1_c",
        "soil_moisture_surface_fraction", "soil_moisture_rootzone_fraction",
        # Lag / Rolling Features
        "precipitation_lag1_mm_day", "precipitation_rolling_3m_mean_mm_day",
        "precipitation_rolling_3m_sum_mm_day", "air_temperature_lag1_c",
        # Interaction Indicators
        "temp_soil_air_diff_c", "soil_moisture_depth_gradient", "monthly_aridity_index",
        # Soil Baseline (0-30cm Depth-Weighted Mean)
        "topsoil_ph_mean", "topsoil_clay_percent", "topsoil_sand_percent",
        "topsoil_silt_percent", "topsoil_soc_g_kg",
        "clay_to_sand_ratio", "soc_to_clay_ratio",
        # Layer-Specific Depths
        "ph_0_5cm", "ph_5_15cm", "ph_15_30cm",
        "clay_0_5cm_percent", "clay_5_15cm_percent", "clay_15_30cm_percent",
        "sand_0_5cm_percent", "sand_5_15cm_percent", "sand_15_30cm_percent",
        "silt_0_5cm_percent", "silt_5_15cm_percent", "silt_15_30cm_percent",
        "soc_0_5cm_g_kg", "soc_5_15cm_g_kg", "soc_15_30cm_g_kg",
        # Metadata
        "soil_measurement_type", "climate_measurement_type",
        "climate_source", "soil_source"
    ]

    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        return False, f"Missing required columns in feature table: {missing_cols}"

    if df.empty:
        return False, "Feature table is empty (0 rows)."

    # Missing values validation:
    # ONLY lag and rolling features should have missing values due to boundary starts.
    # - 1-month lag features: exactly 1 NaN at index 0.
    # - 3-month rolling features: exactly 2 NaNs at indices 0, 1.
    expected_lag1_nans = 1 if len(df) >= 1 else 0
    expected_roll3_nans = 2 if len(df) >= 2 else len(df)

    actual_lag1_p = df["precipitation_lag1_mm_day"].isnull().sum()
    actual_lag1_t = df["air_temperature_lag1_c"].isnull().sum()
    actual_roll3_mean = df["precipitation_rolling_3m_mean_mm_day"].isnull().sum()
    actual_roll3_sum = df["precipitation_rolling_3m_sum_mm_day"].isnull().sum()

    if actual_lag1_p != expected_lag1_nans or actual_lag1_t != expected_lag1_nans:
        return False, f"Unexpected NaN count in 1-month lag features: precip={actual_lag1_p}, temp={actual_lag1_t}"

    if actual_roll3_mean != expected_roll3_nans or actual_roll3_sum != expected_roll3_nans:
        return False, f"Unexpected NaN count in 3-month rolling features: mean={actual_roll3_mean}, sum={actual_roll3_sum}"

    # Verify that NO OTHER column contains NaNs
    non_lag_cols = [c for c in df.columns if c not in [
        "precipitation_lag1_mm_day", "air_temperature_lag1_c",
        "precipitation_rolling_3m_mean_mm_day", "precipitation_rolling_3m_sum_mm_day"
    ]]
    other_nans = df[non_lag_cols].isnull().sum()
    unexpected_nans = other_nans[other_nans > 0].to_dict()
    if unexpected_nans:
        return False, f"Unexpected NaN values in non-lag columns: {unexpected_nans}"

    # Physical bounds checks
    if not df["air_temperature_c"].between(-50.0, 60.0).all():
        return False, "Air temperature out of physical bounds [-50, 60] C."
    if not df["air_humidity_percent"].between(0.0, 100.0).all():
        return False, "Air relative humidity out of physical bounds [0, 100] %."
    if (df["precipitation_mm_day"] < 0.0).any():
        return False, "Negative precipitation detected."

    if not df["soil_temperature_layer1_c"].between(-50.0, 60.0).all():
        return False, "Soil temperature layer 1 out of bounds [-50, 60] C."
    if not df["soil_moisture_surface_fraction"].between(0.0, 1.0).all():
        return False, "Surface soil wetness out of fraction range [0, 1]."
    if not df["soil_moisture_rootzone_fraction"].between(0.0, 1.0).all():
        return False, "Root-zone soil wetness out of fraction range [0, 1]."

    if not df["topsoil_ph_mean"].between(3.0, 11.0).all():
        return False, "Topsoil pH out of realistic range [3.0, 11.0]."
    if not df["topsoil_clay_percent"].between(0.0, 100.0).all():
        return False, "Topsoil clay % out of range [0, 100]."
    if not df["topsoil_sand_percent"].between(0.0, 100.0).all():
        return False, "Topsoil sand % out of range [0, 100]."
    if not df["topsoil_silt_percent"].between(0.0, 100.0).all():
        return False, "Topsoil silt % out of range [0, 100]."

    return True, f"All {len(df)} records conform to schema, physical bounds, and missing-value constraints."
