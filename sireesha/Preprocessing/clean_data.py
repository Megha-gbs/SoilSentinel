"""
Data Cleaning Module.

Standardizes types, formats, precision, and strips unnecessary whitespace.
"""

import pandas as pd


def clean_climate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean climate dataset: ensure numeric types, standardized date strings, drop duplicates."""
    df_clean = df.copy()
    df_clean.drop_duplicates(subset=["region", "year", "month"], inplace=True)

    df_clean["year"] = df_clean["year"].astype(int)
    df_clean["month"] = df_clean["month"].astype(int)
    df_clean["date"] = df_clean["year"].astype(str) + "-" + df_clean["month"].astype(str).str.zfill(2)

    # Core air climate features
    if "air_temperature_c" in df_clean.columns:
        df_clean["air_temperature_c"] = df_clean["air_temperature_c"].astype(float).round(2)
    if "temperature_c" in df_clean.columns:
        df_clean["temperature_c"] = df_clean["temperature_c"].astype(float).round(2)

    if "air_humidity_percent" in df_clean.columns:
        df_clean["air_humidity_percent"] = df_clean["air_humidity_percent"].astype(float).round(2)
    if "humidity_percent" in df_clean.columns:
        df_clean["humidity_percent"] = df_clean["humidity_percent"].astype(float).round(2)

    if "precipitation_mm_day" in df_clean.columns:
        df_clean["precipitation_mm_day"] = df_clean["precipitation_mm_day"].astype(float).round(2)

    # Soil environmental indicators
    if "soil_temperature_layer1_c" in df_clean.columns:
        df_clean["soil_temperature_layer1_c"] = df_clean["soil_temperature_layer1_c"].astype(float).round(2)
    if "soil_moisture_surface_fraction" in df_clean.columns:
        df_clean["soil_moisture_surface_fraction"] = df_clean["soil_moisture_surface_fraction"].astype(float).round(4)
    if "soil_moisture_rootzone_fraction" in df_clean.columns:
        df_clean["soil_moisture_rootzone_fraction"] = df_clean["soil_moisture_rootzone_fraction"].astype(float).round(4)

    df_clean.sort_values(by=["year", "month"], inplace=True)
    df_clean.reset_index(drop=True, inplace=True)
    return df_clean


def clean_soil_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean soil dataset: round precision, drop duplicates, ensure standard intervals."""
    df_clean = df.copy()
    df_clean.drop_duplicates(subset=["region", "depth_interval"], inplace=True)

    for col in ["soil_ph", "clay_percent", "sand_percent", "silt_percent", "soc_g_kg"]:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].astype(float).round(2)

    df_clean.reset_index(drop=True, inplace=True)
    return df_clean
