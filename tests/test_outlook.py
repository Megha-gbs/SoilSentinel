"""
Unit Tests for SoilSentinel Member 2 Weather Forecast Outlook & Scenario Engine.

Verifies:
1. Valid 7-day and 14-day weather forecast retrieval via mocked Open-Meteo API.
2. Rejection of unsupported forecast horizons and invalid coordinates.
3. Robust handling of API timeouts, HTTP errors, connection failures, malformed JSON, and null values.
4. Stale antecedent soil data detection (e.g. 2024-12 record vs 2026 forecast start date).
5. Generation of clearly labeled WEATHER_ONLY_OUTLOOK with no fabricated soil state.
6. Scientific distinction between 2m ambient air temperature and soil temperature.
7. Fresh antecedent coupling when antecedent observation is within allowable age window.
8. Missing or incomplete antecedent feature handling.
9. 30-day hypothetical scenarios (dry_spell, normal_climatology, heavy_rainfall, custom).
10. Strict separation of forecast outputs from scenario outputs (no invented probabilities).
11. End-to-end integration and schema consistency with standard SoilSentinel audit logger.
"""

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

import requests
import pandas as pd

from src.Model.outlook import (
    fetch_weather_forecast,
    check_antecedent_status,
    evaluate_forecast_outlook,
    evaluate_scenario_outlook,
    WeatherForecastResult,
    OutlookResult,
    OPEN_METEO_SOURCE,
    OUTLOOK_INDEX_NAME,
    WEATHER_ONLY_LABEL,
    SCENARIO_LABEL,
    SUPPORTED_FORECAST_HORIZONS,
    SCENARIO_PRESETS,
)
from src.Model.audit_log import AUDIT_LOG_FIELDS


def make_mock_open_meteo_response(days=7, start_date="2026-10-14", base_temp=26.0, base_precip=0.0):
    """Helper to construct synthetic Open-Meteo JSON responses."""
    dates = [f"2026-10-{14 + i:02d}" for i in range(days)]
    temps = [base_temp + (i * 0.2) for i in range(days)]
    precips = [base_precip + (0.5 if i % 3 == 0 else 0.0) for i in range(days)]

    return {
        "latitude": 30.7333,
        "longitude": 76.7794,
        "generationtime_ms": 0.15,
        "utc_offset_seconds": 0,
        "timezone": "UTC",
        "timezone_abbreviation": "UTC",
        "elevation": 312.0,
        "daily_units": {
            "time": "iso8601",
            "temperature_2m_mean": "°C",
            "precipitation_sum": "mm",
        },
        "daily": {
            "time": dates,
            "temperature_2m_mean": temps,
            "precipitation_sum": precips,
        },
    }


class TestFetchWeatherForecast(unittest.TestCase):
    """Tests for fetch_weather_forecast with mocked Open-Meteo API responses."""

    @patch("requests.get")
    def test_valid_7day_forecast_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = make_mock_open_meteo_response(days=7)
        mock_get.return_value = mock_resp

        res = fetch_weather_forecast(lat=30.7333, lon=76.7794, days=7)

        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.forecast_days, 7)
        self.assertEqual(len(res.forecast_dates), 7)
        self.assertEqual(len(res.daily_precipitation), 7)
        self.assertEqual(len(res.daily_mean_air_temperature), 7)
        self.assertEqual(res.source, OPEN_METEO_SOURCE)
        self.assertIn("T", res.retrieval_timestamp)
        self.assertIn("Operational atmospheric weather forecast", res.limitations)
        self.assertIsNone(res.error_message)

    @patch("requests.get")
    def test_valid_14day_forecast_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = make_mock_open_meteo_response(days=14)
        mock_get.return_value = mock_resp

        res = fetch_weather_forecast(lat=30.7333, lon=76.7794, days=14)

        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.forecast_days, 14)
        self.assertEqual(len(res.forecast_dates), 14)

    def test_unsupported_horizons_rejected(self):
        """Operational forecast API must reject unsupported horizons (e.g. 30 days)."""
        for invalid_days in [30, 1, 3, 10, 21, -7, 0]:
            with self.subTest(days=invalid_days):
                with self.assertRaises(ValueError) as ctx:
                    fetch_weather_forecast(lat=30.7333, lon=76.7794, days=invalid_days)
                self.assertIn("Unsupported forecast horizon", str(ctx.exception))
                self.assertIn(str(SUPPORTED_FORECAST_HORIZONS), str(ctx.exception))

    def test_invalid_geographic_coordinates(self):
        with self.assertRaises(ValueError):
            fetch_weather_forecast(lat=95.0, lon=76.7794, days=7)
        with self.assertRaises(ValueError):
            fetch_weather_forecast(lat=-95.0, lon=76.7794, days=7)
        with self.assertRaises(ValueError):
            fetch_weather_forecast(lat=30.7333, lon=185.0, days=7)
        with self.assertRaises(ValueError):
            fetch_weather_forecast(lat=30.7333, lon=-200.0, days=7)

    @patch("requests.get")
    def test_api_timeout_handling(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out after 10s")

        res = fetch_weather_forecast(lat=30.7333, lon=76.7794, days=7, timeout=10)

        self.assertEqual(res.status, "API_TIMEOUT")
        self.assertEqual(len(res.forecast_dates), 0)
        self.assertIn("timed out", res.error_message)

    @patch("requests.get")
    def test_api_http_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.text = "Service Temporarily Unavailable"
        mock_get.return_value = mock_resp

        res = fetch_weather_forecast(lat=30.7333, lon=76.7794, days=7)

        self.assertEqual(res.status, "API_ERROR")
        self.assertIn("503", res.error_message)

    @patch("requests.get")
    def test_api_connection_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("Failed to establish DNS connection")

        res = fetch_weather_forecast(lat=30.7333, lon=76.7794, days=7)

        self.assertEqual(res.status, "API_ERROR")
        self.assertIn("Network request error", res.error_message)

    @patch("requests.get")
    def test_malformed_json_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "<html>error</html>", 0)
        mock_get.return_value = mock_resp

        res = fetch_weather_forecast(lat=30.7333, lon=76.7794, days=7)

        self.assertEqual(res.status, "MALFORMED_DATA")
        self.assertIn("Invalid JSON", res.error_message)

    @patch("requests.get")
    def test_malformed_missing_daily_block(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"latitude": 30.7333, "elevation": 312.0}
        mock_get.return_value = mock_resp

        res = fetch_weather_forecast(lat=30.7333, lon=76.7794, days=7)

        self.assertEqual(res.status, "MALFORMED_DATA")
        self.assertIn("missing expected 'daily' block", res.error_message)

    @patch("requests.get")
    def test_missing_values_in_forecast_series(self, mock_get):
        payload = make_mock_open_meteo_response(days=7)
        payload["daily"]["temperature_2m_mean"][3] = None  # Missing day 4 temperature
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = payload
        mock_get.return_value = mock_resp

        res = fetch_weather_forecast(lat=30.7333, lon=76.7794, days=7)

        self.assertEqual(res.status, "MISSING_VALUES")
        self.assertIn("Null or unobserved", res.error_message)

    @patch("requests.get")
    def test_mismatched_precipitation_array_length(self, mock_get):
        payload = make_mock_open_meteo_response(days=7)
        payload["daily"]["precipitation_sum"] = payload["daily"]["precipitation_sum"][:6]  # 6 precip vs 7 dates
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = payload
        mock_get.return_value = mock_resp

        res = fetch_weather_forecast(lat=30.7333, lon=76.7794, days=7)

        self.assertEqual(res.status, "MALFORMED_DATA")
        self.assertIn("does not equal number of precipitation values", res.error_message)

        # Confirm evaluate_forecast_outlook produces error and no score
        outlook = evaluate_forecast_outlook(res)
        self.assertEqual(outlook.status, "MALFORMED_DATA")
        self.assertEqual(outlook.outlook_type, "ERROR")
        self.assertIsNone(outlook.score)

    @patch("requests.get")
    def test_mismatched_temperature_array_length(self, mock_get):
        payload = make_mock_open_meteo_response(days=7)
        payload["daily"]["temperature_2m_mean"] = payload["daily"]["temperature_2m_mean"][:5]  # 5 temp vs 7 dates
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = payload
        mock_get.return_value = mock_resp

        res = fetch_weather_forecast(lat=30.7333, lon=76.7794, days=7)

        self.assertEqual(res.status, "MALFORMED_DATA")
        self.assertIn("does not equal number of temperature values", res.error_message)

        outlook = evaluate_forecast_outlook(res)
        self.assertIsNone(outlook.score)

    @patch("requests.get")
    def test_mismatched_dates_vs_requested_horizon(self, mock_get):
        payload = make_mock_open_meteo_response(days=5)  # 5 days returned when 7 requested
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = payload
        mock_get.return_value = mock_resp

        res = fetch_weather_forecast(lat=30.7333, lon=76.7794, days=7)

        self.assertEqual(res.status, "MALFORMED_DATA")
        self.assertIn("does not match requested forecast horizon (7 days)", res.error_message)

        outlook = evaluate_forecast_outlook(res)
        self.assertIsNone(outlook.score)



class TestAntecedentStateSafeguards(unittest.TestCase):
    """Tests for safeguarding against stale or unavailable antecedent soil data."""

    def test_stale_antecedent_detection_from_december_2024(self):
        """The latest feature record from 2024-12 evaluated in 2026 must be flagged as STALE."""
        record_2024 = {
            "date": "2024-12",
            "soil_moisture_rootzone_fraction": 0.42,
            "soil_temperature_layer1_c": 18.5,
            "topsoil_soc_g_kg": 12.95,
            "topsoil_ph_mean": 6.55,
        }
        status, age_days, ant_date, note = check_antecedent_status(
            record_2024,
            reference_date_str="2026-10-14",
            max_age_days=60
        )

        self.assertEqual(status, "STALE")
        self.assertGreater(age_days, 600)  # Over 650 days old
        self.assertEqual(ant_date, "2024-12")
        self.assertIn("> threshold 60 days", note)

    def test_fresh_antecedent_detection(self):
        record_fresh = {
            "date": "2026-10-01",
            "soil_moisture_rootzone_fraction": 0.45,
            "soil_temperature_layer1_c": 26.0,
            "topsoil_soc_g_kg": 12.95,
            "topsoil_ph_mean": 6.55,
        }
        status, age_days, ant_date, note = check_antecedent_status(
            record_fresh,
            reference_date_str="2026-10-14",
            max_age_days=60
        )

        self.assertEqual(status, "FRESH")
        self.assertEqual(age_days, 13)
        self.assertIn("<= 60 days", note)

    def test_unavailable_antecedent_missing_record(self):
        status, age_days, ant_date, note = check_antecedent_status(None, "2026-10-14")
        self.assertEqual(status, "UNAVAILABLE")
        self.assertIsNone(age_days)

    def test_unavailable_antecedent_missing_soil_moisture(self):
        record_no_moist = {
            "date": "2026-10-10",
            "soil_moisture_rootzone_fraction": None,
            "topsoil_soc_g_kg": 12.95,
        }
        status, _, _, note = check_antecedent_status(record_no_moist, "2026-10-14")
        self.assertEqual(status, "UNAVAILABLE")
        self.assertIn("soil_moisture_rootzone_fraction", note)

    def test_invalid_future_antecedent_date(self):
        record_future = {
            "date": "2026-11-01",
            "soil_moisture_rootzone_fraction": 0.45,
        }
        status, age_days, _, note = check_antecedent_status(record_future, "2026-10-14")
        self.assertEqual(status, "INVALID_DATE")
        self.assertLess(age_days, 0)


class TestOutlookEvaluation(unittest.TestCase):
    """Tests for evaluating operational forecast outlooks and handling staleness."""

    def setUp(self):
        self.valid_forecast_7d = WeatherForecastResult(
            status="SUCCESS",
            source=OPEN_METEO_SOURCE,
            retrieval_timestamp="2026-10-14T04:00:00Z",
            forecast_days=7,
            forecast_dates=["2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18", "2026-10-19", "2026-10-20"],
            daily_precipitation=[0.0, 0.0, 1.2, 0.0, 0.0, 0.0, 0.5],
            daily_mean_air_temperature=[28.0, 28.5, 27.0, 28.0, 29.0, 28.2, 27.8],
            latitude=30.7333,
            longitude=76.7794,
            limitations="Operational forecast.",
            error_message=None
        )

    def test_stale_antecedent_yields_weather_only_outlook(self):
        """Stale antecedent record must produce WEATHER_ONLY_OUTLOOK with score=None."""
        stale_record = {
            "date": "2024-12",
            "soil_moisture_rootzone_fraction": 0.42,
            "soil_temperature_layer1_c": 18.5,
            "topsoil_soc_g_kg": 12.95,
            "topsoil_ph_mean": 6.55,
        }

        res = evaluate_forecast_outlook(
            forecast=self.valid_forecast_7d,
            antecedent_record=stale_record,
            max_antecedent_age_days=60
        )

        self.assertEqual(res.index_name, OUTLOOK_INDEX_NAME)
        self.assertEqual(res.status, WEATHER_ONLY_LABEL)
        self.assertEqual(res.outlook_type, WEATHER_ONLY_LABEL)
        self.assertEqual(res.risk_category, WEATHER_ONLY_LABEL)
        self.assertIsNone(res.score)  # Must NOT present combined soil-state prediction
        self.assertEqual(res.antecedent_status, "STALE")
        self.assertGreater(res.antecedent_age_days, 60)
        self.assertEqual(res.forecast_horizon_days, 7)

        # Weather atmospheric metrics must be present and valid
        self.assertIsNotNone(res.atmospheric_recharge_deficit_score)
        self.assertIsNotNone(res.atmospheric_thermal_load_score)
        self.assertIsNotNone(res.atmospheric_hydro_thermal_load_score)

        # Scientific disclaimers
        explanation = res.explanation
        self.assertIn("Weather-Only Outlook", explanation)
        self.assertIn("withheld to prevent unscientific stale-data extrapolation", explanation)
        self.assertTrue(any("2-meter ambient temperature" in a for a in res.assumptions))

    def test_fresh_antecedent_yields_coupled_outlook(self):
        """Fresh antecedent record produces coupled provisional score and category."""
        fresh_record = {
            "date": "2026-10-05",
            "soil_moisture_rootzone_fraction": 0.45,
            "soil_temperature_layer1_c": 27.0,
            "topsoil_soc_g_kg": 12.95,
            "topsoil_ph_mean": 6.55,
        }

        res = evaluate_forecast_outlook(
            forecast=self.valid_forecast_7d,
            antecedent_record=fresh_record,
            max_antecedent_age_days=60
        )

        self.assertEqual(res.status, "COMPLETE")
        self.assertEqual(res.outlook_type, "COUPLED_HYDRO_THERMAL_OUTLOOK")
        self.assertEqual(res.antecedent_status, "FRESH")
        self.assertIsNotNone(res.score)
        self.assertGreaterEqual(res.score, 0.0)
        self.assertLessEqual(res.score, 100.0)
        self.assertIn(res.risk_category, ["Low", "Medium", "High"])
        self.assertIsNotNone(res.dynamic_environmental_stress)
        self.assertIsNotNone(res.baseline_soil_vulnerability)

    def test_forecast_api_error_propagation(self):
        err_forecast = WeatherForecastResult(
            status="API_ERROR",
            source=OPEN_METEO_SOURCE,
            retrieval_timestamp="2026-10-14T04:00:00Z",
            forecast_days=7,
            forecast_dates=[],
            daily_precipitation=[],
            daily_mean_air_temperature=[],
            latitude=30.7333,
            longitude=76.7794,
            limitations="API Error",
            error_message="HTTP 500 Internal Server Error"
        )

        res = evaluate_forecast_outlook(forecast=err_forecast)

        self.assertEqual(res.status, "API_ERROR")
        self.assertEqual(res.outlook_type, "ERROR")
        self.assertIsNone(res.score)
        self.assertEqual(res.risk_category, "UNKNOWN")
        self.assertIn("HTTP 500", res.explanation)


class TestHypotheticalScenarioEngine(unittest.TestCase):
    """Tests for the 30-day hypothetical scenario engine."""

    def test_dry_spell_scenario(self):
        res = evaluate_scenario_outlook(scenario_name="dry_spell")

        self.assertEqual(res.status, SCENARIO_LABEL)
        self.assertEqual(res.outlook_type, SCENARIO_LABEL)
        self.assertEqual(res.risk_category, SCENARIO_LABEL)
        self.assertEqual(res.forecast_horizon_days, 30)
        self.assertEqual(res.mean_daily_precipitation_mm_day, 0.0)
        self.assertEqual(res.total_precipitation_mm, 0.0)
        self.assertEqual(res.mean_daily_air_temperature_c, 32.0)
        self.assertEqual(res.forecast_source, "HYPOTHETICAL_SCENARIO_ENGINE")

        # Zero rain rate must produce max recharge deficit
        self.assertEqual(res.atmospheric_recharge_deficit_score, 100.0)

        # Assumptions must explicitly state no probabilities are claimed
        assumptions_str = " ".join(res.assumptions)
        self.assertIn("HYPOTHETICAL SCENARIO", assumptions_str)
        self.assertIn("NO probability of occurrence", assumptions_str)

    def test_normal_climatology_scenario(self):
        res = evaluate_scenario_outlook(scenario_name="normal_climatology")

        self.assertEqual(res.status, SCENARIO_LABEL)
        self.assertEqual(res.mean_daily_precipitation_mm_day, 1.5)
        self.assertEqual(res.mean_daily_air_temperature_c, 24.0)
        self.assertEqual(res.total_precipitation_mm, 45.0)

    def test_heavy_rainfall_scenario(self):
        res = evaluate_scenario_outlook(scenario_name="heavy_rainfall")

        self.assertEqual(res.status, SCENARIO_LABEL)
        self.assertEqual(res.mean_daily_precipitation_mm_day, 15.0)
        # Heavy rain >= 6.0 mm/day yields 0.0 recharge deficit
        self.assertEqual(res.atmospheric_recharge_deficit_score, 0.0)

    def test_custom_scenario(self):
        res = evaluate_scenario_outlook(
            scenario_name="custom",
            custom_daily_precipitation=4.0,
            custom_daily_air_temperature=26.5,
            horizon_days=30
        )
        self.assertEqual(res.mean_daily_precipitation_mm_day, 4.0)
        self.assertEqual(res.mean_daily_air_temperature_c, 26.5)

    def test_unknown_scenario_name_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            evaluate_scenario_outlook(scenario_name="apocalypse_now")
        self.assertIn("Unknown scenario name", str(ctx.exception))

    def test_invalid_horizon_days_raises_value_error(self):
        with self.assertRaises(ValueError):
            evaluate_scenario_outlook(scenario_name="dry_spell", horizon_days=-5)
        with self.assertRaises(ValueError):
            evaluate_scenario_outlook(scenario_name="dry_spell", horizon_days=0)


class TestOutlookAuditLogIntegration(unittest.TestCase):
    """Tests for seamless audit logging of forecasts and scenarios."""

    def test_audit_log_weather_only_entry(self):
        forecast_7d = WeatherForecastResult(
            status="SUCCESS",
            source=OPEN_METEO_SOURCE,
            retrieval_timestamp="2026-10-14T04:00:00Z",
            forecast_days=7,
            forecast_dates=["2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18", "2026-10-19", "2026-10-20"],
            daily_precipitation=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            daily_mean_air_temperature=[28.0, 28.0, 28.0, 28.0, 28.0, 28.0, 28.0],
            latitude=30.7333,
            longitude=76.7794,
            limitations="Standard forecast.",
            error_message=None
        )
        stale_record = {"date": "2024-12", "soil_moisture_rootzone_fraction": 0.40}

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.csv"

            # 1. Log Weather-Only Outlook
            evaluate_forecast_outlook(
                forecast=forecast_7d,
                antecedent_record=stale_record,
                audit_log_path=log_path
            )

            # 2. Log 30-Day Scenario
            evaluate_scenario_outlook(
                scenario_name="dry_spell",
                audit_log_path=log_path
            )

            self.assertTrue(log_path.exists())
            df_log = pd.read_csv(log_path, keep_default_na=False)

            self.assertEqual(len(df_log), 2)
            self.assertEqual(list(df_log.columns), AUDIT_LOG_FIELDS)

            # Row 0: Weather-Only Outlook
            self.assertEqual(df_log.loc[0, "index_name"], OUTLOOK_INDEX_NAME)
            self.assertEqual(df_log.loc[0, "status"], WEATHER_ONLY_LABEL)
            self.assertEqual(df_log.loc[0, "score"], "")  # Empty score for weather-only
            self.assertEqual(df_log.loc[0, "risk_category"], WEATHER_ONLY_LABEL)
            self.assertEqual(df_log.loc[0, "source_id"], "open_meteo_forecast_7d")
            self.assertEqual(df_log.loc[0, "input_date"], "2026-10-14")

            # Row 1: 30-Day Scenario
            self.assertEqual(df_log.loc[1, "index_name"], OUTLOOK_INDEX_NAME)
            self.assertEqual(df_log.loc[1, "status"], SCENARIO_LABEL)
            self.assertEqual(df_log.loc[1, "risk_category"], SCENARIO_LABEL)
            self.assertEqual(df_log.loc[1, "source_id"], "hypothetical_scenario_dry_spell_30d")


if __name__ == "__main__":
    unittest.main()
