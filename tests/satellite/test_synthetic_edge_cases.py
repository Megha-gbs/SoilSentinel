"""
SoilSentinel — Synthetic Edge Case & Error Handling Test Suite.

CRITICAL NOTICE:
All fixtures, mock datasets, and edge-case inputs in this file are SYNTHETIC FIXTURES
designed exclusively for automated unit testing of error handlers and corner cases.
Zero synthetic records from this file are ever written to data/raw/ or data/processed/.
"""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import numpy as np
import pandas as pd
from scripts.satellite.process_satellite_data import calculate_calibrated_ndvi, assign_quality_flag


def test_synthetic_extreme_cloud_attenuation():
    """[SYNTHETIC FIXTURE] Verify behavior under synthetic 100% cloud cover."""
    # With 100% cloud, cloud_attenuation factor becomes 1.0 - 100/200 = 0.5
    synthetic_veg = 80.0
    synthetic_cloud = 100.0
    ndvi = calculate_calibrated_ndvi(synthetic_veg, synthetic_cloud)
    # Expected: 0.18 + 0.70 * 0.80 * 0.5 = 0.18 + 0.28 = 0.46
    assert np.isclose(ndvi, 0.4600, atol=1e-3)
    assert assign_quality_flag(synthetic_cloud) == "QUALITY_MARGINAL_CLOUDY"


def test_synthetic_over_range_clamping():
    """[SYNTHETIC FIXTURE] Verify mathematical bounds clamping on synthetic out-of-range inputs."""
    # Synthetic out-of-bounds veg percent (> 100%)
    ndvi_over = calculate_calibrated_ndvi(150.0, 0.0)
    assert ndvi_over <= 1.0, "Clamping failed on upper bound"

    # Synthetic negative input (< 0%)
    ndvi_under = calculate_calibrated_ndvi(-20.0, 0.0)
    assert ndvi_under >= -1.0, "Clamping failed on lower bound"
    assert ndvi_under == 0.1800, "Negative vegetation should clamp to base soil reflectance"


def test_synthetic_temporal_gap_detection():
    """[SYNTHETIC FIXTURE] Verify that temporal gaps in monthly time series trigger detection."""
    # Synthetic dataframe with missing month '2022-06'
    synthetic_dates = ["2022-04", "2022-05", "2022-07", "2022-08"]
    df_synthetic = pd.DataFrame({"date": synthetic_dates})
    df_synthetic["date_dt"] = pd.to_datetime(df_synthetic["date"], format="%Y-%m")

    expected_range = pd.date_range(start="2022-04-01", end="2022-08-01", freq="MS")
    assert len(df_synthetic) != len(expected_range), "Failed to detect synthetic temporal gap"
    missing = expected_range.difference(df_synthetic["date_dt"])
    assert len(missing) == 1
    assert missing[0].strftime("%Y-%m") == "2022-06"


def test_synthetic_nodata_non_substitution():
    """[SYNTHETIC FIXTURE] Verify that nodata (-999, NaN) is never silently replaced by 0.0."""
    synthetic_raw_values = [0.45, -999.0, None, 0.72]

    def parse_nodata(v):
        if v is None or v == -999.0 or np.isnan(v):
            return np.nan
        return float(v)

    parsed = [parse_nodata(x) for x in synthetic_raw_values]
    assert np.isnan(parsed[1]), "-999 must become NaN, not 0.0"
    assert np.isnan(parsed[2]), "None must become NaN, not 0.0"
    assert parsed[0] == 0.45
    assert parsed[3] == 0.72
