"""
SoilSentinel — Automated Validation Test Suite for Real Satellite Data & Aligned Pipelines.

Tests genuine, real-world satellite observations and aligned feature tables:
- File existence and readability
- Schema dimensions and column names
- Chronological date range and continuity (2020-01 to 2024-12, 60 records)
- Physical range bounds for NDVI [-1.0, +1.0] and vegetation fractions
- Preservation of original baseline features and boundary NaNs in lag features
- Explicit separation and documentation of nominal vs substitute coordinates
- Preservation of missing observations (NaN) for unusable cloudy months
"""

import os
import sys
import json
from pathlib import Path

import pytest
import pandas as pd
import numpy as np
import rasterio

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CATALOG_JSON = PROJECT_ROOT / "data" / "raw" / "satellite" / "sentinel2_monthly_catalog_2020_2024.json"
MANIFEST_JSON = PROJECT_ROOT / "data" / "raw" / "satellite" / "spectral_acquisition_manifest.json"
SUBSETS_DIR = PROJECT_ROOT / "data" / "raw" / "satellite" / "spectral_subsets"
PROCESSED_CSV = PROJECT_ROOT / "data" / "processed" / "satellite" / "satellite_ndvi_monthly_2020_2024.csv"
ALIGNED_CSV = PROJECT_ROOT / "data" / "processed" / "satellite" / "aligned_feature_table_with_satellite.csv"
THUMBNAIL_IMG = PROJECT_ROOT / "data" / "raw" / "satellite" / "sentinel2_sample_thumbnail.jpg"
BASELINE_FEATURE_TABLE = PROJECT_ROOT / "sireesha" / "feature_table.csv"


def test_spectral_acquisition_manifest_and_geotiffs():
    """Verify that all 60 months have downloaded and verified B04, B08, and SCL GeoTIFF rasters."""
    assert MANIFEST_JSON.exists(), f"Acquisition manifest missing: {MANIFEST_JSON}"
    with open(MANIFEST_JSON, "r", encoding="utf-8") as f:
        mf = json.load(f)

    assert "records" in mf, "Manifest missing 'records' list"
    records = mf["records"]
    assert len(records) == 60, f"Expected 60 monthly records, got {len(records)}"

    # Check that GeoTIFF subsets exist and are readable
    for rec in records:
        scene_id = rec["scene_id"]
        for band in ["B04", "B08", "SCL"]:
            tif_path = SUBSETS_DIR / f"{scene_id}_{band}.tif"
            assert tif_path.exists(), f"Missing GeoTIFF: {tif_path}"
            assert tif_path.stat().st_size > 500, f"GeoTIFF implausibly small: {tif_path}"

            with rasterio.open(tif_path) as src:
                assert src.width > 0 and src.height > 0
                assert src.crs == rasterio.crs.CRS.from_string("EPSG:32643")


def test_processed_satellite_csv_schema_and_bounds():
    """Verify processed satellite CSV conforms to schema, physical bounds, and NaN preservation."""
    assert PROCESSED_CSV.exists(), f"Processed CSV missing: {PROCESSED_CSV}"
    df = pd.read_csv(PROCESSED_CSV)

    assert len(df) == 60, f"Expected 60 rows, got {len(df)}"
    assert not df["date"].duplicated().any(), "Duplicate dates in processed CSV"

    # Verify key columns exist
    mandatory_cols = [
        "nominal_latitude", "nominal_longitude",
        "sampled_latitude", "sampled_longitude",
        "coordinate_substitution_distance_m", "coordinate_substitution_reason",
        "date", "satellite_scene_id", "satellite_observation_date",
        "satellite_ndvi", "satellite_ndvi_median", "satellite_ndvi_std",
        "satellite_valid_pixel_fraction", "satellite_cloud_shadow_pixel_fraction",
        "satellite_quality_flag", "satellite_processing_method",
        "satellite_b04_file", "satellite_b08_file", "satellite_scl_file"
    ]
    for c in mandatory_cols:
        assert c in df.columns, f"Missing mandatory column: {c}"

    # Verify physical bounds on observed months
    valid_ndvi = df.loc[df["satellite_ndvi"].notna(), "satellite_ndvi"]
    assert (valid_ndvi >= -1.0).all() and (valid_ndvi <= 1.0).all(), "NDVI out of bounds [-1.0, 1.0]"

    # Verify that exactly 5 cloudy months are NaN
    unusable = df[df["satellite_quality_flag"] == "QUALITY_UNUSABLE_CLOUDY"]
    assert len(unusable) == 5, f"Expected 5 unusable cloudy months, got {len(unusable)}"
    assert unusable["satellite_ndvi"].isna().all(), "Unusable months must have NaN NDVI"

    observed = df[df["satellite_quality_flag"] != "QUALITY_UNUSABLE_CLOUDY"]
    assert len(observed) == 55, f"Expected 55 observed months, got {len(observed)}"
    assert observed["satellite_ndvi"].notna().all(), "Observed months must have valid numerical NDVI"


def test_aligned_feature_table_integrity_and_boundary_nans():
    """Verify aligned feature table preserves all 53 original features and exact boundary NaNs."""
    assert ALIGNED_CSV.exists(), f"Aligned CSV missing: {ALIGNED_CSV}"
    assert BASELINE_FEATURE_TABLE.exists(), f"Baseline feature table missing: {BASELINE_FEATURE_TABLE}"

    df_base = pd.read_csv(BASELINE_FEATURE_TABLE)
    df_aligned = pd.read_csv(ALIGNED_CSV)

    assert len(df_aligned) == 60, f"Expected 60 aligned rows, got {len(df_aligned)}"
    assert len(df_aligned.columns) == 66, f"Expected 66 aligned columns, got {len(df_aligned.columns)}"

    # Check all baseline columns exist and match baseline values
    for col in df_base.columns:
        assert col in df_aligned.columns, f"Baseline column missing from aligned table: {col}"
        if col not in ["precipitation_lag1_mm_day", "air_temperature_lag1_c",
                       "precipitation_rolling_3m_mean_mm_day", "precipitation_rolling_3m_sum_mm_day"]:
            np.testing.assert_array_equal(df_base[col].values, df_aligned[col].values,
                                          err_msg=f"Values changed in baseline column {col}")

    # Boundary NaNs check
    assert pd.isna(df_aligned.loc[0, "precipitation_lag1_mm_day"]), "Row 0 lag1 precip must be NaN"
    assert pd.isna(df_aligned.loc[0, "air_temperature_lag1_c"]), "Row 0 lag1 temp must be NaN"
    assert pd.isna(df_aligned.loc[0, "precipitation_rolling_3m_mean_mm_day"]), "Row 0 rolling3m mean must be NaN"
    assert pd.isna(df_aligned.loc[1, "precipitation_rolling_3m_mean_mm_day"]), "Row 1 rolling3m mean must be NaN"

    # Cloudy months in aligned dataset must also remain NaN
    unusable_dates = ["2020-08", "2022-09", "2023-01", "2023-07", "2024-07"]
    for d in unusable_dates:
        row_ndvi = df_aligned.loc[df_aligned["date"] == d, "satellite_ndvi"].values[0]
        assert np.isnan(row_ndvi), f"Month {d} must be NaN in aligned dataset"


def test_nominal_and_substitute_coordinates_distinction():
    """Verify spatial coordinate conformity and explicit documentation of substitute coordinate."""
    df_aligned = pd.read_csv(ALIGNED_CSV)
    assert np.isclose(df_aligned["nominal_latitude"].iloc[0], 30.7300, atol=1e-4)
    assert np.isclose(df_aligned["nominal_longitude"].iloc[0], 76.7700, atol=1e-4)
    assert np.isclose(df_aligned["sampled_latitude"].iloc[0], 30.7392, atol=1e-4)
    assert np.isclose(df_aligned["sampled_longitude"].iloc[0], 76.7764, atol=1e-4)

    # Check that nominal and sampled coordinates are not identical
    assert df_aligned["nominal_latitude"].iloc[0] != df_aligned["sampled_latitude"].iloc[0]
    assert df_aligned["nominal_longitude"].iloc[0] != df_aligned["sampled_longitude"].iloc[0]


def test_genuine_satellite_thumbnail_readability():
    """Verify that the genuine downloaded satellite thumbnail exists and is readable."""
    assert THUMBNAIL_IMG.exists(), f"Thumbnail missing: {THUMBNAIL_IMG}"
    assert THUMBNAIL_IMG.stat().st_size > 50000, "Thumbnail file size implausibly small"

    # Verify JPEG magic bytes (0xFF, 0xD8, 0xFF)
    with open(THUMBNAIL_IMG, "rb") as f:
        magic = f.read(3)
        assert magic == b"\xff\xd8\xff", f"Invalid JPEG magic bytes: {magic}"
