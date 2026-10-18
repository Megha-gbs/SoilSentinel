"""Tests for the authenticated dashboard observations payload source."""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Model.bridge import handle_get_observations


def test_observations_are_allow_listed_and_temporally_ordered():
    payload = handle_get_observations()
    assert payload["success"] is True
    assert payload["count"] == len(payload["rows"])
    assert payload["count"] >= 2
    dates = [row["date"] for row in payload["rows"]]
    assert dates == sorted(dates)
    assert dates[0] == payload["date_start"]
    assert dates[-1] == payload["date_end"]
    assert payload["coordinates"]["latitude"] is not None
    assert payload["coordinates"]["longitude"] is not None
    assert all("password" not in row and "email" not in row for row in payload["rows"])


def test_observation_rows_have_chart_units_and_depth_fields():
    payload = handle_get_observations()
    first = payload["rows"][0]
    assert isinstance(first["air_temperature_c"], float)
    assert isinstance(first["precipitation_mm_day"], float)
    assert first["climate_measurement_type"] == "monthly_time_series"
    assert first["soil_measurement_type"] == "static_regional_baseline"
    assert "soc_0_5cm_g_kg" in first
    assert "soc_5_15cm_g_kg" in first
    assert "soc_15_30cm_g_kg" in first
