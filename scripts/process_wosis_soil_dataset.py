"""
SoilSentinel - Processing of ISRIC WoSIS Measured Soil Observations.

Processes raw WoSIS GeoJSON layers downloaded into data/raw/wosis/:
- wosis_profiles_punjab_bbox.geojson (Profile locations, survey year, taxonomy)
- wosis_orgc_punjab_bbox.geojson (Measured soil organic carbon, g/kg)
- wosis_phaq_punjab_bbox.geojson (Measured soil pH in H2O)
- wosis_clay_punjab_bbox.geojson (Measured clay fraction, %)
- wosis_sand_punjab_bbox.geojson (Measured sand fraction, %)
- wosis_silt_punjab_bbox.geojson (Measured silt fraction, %)

Aggregates depth-interval measurements into standardized topsoil plow-zone (0-30cm)
physical soil property profiles. Computes agronomic ratings (SOC rating, pH rating, texture class).

Output:
data/processed/wosis_measured_soil_properties.csv
"""

import json
import logging
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_WOSIS_DIR = PROJECT_ROOT / "data" / "raw" / "wosis"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
LOGS_DIR = PROJECT_ROOT / "data" / "logs"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging
log_file = LOGS_DIR / "wosis_processing.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("wosis_processing")


def parse_wosis_value(val_str: Any) -> Optional[float]:
    """Parse WoSIS value string like '{4.0}' or float to float."""
    if val_str is None or pd.isna(val_str):
        return None
    if isinstance(val_str, (int, float)):
        return float(val_str)
    s = str(val_str).strip()
    match = re.search(r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?", s)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            return None
    return None


def determine_texture_class(sand: float, clay: float, silt: float) -> str:
    """Classify USDA soil texture from sand, clay, silt percentages."""
    if not (np.isfinite(sand) and np.isfinite(clay) and np.isfinite(silt)):
        return "Unclassified"
    if sand >= 85 and silt + 1.5 * clay < 15:
        return "Sand"
    elif sand >= 70 and silt + 1.5 * clay >= 15 and silt + 2 * clay < 30:
        return "Loamy Sand"
    elif (clay >= 7 and clay < 20 and sand > 52 and silt + 2 * clay >= 30) or (clay < 7 and silt < 50 and silt + 2 * clay >= 30):
        return "Sandy Loam"
    elif clay >= 7 and clay < 27 and silt >= 28 and silt < 50 and sand <= 52:
        return "Loam"
    elif (silt >= 50 and clay >= 12 and clay < 27) or (silt >= 50 and silt < 80 and clay < 12):
        return "Silt Loam"
    elif silt >= 80 and clay < 12:
        return "Silt"
    elif clay >= 20 and clay < 35 and silt < 28 and sand > 45:
        return "Sandy Clay Loam"
    elif clay >= 27 and clay < 40 and sand > 20 and sand <= 45:
        return "Clay Loam"
    elif clay >= 27 and clay < 40 and sand <= 20:
        return "Silty Clay Loam"
    elif clay >= 35 and sand > 45:
        return "Sandy Clay"
    elif clay >= 40 and silt >= 40:
        return "Silty Clay"
    elif clay >= 40 and sand <= 45 and silt < 40:
        return "Clay"
    return "Loam"


def process_wosis_profiles() -> pd.DataFrame:
    logger.info("=== Starting WoSIS Raw Layer Processing ===")

    # 1. Load profiles
    prof_file = RAW_WOSIS_DIR / "wosis_profiles_punjab_bbox.geojson"
    if not prof_file.exists():
        raise FileNotFoundError(f"Missing {prof_file}")

    with open(prof_file, "r", encoding="utf-8") as f:
        profiles_raw = json.load(f)["features"]

    profiles_data = []
    for f in profiles_raw:
        props = f.get("properties", {})
        profiles_data.append({
            "profile_id": props.get("profile_id"),
            "profile_code": props.get("profile_code"),
            "dataset_code": props.get("dataset_code"),
            "country_name": props.get("country_name"),
            "sampling_year": props.get("year"),
            "latitude": props.get("latitude"),
            "longitude": props.get("longitude"),
            "positional_uncertainty": props.get("positional_uncertainty"),
            "soil_group": props.get("wrb_reference_soil_group_name") or props.get("wrb_reference_soil_group_code"),
        })

    df_profiles = pd.DataFrame(profiles_data).drop_duplicates(subset=["profile_id"]).reset_index(drop=True)
    logger.info(f"Loaded {len(df_profiles)} unique profile sites in NW India / Punjab BBOX.")

    # 2. Helper to load and aggregate a property for topsoil (upper_depth <= 30cm)
    def load_topsoil_property(filename: str, val_col_name: str, depth_max: int = 30) -> pd.DataFrame:
        filepath = RAW_WOSIS_DIR / filename
        if not filepath.exists():
            logger.warning(f"File {filename} not found.")
            return pd.DataFrame(columns=["profile_id", val_col_name])

        with open(filepath, "r", encoding="utf-8") as f:
            features = json.load(f)["features"]

        records = []
        for feat in features:
            props = feat.get("properties", {})
            p_id = props.get("profile_id")
            u_depth = props.get("upper_depth", 0)
            l_depth = props.get("lower_depth", 30)
            val = parse_wosis_value(props.get("value"))

            if val is not None and u_depth is not None and u_depth <= depth_max:
                records.append({
                    "profile_id": p_id,
                    "upper_depth": u_depth,
                    "lower_depth": l_depth,
                    "value": val,
                })

        if not records:
            return pd.DataFrame(columns=["profile_id", val_col_name])

        df_prop = pd.DataFrame(records)
        # Weight by layer thickness if available, or average topsoil
        df_prop["thickness"] = (df_prop["lower_depth"] - df_prop["upper_depth"]).clip(lower=1)
        grouped = df_prop.groupby("profile_id").apply(
            lambda g: np.average(g["value"], weights=g["thickness"]) if len(g) > 1 else g["value"].iloc[0],
            include_groups=False,
        ).reset_index(name=val_col_name)

        return grouped

    # Load properties
    df_orgc = load_topsoil_property("wosis_orgc_punjab_bbox.geojson", "soc_measured_g_kg")
    df_phaq = load_topsoil_property("wosis_phaq_punjab_bbox.geojson", "ph_measured_h2o")
    df_clay = load_topsoil_property("wosis_clay_punjab_bbox.geojson", "clay_measured_pct")
    df_sand = load_topsoil_property("wosis_sand_punjab_bbox.geojson", "sand_measured_pct")
    df_silt = load_topsoil_property("wosis_silt_punjab_bbox.geojson", "silt_measured_pct")

    # In WoSIS, orgc is often in g/kg or dg/kg. In our inspection, values were 0.5 to 10 g/kg.
    # Convert soc to %: 10 g/kg = 1.0 %
    df_orgc["soc_measured_pct"] = np.round(df_orgc["soc_measured_g_kg"] / 10.0, 3)

    # Clay, Sand, Silt: in WoSIS clay is g/kg (mass fraction). 200 g/kg = 20%.
    # Check max values: if max > 100, divide by 10 to get percentage.
    for col, df_t in [("clay_measured_pct", df_clay), ("sand_measured_pct", df_sand), ("silt_measured_pct", df_silt)]:
        if not df_t.empty and df_t[col].max() > 100:
            df_t[col] = np.round(df_t[col] / 10.0, 1)

    # 3. Merge all properties onto profiles
    merged = df_profiles.merge(df_orgc, on="profile_id", how="left")
    merged = merged.merge(df_phaq, on="profile_id", how="left")
    merged = merged.merge(df_clay, on="profile_id", how="left")
    merged = merged.merge(df_sand, on="profile_id", how="left")
    merged = merged.merge(df_silt, on="profile_id", how="left")

    # Round properties
    for col in ["soc_measured_g_kg", "soc_measured_pct", "ph_measured_h2o", "clay_measured_pct", "sand_measured_pct", "silt_measured_pct"]:
        if col in merged.columns:
            merged[col] = merged[col].round(2)

    # 4. Compute Agronomic Categorical Labels
    def rate_soc(pct):
        if pd.isna(pct):
            return None
        if pct < 0.50:
            return "Low (<0.50%)"
        elif pct <= 0.75:
            return "Medium (0.50-0.75%)"
        else:
            return "High (>0.75%)"

    def rate_ph(ph):
        if pd.isna(ph):
            return None
        if ph < 6.5:
            return "Acidic (<6.5)"
        elif ph <= 7.5:
            return "Neutral (6.5-7.5)"
        elif ph <= 8.5:
            return "Alkaline (7.5-8.5)"
        else:
            return "Strongly Alkaline / Sodic (>8.5)"

    merged["soc_rating"] = merged["soc_measured_pct"].apply(rate_soc)
    merged["ph_rating"] = merged["ph_measured_h2o"].apply(rate_ph)

    # Texture class
    texture_classes = [
        determine_texture_class(row["sand_measured_pct"], row["clay_measured_pct"], row["silt_measured_pct"])
        for _, row in merged.iterrows()
    ]
    merged["texture_class"] = texture_classes

    # Filter to profiles that have at least one measured physical property
    has_measurements = (
        merged["soc_measured_g_kg"].notna()
        | merged["ph_measured_h2o"].notna()
        | merged["clay_measured_pct"].notna()
    )
    df_valid = merged[has_measurements].copy().reset_index(drop=True)

    out_csv = PROCESSED_DIR / "wosis_measured_soil_properties.csv"
    df_valid.to_csv(out_csv, index=False)
    logger.info(
        f"Saved processed WoSIS dataset: {out_csv.name} ({len(df_valid)} profiles with measured laboratory data, {out_csv.stat().st_size} bytes)"
    )

    return df_valid


if __name__ == "__main__":
    df_res = process_wosis_profiles()
    print("\nProcessed WoSIS Dataset Preview:")
    print(df_res.head())
    print("\nSummary of Columns and Non-Null Counts:")
    print(df_res.info())
