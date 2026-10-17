"""
SoilSentinel — Automated Validation Test Suite for Real Satellite Data & Aligned Pipelines.

Tests genuine, real-world satellite observations and aligned feature tables:
- File existence and readability
- Schema dimensions and column names
- Chronological date range and continuity (2020-01 to 2024-12, 60 records)
- Physical range bounds for NDVI [-1.0, +1.0] and vegetation fraction [0.0, 1.0]
- Preservation of original baseline features and boundary NaNs in lag features
- Quality assurance flags and geographic coordinate conformity
- Pipeline mathematical reproducibility
"""

import os
import sys
import json
from pathlib import Path

import pytest
import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CATALOG_JSON = PROJECT_ROOT / "data" / "raw" / "satellite" / "sentinel2_monthly_catalog_2020_2024.json"
PROCESSED_CSV = PROJECT_ROOT / "data" / "processed" / "satellite" / "satellite_ndvi_monthly_2020_2024.csv"
ALIGNED_CSV = PROJECT_ROOT / "data" / "processed" / "satellite" / "aligned_feature_table_with_satellite.csv"
THUMBNAIL_IMG = PROJECT_ROOT / "data" / "raw" / "satellite" / "sentinel2_sample_thumbnail.jpg"
BASELINE_FEATURE_TABLE = PROJECT_ROOT / "sireesha" / "feature_table.csv"


def test_raw_satellite_catalog_integrity():
    """Verify raw Sentinel-2 catalog JSON exists, is valid, and contains 60 monthly scenes."""
    assert CATALOG_JSON.exists(), f"Raw catalog missing: {CATALOG_JSON}"
    with open(CATALOG_JSON, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    assert "records" in catalog, "Catalog missing 'records' array"
    records = catalog["records"]
    assert len(records) == 60, f"Expected 60 monthly records, got {len(records)}"

    dates = [r["month"] for r in records]
    assert dates[0] == "2020-01", f"Start month must be 2020-01, got {dates[0]}"
    assert dates[-1] == "2024-12", f"End month must be 2024-12, got {dates[-1]}"
    assert len(dates) == len(set(dates)), "Duplicate months found in raw catalog"

    # Verify scene properties
    for r in records:
        assert r["platform"] in ["sentinel-2a", "sentinel-2b"], f"Unknown platform: {r['platform']}"
        assert 0.0 <= r["cloud_cover_percent"] <= 100.0, f"Cloud cover out of bounds: {r['cloud_cover_percent']}"
        assert 0.0 <= r["vegetation_percent"] <= 100.0, f"Vegetation % out of bounds: {r['vegetation_percent']}"


def test_processed_satellite_csv_schema_and_bounds():
    """Verify processed satellite CSV conforms to schema and physical bounds."""
    assert PROCESSED_CSV.exists(), f"Processed CSV missing: {PROCESSED_CSV}"
    df = pd.read_csv(PROCESSED_CSV)

    assert len(df) == 60, f"Expected 60 rows, got {len(df)}"
    assert len(df.columns) == 20, f"Expected 20 columns, got {len(df.columns)}"

    expected_cols = [
        "region", "nominal_latitude", "nominal_longitude",
        "sampled_latitude", "sampled_longitude", "year", "month", "date",
        "satellite_scene_id", "satellite_observation_date", "satellite_platform",
        "satellite_ndvi", "satellite_vegetation_fraction", "satellite_cloud_cover_percent",
        "satellite_sun_elevation_deg", "satellite_quality_flag", "satellite_spatial_resolution_m",
        "satellite_sensor", "satellite_data_source", "satellite_licence"
    ]
    for c in expected_cols:
        assert c in df.columns, f"Missing expected column: {c}"

    # Physical bounds checks
    assert df["satellite_ndvi"].between(-1.0, 1.0).all(), "NDVI out of bounds [-1.0, 1.0]"
    assert df["satellite_vegetation_fraction"].between(0.0, 1.0).all(), "Vegetation fraction out of bounds [0.0, 1.0]"
    assert df["satellite_cloud_cover_percent"].between(0.0, 100.0).all(), "Cloud cover out of bounds [0, 100]"

    # Quality flags validity
    valid_flags = {"QUALITY_PRISTINE", "QUALITY_GOOD", "QUALITY_ACCEPTABLE", "QUALITY_MARGINAL_CLOUDY"}
    assert set(df["satellite_quality_flag"].unique()).issubset(valid_flags), "Invalid quality flags found"


def test_aligned_feature_table_integrity_and_boundary_nans():
    """Verify aligned feature table preserves all 53 original features and exact boundary NaNs."""
    assert ALIGNED_CSV.exists(), f"Aligned CSV missing: {ALIGNED_CSV}"
    assert BASELINE_FEATURE_TABLE.exists(), f"Baseline feature table missing: {BASELINE_FEATURE_TABLE}"

    df_base = pd.read_csv(BASELINE_FEATURE_TABLE)
    df_aligned = pd.read_csv(ALIGNED_CSV)

    assert len(df_aligned) == 60, f"Expected 60 aligned rows, got {len(df_aligned)}"
    assert len(df_aligned.columns) == 61, f"Expected 61 aligned columns, got {len(df_aligned.columns)}"

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
    assert pd.isna(df_aligned.loc[0, "precipitation_rolling_3m_sum_mm_day"]), "Row 0 rolling3m sum must be NaN"
    assert pd.isna(df_aligned.loc[1, "precipitation_rolling_3m_sum_mm_day"]), "Row 1 rolling3m sum must be NaN"

    # Non-lag columns must have 0 NaNs
    non_lag_cols = [c for c in df_aligned.columns if c not in [
        "precipitation_lag1_mm_day", "air_temperature_lag1_c",
        "precipitation_rolling_3m_mean_mm_day", "precipitation_rolling_3m_sum_mm_day"
    ]]
    assert df_aligned[non_lag_cols].isnull().sum().sum() == 0, "Unexpected NaNs found in non-lag columns"


def test_geographic_coordinates_and_datum():
    """Verify spatial coordinate conformity to nominal and adjusted agricultural site."""
    df_aligned = pd.read_csv(ALIGNED_CSV)
    assert np.isclose(df_aligned["nominal_latitude"].iloc[0], 30.7300, atol=1e-4)
    assert np.isclose(df_aligned["nominal_longitude"].iloc[0], 76.7700, atol=1e-4)
    assert np.isclose(df_aligned["sampled_latitude"].iloc[0], 30.7392, atol=1e-4)
    assert np.isclose(df_aligned["sampled_longitude"].iloc[0], 76.7764, atol=1e-4)


def test_genuine_satellite_thumbnail_readability():
    """Verify that the genuine downloaded satellite thumbnail exists and is readable."""
    assert THUMBNAIL_IMG.exists(), f"Thumbnail missing: {THUMBNAIL_IMG}"
    assert THUMBNAIL_IMG.stat().st_size > 50000, "Thumbnail file size implausibly small"

    # Verify JPEG magic bytes (0xFF, 0xD8, 0xFF)
    with open(THUMBNAIL_IMG, "rb") as f:
        magic = f.read(3)
        assert magic == b"\xff\xd8\xff", f"Invalid JPEG magic bytes: {magic}"

    # Verify image dimensions via PIL if installed
    try:
        from PIL import Image
        im = Image.open(THUMBNAIL_IMG)
        assert im.format == "JPEG"
        assert im.size[0] > 100 and im.size[1] > 100
    except ImportError:
        pass



def test_pipeline_processing_reproducibility():
    """Test mathematical reproducibility of calibrated NDVI pipeline."""
    from scripts.satellite.process_satellite_data import calculate_calibrated_ndvi, assign_quality_flag

    # Case 1: 0% veg, 0% cloud -> bare soil baseline (0.18)
    assert calculate_calibrated_ndvi(0.0, 0.0) == 0.1800

    # Case 2: 100% veg, 0% cloud -> max active canopy (0.18 + 0.70 = 0.88)
    assert calculate_calibrated_ndvi(100.0, 0.0) == 0.8800

    # Case 3: 50% veg, 0% cloud -> (0.18 + 0.35 = 0.53)
    assert calculate_calibrated_ndvi(50.0, 0.0) == 0.5300

    # Quality flag thresholds
    assert assign_quality_flag(2.0) == "QUALITY_PRISTINE"
    assert assign_quality_flag(12.0) == "QUALITY_GOOD"
    assert assign_quality_flag(25.0) == "QUALITY_ACCEPTABLE"
    assert assign_quality_flag(45.0) == "QUALITY_MARGINAL_CLOUDY"
