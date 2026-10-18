"""
SoilSentinel — Satellite Data Alignment Pipeline.

Merges verified spaceborne satellite indicators (Copernicus Sentinel-2 Level-2A genuine
spectral NDVI and SCL metrics) with the authoritative SoilSentinel feature table (sireesha/feature_table.csv).

Key Principles:
1. Strict 1-to-1 temporal matching on exact chronological dates ('2020-01' to '2024-12').
2. Geographic alignment verified on nominal (30.73, 76.77) and sampled (30.7392, 76.7764) coordinates.
3. Preserves all 53 original feature columns untouched without dropping or renaming.
4. Preserves boundary NaNs in lag/rolling features (row 0 lag1, rows 0-1 rolling3m).
5. Explicit 'satellite_' namespace for all merged satellite indicators.
6. Preserves missing/cloudy satellite months as NaN without synthetic zero-filling.

Output:
  data/processed/satellite/aligned_feature_table_with_satellite.csv
"""

import sys
import logging
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("align_satellite")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FEATURE_TABLE_PATH = (
    PROJECT_ROOT / "data" / "feature_table.csv"
    if (PROJECT_ROOT / "data" / "feature_table.csv").exists()
    else PROJECT_ROOT / "sireesha" / "feature_table.csv"
)
SATELLITE_CSV_PATH = PROJECT_ROOT / "data" / "processed" / "satellite" / "satellite_ndvi_monthly_2020_2024.csv"
OUTPUT_ALIGNED_PATH = PROJECT_ROOT / "data" / "processed" / "satellite" / "aligned_feature_table_with_satellite.csv"


def align_datasets(
    feature_table_path: Optional[Path] = None,
    satellite_path: Optional[Path] = None,
    output_path: Optional[Path] = None
) -> pd.DataFrame:
    """Execute strict alignment between existing feature table and satellite indicators."""
    feat_file = feature_table_path or FEATURE_TABLE_PATH
    sat_file = satellite_path or SATELLITE_CSV_PATH
    out_file = output_path or OUTPUT_ALIGNED_PATH

    if not feat_file.exists():
        raise FileNotFoundError(f"Feature table not found at {feat_file}")
    if not sat_file.exists():
        raise FileNotFoundError(f"Satellite dataset not found at {sat_file}")

    logger.info("Loading baseline feature table from %s", feat_file)
    df_feat = pd.read_csv(feat_file)
    logger.info("Loading processed satellite dataset from %s", sat_file)
    df_sat = pd.read_csv(sat_file)

    # 1. Dimensionality and length verification
    if len(df_feat) != 60:
        raise ValueError(f"Feature table expected 60 rows, got {len(df_feat)}")
    if len(df_sat) != 60:
        raise ValueError(f"Satellite table expected 60 rows, got {len(df_sat)}")

    # 2. Chronological sequence check
    if not (df_feat["date"] == df_sat["date"]).all():
        mismatched = df_feat[df_feat["date"] != df_sat["date"]][["date"]]
        raise ValueError(f"Date alignment mismatch detected: {mismatched.to_dict()}")

    # 3. Geographic compatibility check
    assert abs(df_feat["nominal_latitude"].iloc[0] - df_sat["nominal_latitude"].iloc[0]) < 1e-4, "Nominal latitude mismatch"
    assert abs(df_feat["nominal_longitude"].iloc[0] - df_sat["nominal_longitude"].iloc[0]) < 1e-4, "Nominal longitude mismatch"
    assert abs(df_feat["sampled_latitude"].iloc[0] - df_sat["sampled_latitude"].iloc[0]) < 1e-4, "Sampled latitude mismatch"
    assert abs(df_feat["sampled_longitude"].iloc[0] - df_sat["sampled_longitude"].iloc[0]) < 1e-4, "Sampled longitude mismatch"

    # 4. Select satellite columns to merge
    sat_cols_to_merge = [
        "date",
        "satellite_ndvi",
        "satellite_ndvi_median",
        "satellite_ndvi_std",
        "satellite_valid_pixel_fraction",
        "satellite_cloud_shadow_pixel_fraction",
        "satellite_scl_vegetation_fraction",
        "satellite_scl_bare_soil_fraction",
        "satellite_quality_flag",
        "satellite_scene_id",
        "satellite_observation_date",
        "satellite_platform",
        "satellite_processing_method",
        "satellite_data_source"
    ]

    df_sat_subset = df_sat[sat_cols_to_merge]

    # 5. Execute merge
    df_aligned = pd.merge(df_feat, df_sat_subset, on="date", how="inner")

    # 6. Verify row count and column integrity
    assert len(df_aligned) == 60, f"Aligned row count {len(df_aligned)} != 60"
    expected_cols = len(df_feat.columns) + len(sat_cols_to_merge) - 1  # -1 for 'date'
    assert len(df_aligned.columns) == expected_cols, f"Aligned columns {len(df_aligned.columns)} != {expected_cols}"

    # 7. Verify preservation of boundary NaNs in lag features
    assert pd.isna(df_aligned.loc[0, "precipitation_lag1_mm_day"]), "Row 0 precip lag1 must remain NaN"
    assert pd.isna(df_aligned.loc[0, "precipitation_rolling_3m_mean_mm_day"]), "Row 0 rolling3m must remain NaN"
    assert pd.isna(df_aligned.loc[1, "precipitation_rolling_3m_mean_mm_day"]), "Row 1 rolling3m must remain NaN"

    # 8. Verify missing satellite months remain NaN (no silent zero-filling)
    unusable_months = df_sat.loc[df_sat["satellite_quality_flag"] == "QUALITY_UNUSABLE_CLOUDY", "date"].tolist()
    for m in unusable_months:
        idx = df_aligned.index[df_aligned["date"] == m].tolist()[0]
        assert pd.isna(df_aligned.loc[idx, "satellite_ndvi"]), f"Unusable month {m} must remain NaN"

    # 9. Save aligned dataset
    out_file.parent.mkdir(parents=True, exist_ok=True)
    df_aligned.to_csv(out_file, index=False)
    logger.info("Successfully wrote aligned feature table to: %s (shape: %s)", out_file, df_aligned.shape)

    return df_aligned


if __name__ == "__main__":
    df = align_datasets()
    print("\nAligned Dataset Summary:")
    print(f"- Rows: {len(df)}")
    print(f"- Columns ({len(df.columns)} total): {list(df.columns)}")
    print("\nPreview of Aligned Satellite Features:")
    print(df[["date", "air_temperature_c", "precipitation_mm_day", "soil_moisture_rootzone_fraction", "satellite_ndvi", "satellite_valid_pixel_fraction", "satellite_quality_flag"]].head(10))
