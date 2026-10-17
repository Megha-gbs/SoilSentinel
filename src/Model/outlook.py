"""
SoilSentinel - Member 2: Weather Forecast Outlook & Hypothetical Scenario Engine.

Provides defensible, transparent short-to-medium range environmental risk outlooks:
1. Operational Weather Forecast Outlook (7-day and 14-day horizons) via Open-Meteo.
2. Safeguards against Stale / Unavailable Antecedent Soil Data:
   - Actively verifies antecedent record timestamps against forecast dates.
   - Rejects stale antecedent data (e.g. historical records from 2024-12 evaluated in 2026).
   - Generates clearly labeled "WEATHER_ONLY_OUTLOOK" without fabricating soil state.
   - Never conflates 2-meter ambient air temperature with root-zone soil temperature.
3. 30-Day Hypothetical Scenario Engine:
   - Formally labeled "HYPOTHETICAL_SCENARIO" for stress-testing and resilience planning.
   - Documented, configurable presets (dry_spell, normal_climatology, heavy_rainfall).
   - Does NOT invent scenario probabilities, confidence percentages, or validation accuracy.
4. Seamless, non-breaking integration with the standard SoilSentinel audit logger.
5. IBM LinuxONE (s390x) Portable: Pure Python, NumPy, Pandas, and Requests. Zero native C extensions.
"""

import sys
import json
import logging
import argparse
from datetime import datetime, date, timezone
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import requests

# Ensure project root resolution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Model.audit_log import (
    DEFAULT_AUDIT_LOG_PATH,
    OUTLOOK_INDEX_NAME,
    log_outlook_entry,
)
from src.Model.risk_scoring import (
    calculate_moisture_deficit_score,
    calculate_buffering_factor,
    calculate_soc_vulnerability_score,
    calculate_ph_deviation_score,
    WEIGHT_MOISTURE_DEFICIT,
    WEIGHT_PRECIPITATION_DEFICIT,
    WEIGHT_THERMAL_STRESS,
    WEIGHT_SOC_DEPLETION,
    WEIGHT_PH_DEVIATION,
    THRESHOLD_LOW_UPPER,
    THRESHOLD_MEDIUM_UPPER,
)

logger = logging.getLogger("outlook")

# ---------------------------------------------------------------------------
# Constants & Configuration
# ---------------------------------------------------------------------------

OPEN_METEO_API_URL = "https://api.open-meteo.com/v1/forecast"
SUPPORTED_FORECAST_HORIZONS = (7, 14)
DEFAULT_FORECAST_DAYS = 7
DEFAULT_MAX_ANTECEDENT_AGE_DAYS = 60
DEFAULT_TIMEOUT_SECONDS = 10

OPEN_METEO_SOURCE = "Open-Meteo Weather Forecast API"
SCENARIO_LABEL = "HYPOTHETICAL_SCENARIO"
WEATHER_ONLY_LABEL = "WEATHER_ONLY_OUTLOOK"

# Atmospheric stress normalization thresholds (Provisional Engineering Heuristics)
AIR_TEMP_HEAT_BASELINE_C = 22.0
AIR_TEMP_HEAT_SEVERE_C = 38.0
PRECIP_DEFICIT_MIN_RATE_MM_DAY = 0.5
PRECIP_DEFICIT_MAX_RATE_MM_DAY = 6.0

# 30-Day Hypothetical Scenario Presets
SCENARIO_PRESETS: Dict[str, Dict[str, Any]] = {
    "dry_spell": {
        "name": "dry_spell",
        "description": "Extended 30-day acute dry spell with zero precipitation and elevated ambient air temperatures.",
        "daily_precipitation_mm_day": 0.0,
        "daily_mean_air_temperature_c": 32.0,
        "horizon_days": 30,
        "assumptions": [
            "Assumes zero atmospheric precipitation over the entire 30-day projection horizon.",
            "Assumes constant elevated 2m air temperature of 32.0 C (+3.0 C regional anomaly).",
            "Atmospheric evaporative demand is sustained at high levels without precipitation replenishment.",
            "Does not simulate subsurface irrigation, perched water tables, or capillary flux.",
        ],
    },
    "normal_climatology": {
        "name": "normal_climatology",
        "description": "Historical regional transition-season climatological average conditions.",
        "daily_precipitation_mm_day": 1.5,
        "daily_mean_air_temperature_c": 24.0,
        "horizon_days": 30,
        "assumptions": [
            "Assumes steady climatological baseline rainfall of 1.5 mm/day (approx. 45 mm cumulative).",
            "Assumes seasonal average 2m air temperature of 24.0 C.",
            "Represents typical Indo-Gangetic autumn/spring meteorological conditions.",
        ],
    },
    "heavy_rainfall": {
        "name": "heavy_rainfall",
        "description": "Active monsoon / atmospheric recharge pulse with high cumulative precipitation.",
        "daily_precipitation_mm_day": 15.0,
        "daily_mean_air_temperature_c": 22.0,
        "horizon_days": 30,
        "assumptions": [
            "Assumes persistent high atmospheric precipitation of 15.0 mm/day (450 mm cumulative).",
            "Assumes moderate 2m air temperature of 22.0 C during cloudy/rainy conditions.",
            "Evaluates potential waterlogging and excess recharge scenarios.",
        ],
    },
}


# ---------------------------------------------------------------------------
# Structured Result Containers
# ---------------------------------------------------------------------------

@dataclass
class WeatherForecastResult:
    """Structured container for retrieved Open-Meteo weather forecast data."""
    status: str  # "SUCCESS", "API_ERROR", "API_TIMEOUT", "MALFORMED_DATA", "UNSUPPORTED_HORIZON"
    source: str
    retrieval_timestamp: str
    forecast_days: int
    forecast_dates: List[str]
    daily_precipitation: List[float]
    daily_mean_air_temperature: List[float]
    latitude: float
    longitude: float
    limitations: str
    error_message: Optional[str] = None

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OutlookResult:
    """Structured container for SoilSentinel Risk Outlooks and Scenarios."""
    index_name: str
    outlook_type: str  # "WEATHER_ONLY_OUTLOOK", "COUPLED_HYDRO_THERMAL_OUTLOOK", "HYPOTHETICAL_SCENARIO", "ERROR"
    status: str        # "WEATHER_ONLY_OUTLOOK", "COMPLETE", "STALE_ANTECEDENT", "UNAVAILABLE_ANTECEDENT", "API_ERROR", "HYPOTHETICAL_SCENARIO"
    score: Optional[float]
    risk_category: str  # "WEATHER_ONLY_OUTLOOK", "Low", "Medium", "High", "HYPOTHETICAL_SCENARIO", "UNKNOWN"
    antecedent_status: str  # "STALE", "UNAVAILABLE", "FRESH", "INCOMPLETE"
    antecedent_date: Optional[str]
    antecedent_age_days: Optional[int]
    forecast_source: str
    forecast_horizon_days: int
    forecast_start_date: Optional[str]
    forecast_end_date: Optional[str]
    mean_daily_precipitation_mm_day: Optional[float]
    total_precipitation_mm: Optional[float]
    mean_daily_air_temperature_c: Optional[float]
    atmospheric_recharge_deficit_score: Optional[float]
    atmospheric_thermal_load_score: Optional[float]
    atmospheric_hydro_thermal_load_score: Optional[float]
    dynamic_environmental_stress: Optional[float]
    baseline_soil_vulnerability: Optional[float]
    indicators: Dict[str, Any] = field(default_factory=dict)
    assumptions: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    explanation: str = ""
    scenario_label: Optional[str] = None
    scenario_name: Optional[str] = None
    location_id: Optional[str] = None
    date: Optional[str] = None

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Core Weather API Client
# ---------------------------------------------------------------------------

def fetch_weather_forecast(
    lat: float,
    lon: float,
    days: int = DEFAULT_FORECAST_DAYS,
    timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> WeatherForecastResult:
    """
    Retrieve operational weather forecast from Open-Meteo for supported horizons.

    Parameters:
        lat: Geographic latitude in decimal degrees [-90.0, 90.0].
        lon: Geographic longitude in decimal degrees [-180.0, 180.0].
        days: Forecast horizon in days. Supported horizons: 7 or 14 days.
        timeout: Network socket timeout in seconds.

    Returns:
        Structured WeatherForecastResult.

    Raises:
        ValueError: If coordinates or requested days horizon are outside valid parameters.
    """
    # 1. Geographic input validation
    if not isinstance(lat, (int, float)) or not (-90.0 <= lat <= 90.0):
        raise ValueError(f"Latitude must be a valid float between -90.0 and 90.0 degrees; received {lat}.")
    if not isinstance(lon, (int, float)) or not (-180.0 <= lon <= 180.0):
        raise ValueError(f"Longitude must be a valid float between -180.0 and 180.0 degrees; received {lon}.")

    # 2. Forecast horizon validation
    if days not in SUPPORTED_FORECAST_HORIZONS:
        raise ValueError(
            f"Unsupported forecast horizon: {days} days. "
            f"Open-Meteo operational weather forecasts are only supported for {SUPPORTED_FORECAST_HORIZONS} days. "
            "For 30-day projections, use evaluate_scenario_outlook()."
        )

    retrieval_ts = datetime.now(timezone.utc).isoformat()
    standard_limitations = (
        f"Operational atmospheric weather forecast sourced from {OPEN_METEO_SOURCE}. "
        "Provides 2m ambient air temperature and precipitation. Does NOT measure or model root-zone "
        "soil moisture or soil temperature. Forecast skill degrades with increasing horizon; "
        "atmospheric forecasts do not prove actual future weather will occur."
    )

    params = {
        "latitude": round(float(lat), 4),
        "longitude": round(float(lon), 4),
        "daily": "temperature_2m_mean,precipitation_sum",
        "forecast_days": int(days),
        "timezone": "UTC",
    }

    try:
        response = requests.get(
            OPEN_METEO_API_URL,
            params=params,
            timeout=timeout,
            headers={"User-Agent": "SoilSentinel-AI-Risk-Engine/1.0"}
        )
    except requests.exceptions.Timeout:
        logger.warning("Open-Meteo API connection timed out after %d seconds.", timeout)
        return WeatherForecastResult(
            status="API_TIMEOUT",
            source=OPEN_METEO_SOURCE,
            retrieval_timestamp=retrieval_ts,
            forecast_days=days,
            forecast_dates=[],
            daily_precipitation=[],
            daily_mean_air_temperature=[],
            latitude=lat,
            longitude=lon,
            limitations=standard_limitations,
            error_message=f"Request to {OPEN_METEO_API_URL} timed out after {timeout} seconds."
        )
    except requests.exceptions.RequestException as exc:
        logger.warning("Open-Meteo API network request failed: %s", exc)
        return WeatherForecastResult(
            status="API_ERROR",
            source=OPEN_METEO_SOURCE,
            retrieval_timestamp=retrieval_ts,
            forecast_days=days,
            forecast_dates=[],
            daily_precipitation=[],
            daily_mean_air_temperature=[],
            latitude=lat,
            longitude=lon,
            limitations=standard_limitations,
            error_message=f"Network request error: {str(exc)}"
        )

    # 3. HTTP status check
    if response.status_code != 200:
        logger.warning("Open-Meteo API returned HTTP %d: %s", response.status_code, response.text[:200])
        return WeatherForecastResult(
            status="API_ERROR",
            source=OPEN_METEO_SOURCE,
            retrieval_timestamp=retrieval_ts,
            forecast_days=days,
            forecast_dates=[],
            daily_precipitation=[],
            daily_mean_air_temperature=[],
            latitude=lat,
            longitude=lon,
            limitations=standard_limitations,
            error_message=f"Open-Meteo API returned HTTP {response.status_code}: {response.text[:150]}"
        )

    # 4. JSON parsing and structure validation
    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        return WeatherForecastResult(
            status="MALFORMED_DATA",
            source=OPEN_METEO_SOURCE,
            retrieval_timestamp=retrieval_ts,
            forecast_days=days,
            forecast_dates=[],
            daily_precipitation=[],
            daily_mean_air_temperature=[],
            latitude=lat,
            longitude=lon,
            limitations=standard_limitations,
            error_message=f"Invalid JSON response: {str(exc)}"
        )

    daily = data.get("daily")
    if not isinstance(daily, dict):
        return WeatherForecastResult(
            status="MALFORMED_DATA",
            source=OPEN_METEO_SOURCE,
            retrieval_timestamp=retrieval_ts,
            forecast_days=days,
            forecast_dates=[],
            daily_precipitation=[],
            daily_mean_air_temperature=[],
            latitude=lat,
            longitude=lon,
            limitations=standard_limitations,
            error_message="Response missing expected 'daily' block."
        )

    dates = daily.get("time")
    precip = daily.get("precipitation_sum")
    temp = daily.get("temperature_2m_mean")

    if not isinstance(dates, list) or not isinstance(precip, list) or not isinstance(temp, list):
        return WeatherForecastResult(
            status="MALFORMED_DATA",
            source=OPEN_METEO_SOURCE,
            retrieval_timestamp=retrieval_ts,
            forecast_days=days,
            forecast_dates=[],
            daily_precipitation=[],
            daily_mean_air_temperature=[],
            latitude=lat,
            longitude=lon,
            limitations=standard_limitations,
            error_message="Incomplete or non-list daily series in Open-Meteo response."
        )

    # Validate array lengths match each other and requested horizon
    if len(dates) != int(days):
        return WeatherForecastResult(
            status="MALFORMED_DATA",
            source=OPEN_METEO_SOURCE,
            retrieval_timestamp=retrieval_ts,
            forecast_days=days,
            forecast_dates=[],
            daily_precipitation=[],
            daily_mean_air_temperature=[],
            latitude=lat,
            longitude=lon,
            limitations=standard_limitations,
            error_message=(
                f"Date array length ({len(dates)}) does not match requested forecast horizon ({days} days)."
            )
        )

    if len(dates) != len(precip):
        return WeatherForecastResult(
            status="MALFORMED_DATA",
            source=OPEN_METEO_SOURCE,
            retrieval_timestamp=retrieval_ts,
            forecast_days=days,
            forecast_dates=[],
            daily_precipitation=[],
            daily_mean_air_temperature=[],
            latitude=lat,
            longitude=lon,
            limitations=standard_limitations,
            error_message=(
                f"Number of dates ({len(dates)}) does not equal number of precipitation values ({len(precip)})."
            )
        )

    if len(dates) != len(temp):
        return WeatherForecastResult(
            status="MALFORMED_DATA",
            source=OPEN_METEO_SOURCE,
            retrieval_timestamp=retrieval_ts,
            forecast_days=days,
            forecast_dates=[],
            daily_precipitation=[],
            daily_mean_air_temperature=[],
            latitude=lat,
            longitude=lon,
            limitations=standard_limitations,
            error_message=(
                f"Number of dates ({len(dates)}) does not equal number of temperature values ({len(temp)})."
            )
        )

    # 5. Missing value / NaN inspection
    clean_precip: List[float] = []
    clean_temp: List[float] = []
    for p_val, t_val in zip(precip, temp):
        if p_val is None or t_val is None:
            return WeatherForecastResult(
                status="MISSING_VALUES",
                source=OPEN_METEO_SOURCE,
                retrieval_timestamp=retrieval_ts,
                forecast_days=days,
                forecast_dates=[],
                daily_precipitation=[],
                daily_mean_air_temperature=[],
                latitude=lat,
                longitude=lon,
                limitations=standard_limitations,
                error_message="Null or unobserved daily forecast entries encountered."
            )
        clean_precip.append(round(float(p_val), 2))
        clean_temp.append(round(float(t_val), 2))

    return WeatherForecastResult(
        status="SUCCESS",
        source=OPEN_METEO_SOURCE,
        retrieval_timestamp=retrieval_ts,
        forecast_days=len(dates),
        forecast_dates=[str(d) for d in dates],
        daily_precipitation=clean_precip,
        daily_mean_air_temperature=clean_temp,
        latitude=float(data.get("latitude", lat)),
        longitude=float(data.get("longitude", lon)),
        limitations=standard_limitations,
        error_message=None
    )


# ---------------------------------------------------------------------------
# Antecedent State Staleness & Unavailability Safeguard
# ---------------------------------------------------------------------------

def parse_date_safely(date_input: Any) -> Optional[date]:
    """Parse string or tuple representation of date into a datetime.date object."""
    if date_input is None or (isinstance(date_input, float) and np.isnan(date_input)):
        return None
    s = str(date_input).strip()
    # Try YYYY-MM-DD
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except (ValueError, IndexError):
        pass
    # Try YYYY-MM
    try:
        dt = datetime.strptime(s[:7], "%Y-%m")
        return dt.date()
    except (ValueError, IndexError):
        pass
    # Try YYYY/MM
    try:
        dt = datetime.strptime(s[:7], "%Y/%m")
        return dt.date()
    except (ValueError, IndexError):
        pass
    return None


def check_antecedent_status(
    antecedent_record: Optional[Union[Dict[str, Any], pd.Series]],
    reference_date_str: Optional[str] = None,
    max_age_days: int = DEFAULT_MAX_ANTECEDENT_AGE_DAYS
) -> Tuple[str, Optional[int], Optional[str], str]:
    """
    Verify antecedent record validity, feature presence, and temporal staleness.

    Parameters:
        antecedent_record: Dictionary or Series with antecedent soil features.
        reference_date_str: Forecast start date string (e.g. "2026-10-14").
        max_age_days: Maximum allowable age in days before flagging as STALE.

    Returns:
        (status, age_days, antecedent_date_str, explanation)
        status is one of: "FRESH", "STALE", "UNAVAILABLE", "INCOMPLETE", "INVALID_DATE".
    """
    if antecedent_record is None:
        return "UNAVAILABLE", None, None, "No antecedent soil observation provided."

    # Convert Series to dict if needed
    rec = antecedent_record.to_dict() if isinstance(antecedent_record, pd.Series) else dict(antecedent_record)

    # 1. Check essential physical soil features
    rootzone_val = rec.get("soil_moisture_rootzone_fraction")
    if rootzone_val is None or (isinstance(rootzone_val, float) and np.isnan(rootzone_val)):
        return "UNAVAILABLE", None, None, "Antecedent record missing essential 'soil_moisture_rootzone_fraction'."

    # 2. Extract and parse antecedent date
    raw_date = rec.get("date")
    if not raw_date and "year" in rec and "month" in rec:
        raw_date = f"{rec['year']}-{int(rec['month']):02d}"

    ant_date = parse_date_safely(raw_date)
    if ant_date is None:
        return "UNAVAILABLE", None, None, f"Antecedent record missing valid temporal date identifier: {raw_date}."

    ant_date_str = ant_date.strftime("%Y-%m-%d" if len(str(raw_date)) > 7 else "%Y-%m")

    # 3. Compare with reference forecast start date
    if reference_date_str is None:
        return "FRESH", None, ant_date_str, f"Antecedent observation date: {ant_date_str} (no reference date compared)."

    ref_date = parse_date_safely(reference_date_str)
    if ref_date is None:
        return "FRESH", None, ant_date_str, f"Reference date '{reference_date_str}' unparseable; staleness check bypassed."

    age_days = (ref_date - ant_date).days

    if age_days < 0:
        return (
            "INVALID_DATE",
            age_days,
            ant_date_str,
            f"Antecedent date ({ant_date_str}) is in the future relative to forecast start date ({reference_date_str})."
        )

    if age_days > max_age_days:
        return (
            "STALE",
            age_days,
            ant_date_str,
            f"Antecedent soil record ({ant_date_str}) is {age_days} days old (> threshold {max_age_days} days). "
            "Dynamic soil moisture and temperature evolve rapidly and cannot be treated as valid current conditions."
        )

    return (
        "FRESH",
        age_days,
        ant_date_str,
        f"Antecedent record ({ant_date_str}) is fresh ({age_days} days old <= {max_age_days} days)."
    )


# ---------------------------------------------------------------------------
# Derived Indicator Calculation: Atmospheric Stress Metrics
# ---------------------------------------------------------------------------

def calculate_atmospheric_recharge_deficit_score(mean_daily_precip_mm_day: float) -> Tuple[float, str]:
    """
    Calculate atmospheric precipitation recharge deficit sub-score [0, 100].
    Consistent with the baseline meteorological deficit piecewise function.
    """
    rate = max(0.0, float(mean_daily_precip_mm_day))
    if rate <= PRECIP_DEFICIT_MIN_RATE_MM_DAY:
        score = 100.0
    elif rate >= PRECIP_DEFICIT_MAX_RATE_MM_DAY:
        score = 0.0
    else:
        score = 100.0 * (PRECIP_DEFICIT_MAX_RATE_MM_DAY - rate) / (
            PRECIP_DEFICIT_MAX_RATE_MM_DAY - PRECIP_DEFICIT_MIN_RATE_MM_DAY
        )
    note = (
        f"Mean forecast precipitation = {rate:.2f} mm/day. "
        f"Atmospheric recharge deficit sub-score = {score:.2f}/100."
    )
    return round(float(score), 2), note


def calculate_atmospheric_thermal_load_score(mean_daily_air_temp_c: float) -> Tuple[float, str]:
    """
    Calculate atmospheric thermal load sub-score [0, 100] based on 2m ambient air temperature.

    CRITICAL DISTINCTION:
    Ambient air temperature is an atmospheric driver of evaporative demand and surface heat flux.
    It is NOT measured soil temperature.
    """
    temp = float(mean_daily_air_temp_c)
    if temp <= AIR_TEMP_HEAT_BASELINE_C:
        score = 0.0
    elif temp >= AIR_TEMP_HEAT_SEVERE_C:
        score = 100.0
    else:
        score = 100.0 * (temp - AIR_TEMP_HEAT_BASELINE_C) / (
            AIR_TEMP_HEAT_SEVERE_C - AIR_TEMP_HEAT_BASELINE_C
        )
    note = (
        f"Mean forecast 2m air temperature = {temp:.1f} C. "
        f"Atmospheric thermal load sub-score = {score:.2f}/100. "
        "(Note: Reflects ambient evaporative forcing; not soil temperature)."
    )
    return round(float(score), 2), note


# ---------------------------------------------------------------------------
# Operational Forecast Outlook Projection Function (7-day and 14-day)
# ---------------------------------------------------------------------------

def evaluate_forecast_outlook(
    forecast: Union[Dict[str, Any], WeatherForecastResult],
    antecedent_record: Optional[Union[Dict[str, Any], pd.Series]] = None,
    max_antecedent_age_days: int = DEFAULT_MAX_ANTECEDENT_AGE_DAYS,
    audit_log_path: Optional[Union[str, Path]] = None,
    location_id: Optional[str] = None
) -> OutlookResult:
    """
    Evaluate Provisional Hydro-Thermal Stress Outlook for operational 7-day or 14-day forecasts.

    Enforces all scientific safeguards:
    - Verifies Open-Meteo forecast status and reports actual dates and values.
    - Inspects antecedent soil record. If STALE or UNAVAILABLE:
        * Marks antecedent state as STALE or UNAVAILABLE.
        * Does NOT present output as a combined current soil-state prediction (score = None).
        * Produces a clearly labeled WEATHER_ONLY_OUTLOOK.
        * Never fabricates soil moisture or substitutes air temp for soil temp.
    - If antecedent record is FRESH:
        * Computes coupled provisional hydro-thermal stress indicator.
    - Logs to standard audit log if path provided.

    Parameters:
        forecast: WeatherForecastResult or dictionary from fetch_weather_forecast.
        antecedent_record: Optional antecedent feature record.
        max_antecedent_age_days: Maximum allowed age in days for antecedent soil data.
        audit_log_path: Optional path to write audit entry.
        location_id: Optional regional or coordinate identifier.

    Returns:
        Structured OutlookResult.
    """
    # 1. Handle API Errors or Non-Success Forecast Inputs
    f_status = forecast.get("status")
    if f_status != "SUCCESS":
        err_msg = forecast.get("error_message") or f"Weather forecast status: {f_status}"
        res = OutlookResult(
            index_name=OUTLOOK_INDEX_NAME,
            outlook_type="ERROR",
            status=str(f_status or "API_ERROR"),
            score=None,
            risk_category="UNKNOWN",
            antecedent_status="UNAVAILABLE",
            antecedent_date=None,
            antecedent_age_days=None,
            forecast_source=str(forecast.get("source") or OPEN_METEO_SOURCE),
            forecast_horizon_days=int(forecast.get("forecast_days") or 0),
            forecast_start_date=None,
            forecast_end_date=None,
            mean_daily_precipitation_mm_day=None,
            total_precipitation_mm=None,
            mean_daily_air_temperature_c=None,
            atmospheric_recharge_deficit_score=None,
            atmospheric_thermal_load_score=None,
            atmospheric_hydro_thermal_load_score=None,
            dynamic_environmental_stress=None,
            baseline_soil_vulnerability=None,
            explanation=f"Forecast outlook failed: {err_msg}",
            limitations=[str(forecast.get("limitations") or "Forecast data unavailable.")],
            location_id=location_id
        )
        if audit_log_path is not None:
            log_outlook_entry(
                res.to_dict(),
                source_id=f"forecast_api_error_{forecast.get('forecast_days', 'unknown')}d",
                log_path=audit_log_path
            )
        return res

    # 2. Extract Forecast Metrics
    forecast_dates: List[str] = list(forecast.get("forecast_dates") or [])
    daily_precip: List[float] = [float(p) for p in (forecast.get("daily_precipitation") or [])]
    daily_temp: List[float] = [float(t) for t in (forecast.get("daily_mean_air_temperature") or [])]

    if not forecast_dates or not daily_precip or not daily_temp:
        raise ValueError("Forecast contains empty series despite SUCCESS status.")

    start_date = forecast_dates[0]
    end_date = forecast_dates[-1]
    horizon_days = len(forecast_dates)

    total_precip = round(float(sum(daily_precip)), 2)
    mean_daily_precip = round(float(np.mean(daily_precip)), 2)
    mean_daily_temp = round(float(np.mean(daily_temp)), 2)

    # 3. Compute Atmospheric Metrics
    recharge_deficit_score, recharge_note = calculate_atmospheric_recharge_deficit_score(mean_daily_precip)
    thermal_load_score, thermal_note = calculate_atmospheric_thermal_load_score(mean_daily_temp)
    # Balanced atmospheric load (0.50 recharge deficit + 0.50 air thermal load)
    atm_load_score = round(0.50 * recharge_deficit_score + 0.50 * thermal_load_score, 2)

    # Resolve location identifier
    resolved_loc = location_id
    if not resolved_loc:
        lat = forecast.get("latitude")
        lon = forecast.get("longitude")
        if lat is not None and lon is not None:
            resolved_loc = f"{lat},{lon}"
        else:
            resolved_loc = "UNKNOWN"

    # 4. Check Antecedent Soil Condition
    ant_status, ant_age_days, ant_date_str, ant_note = check_antecedent_status(
        antecedent_record=antecedent_record,
        reference_date_str=start_date,
        max_age_days=max_antecedent_age_days
    )

    assumptions = [
        f"Weather forecast sourced directly from {OPEN_METEO_SOURCE} for {horizon_days}-day horizon ({start_date} to {end_date}).",
        "Forecast air temperature represents 2-meter ambient temperature; it is NOT measured soil temperature.",
        "Atmospheric forecasts do NOT guarantee future meteorological outcomes; skills degrade with forecast horizon.",
    ]
    limitations = [
        forecast.get("limitations") or "Operational atmospheric weather forecast.",
        "Soil hydrological memory and root-zone water storage are not dynamically simulated in weather-only outlook.",
    ]

    # -----------------------------------------------------------------------
    # Case A: Antecedent Soil Data is STALE or UNAVAILABLE
    # -----------------------------------------------------------------------
    if ant_status in ("STALE", "UNAVAILABLE", "INCOMPLETE", "INVALID_DATE"):
        limitations.append(
            f"Antecedent soil state is marked {ant_status}. {ant_note} "
            "Soil moisture and temperature are unobserved. Combined current soil-state prediction is withheld."
        )
        explanation = (
            f"SoilSentinel {horizon_days}-Day Weather-Only Outlook: "
            f"Antecedent soil record is {ant_status} ({ant_note}). "
            f"Forecast atmospheric recharge deficit = {recharge_deficit_score:.1f}/100, "
            f"atmospheric thermal load = {thermal_load_score:.1f}/100. "
            f"Composite atmospheric load = {atm_load_score:.1f}/100. "
            "Combined soil-state risk prediction withheld to prevent unscientific stale-data extrapolation."
        )

        res = OutlookResult(
            index_name=OUTLOOK_INDEX_NAME,
            outlook_type=WEATHER_ONLY_LABEL,
            status=WEATHER_ONLY_LABEL,
            score=None,  # Crucial: DO NOT fabricate or present combined soil score
            risk_category=WEATHER_ONLY_LABEL,
            antecedent_status=ant_status,
            antecedent_date=ant_date_str,
            antecedent_age_days=ant_age_days,
            forecast_source=OPEN_METEO_SOURCE,
            forecast_horizon_days=horizon_days,
            forecast_start_date=start_date,
            forecast_end_date=end_date,
            mean_daily_precipitation_mm_day=mean_daily_precip,
            total_precipitation_mm=total_precip,
            mean_daily_air_temperature_c=mean_daily_temp,
            atmospheric_recharge_deficit_score=recharge_deficit_score,
            atmospheric_thermal_load_score=thermal_load_score,
            atmospheric_hydro_thermal_load_score=atm_load_score,
            dynamic_environmental_stress=None,
            baseline_soil_vulnerability=None,
            indicators={
                "atmospheric_recharge_deficit": {"score": recharge_deficit_score, "note": recharge_note},
                "atmospheric_thermal_load": {"score": thermal_load_score, "note": thermal_note},
                "antecedent_soil": {"status": ant_status, "note": ant_note},
            },
            assumptions=assumptions,
            limitations=limitations,
            explanation=explanation,
            location_id=resolved_loc,
            date=start_date
        )

        if audit_log_path is not None:
            log_outlook_entry(
                res.to_dict(),
                source_id=f"open_meteo_forecast_{horizon_days}d",
                log_path=audit_log_path
            )
        return res

    # -----------------------------------------------------------------------
    # Case B: Antecedent Soil Data is FRESH
    # -----------------------------------------------------------------------
    rec = antecedent_record.to_dict() if isinstance(antecedent_record, pd.Series) else dict(antecedent_record)

    rootzone_moist = float(rec["soil_moisture_rootzone_fraction"])
    soc_val = float(rec.get("topsoil_soc_g_kg", 12.95))
    ph_val = float(rec.get("topsoil_ph_mean", 6.55))

    # 1. Moisture deficit from fresh antecedent
    moist_score, moist_note = calculate_moisture_deficit_score(rootzone_moist)

    # 2. Moisture buffering applied to forecast precipitation recharge deficit
    buffering_factor, buffer_note = calculate_buffering_factor(rootzone_moist)
    buffered_precip_score = round(float(recharge_deficit_score * buffering_factor), 2)

    # 3. Static Baseline Soil Vulnerability
    soc_score, soc_note = calculate_soc_vulnerability_score(soc_val)
    ph_score, ph_note = calculate_ph_deviation_score(ph_val)

    # 4. Composite Scoring
    dynamic_stress = (
        WEIGHT_MOISTURE_DEFICIT * moist_score
        + WEIGHT_PRECIPITATION_DEFICIT * buffered_precip_score
        + WEIGHT_THERMAL_STRESS * thermal_load_score
    )
    baseline_vuln = (
        WEIGHT_SOC_DEPLETION * soc_score
        + WEIGHT_PH_DEVIATION * ph_score
    )
    total_score = round(float(dynamic_stress + baseline_vuln), 2)

    if total_score < THRESHOLD_LOW_UPPER:
        category = "Low"
    elif total_score < THRESHOLD_MEDIUM_UPPER:
        category = "Medium"
    else:
        category = "High"

    assumptions.append(
        f"Coupled evaluation uses validated FRESH antecedent soil observation from {ant_date_str} ({ant_age_days} days old)."
    )
    assumptions.append(
        "Antecedent root-zone soil moisture is assumed as starting condition; soil moisture drainage/depletion is not dynamically modeled."
    )

    explanation = (
        f"SoilSentinel {horizon_days}-Day Provisional Hydro-Thermal Stress Outlook: "
        f"Score = {total_score:.2f} ({category} Risk). "
        f"Dynamic Atmospheric & Soil Stress = {dynamic_stress:.2f}/70.0, "
        f"Baseline Inherent Vulnerability = {baseline_vuln:.2f}/30.0. "
        f"Antecedent moisture = {rootzone_moist:.3f} (buffering factor = {buffering_factor:.2f}). "
        f"Forecast rain rate = {mean_daily_precip:.2f} mm/day, forecast mean air temp = {mean_daily_temp:.1f} C."
    )

    res = OutlookResult(
        index_name=OUTLOOK_INDEX_NAME,
        outlook_type="COUPLED_HYDRO_THERMAL_OUTLOOK",
        status="COMPLETE",
        score=total_score,
        risk_category=category,
        antecedent_status="FRESH",
        antecedent_date=ant_date_str,
        antecedent_age_days=ant_age_days,
        forecast_source=OPEN_METEO_SOURCE,
        forecast_horizon_days=horizon_days,
        forecast_start_date=start_date,
        forecast_end_date=end_date,
        mean_daily_precipitation_mm_day=mean_daily_precip,
        total_precipitation_mm=total_precip,
        mean_daily_air_temperature_c=mean_daily_temp,
        atmospheric_recharge_deficit_score=recharge_deficit_score,
        atmospheric_thermal_load_score=thermal_load_score,
        atmospheric_hydro_thermal_load_score=atm_load_score,
        dynamic_environmental_stress=round(float(dynamic_stress), 2),
        baseline_soil_vulnerability=round(float(baseline_vuln), 2),
        indicators={
            "moisture_deficit": {"score": moist_score, "note": moist_note},
            "precipitation_deficit": {
                "raw_score": recharge_deficit_score,
                "buffering_factor": buffering_factor,
                "buffered_score": buffered_precip_score,
                "note": buffer_note,
            },
            "thermal_load": {"score": thermal_load_score, "note": thermal_note},
            "soc_vulnerability": {"score": soc_score, "note": soc_note},
            "ph_deviation": {"score": ph_score, "note": ph_note},
        },
        assumptions=assumptions,
        limitations=limitations,
        explanation=explanation,
        location_id=resolved_loc,
        date=start_date
    )

    if audit_log_path is not None:
        log_outlook_entry(
            res.to_dict(),
            source_id=f"open_meteo_forecast_{horizon_days}d",
            log_path=audit_log_path
        )

    return res


# ---------------------------------------------------------------------------
# 30-Day Hypothetical Scenario Engine
# ---------------------------------------------------------------------------

def evaluate_scenario_outlook(
    scenario_name: str = "dry_spell",
    antecedent_record: Optional[Union[Dict[str, Any], pd.Series]] = None,
    custom_daily_precipitation: Optional[float] = None,
    custom_daily_air_temperature: Optional[float] = None,
    horizon_days: int = 30,
    audit_log_path: Optional[Union[str, Path]] = None,
    location_id: Optional[str] = None
) -> OutlookResult:
    """
    Evaluate a 30-Day Hypothetical Environmental Stress Scenario.

    CRITICAL SCIENTIFIC STANDARDS:
    1. Output is formally labeled HYPOTHETICAL_SCENARIO.
    2. Prescribed meteorological conditions are synthetic assumptions for risk stress-testing.
    3. Does NOT invent scenario probabilities, occurrence frequencies, confidence percentages,
       or validation accuracy.
    4. Separates scenario outputs completely from operational forecast outputs.

    Parameters:
        scenario_name: Name of preset scenario ("dry_spell", "normal_climatology", "heavy_rainfall", or "custom").
        antecedent_record: Optional antecedent feature record.
        custom_daily_precipitation: Optional override for daily precipitation (mm/day).
        custom_daily_air_temperature: Optional override for daily 2m air temperature (C).
        horizon_days: Projection horizon in days (default: 30).
        audit_log_path: Optional path to write audit entry.
        location_id: Optional location identifier.

    Returns:
        Structured OutlookResult.
    """
    if horizon_days <= 0:
        raise ValueError(f"horizon_days must be a positive integer; received {horizon_days}.")

    # 1. Load preset or custom parameters
    if scenario_name in SCENARIO_PRESETS:
        preset = SCENARIO_PRESETS[scenario_name]
        p_rate = preset["daily_precipitation_mm_day"]
        t_air = preset["daily_mean_air_temperature_c"]
        desc = preset["description"]
        assumptions = list(preset["assumptions"])
    elif scenario_name == "custom":
        if custom_daily_precipitation is None or custom_daily_air_temperature is None:
            raise ValueError("custom scenario requires custom_daily_precipitation and custom_daily_air_temperature.")
        p_rate = float(custom_daily_precipitation)
        t_air = float(custom_daily_air_temperature)
        desc = f"Custom hypothetical scenario: {p_rate:.2f} mm/day, {t_air:.1f} C over {horizon_days} days."
        assumptions = [
            f"Prescribes {p_rate:.2f} mm/day precipitation and {t_air:.1f} C air temperature.",
            "Synthetic conditions specified directly by user.",
        ]
    else:
        raise ValueError(
            f"Unknown scenario name: '{scenario_name}'. "
            f"Supported presets: {list(SCENARIO_PRESETS.keys())} or 'custom'."
        )

    # Apply overrides if provided for presets
    if custom_daily_precipitation is not None:
        p_rate = float(custom_daily_precipitation)
        assumptions.append(f"Precipitation rate overridden to {p_rate:.2f} mm/day.")
    if custom_daily_air_temperature is not None:
        t_air = float(custom_daily_air_temperature)
        assumptions.append(f"Air temperature overridden to {t_air:.1f} C.")

    total_precip = round(p_rate * horizon_days, 2)

    # 2. Compute Atmospheric Synthetic Stress
    recharge_deficit_score, recharge_note = calculate_atmospheric_recharge_deficit_score(p_rate)
    thermal_load_score, thermal_note = calculate_atmospheric_thermal_load_score(t_air)
    atm_load_score = round(0.50 * recharge_deficit_score + 0.50 * thermal_load_score, 2)

    # 3. Check Antecedent State
    ant_status = "UNAVAILABLE"
    ant_date_str = None
    ant_age_days = None
    if antecedent_record is not None:
        rec = antecedent_record.to_dict() if isinstance(antecedent_record, pd.Series) else dict(antecedent_record)
        raw_date = rec.get("date")
        if not raw_date and "year" in rec and "month" in rec:
            raw_date = f"{rec['year']}-{int(rec['month']):02d}"
        ant_date = parse_date_safely(raw_date)
        if ant_date:
            ant_date_str = ant_date.strftime("%Y-%m-%d" if len(str(raw_date)) > 7 else "%Y-%m")
            ant_status = "STALE"  # Scenarios are forward-looking 30d projections
        if rec.get("soil_moisture_rootzone_fraction") is None:
            ant_status = "UNAVAILABLE"

    assumptions.extend([
        "This is an exploratory HYPOTHETICAL SCENARIO for risk stress-testing and resilience analysis.",
        "NO probability of occurrence, validation accuracy, or predictive confidence is assigned or claimed.",
        "Operational numerical weather predictions do NOT offer deterministic skill at a 30-day horizon.",
        "Atmospheric air temperature is NOT measured or simulated soil temperature.",
    ])

    limitations = [
        "Synthetic hypothetical scenario only. Not an empirical weather forecast.",
        "Assumes static meteorological rates across the 30-day window.",
        "Subsurface hydrology, evapotranspiration feedback, and irrigation dynamics are not simulated.",
    ]

    explanation = (
        f"SoilSentinel 30-Day HYPOTHETICAL SCENARIO [{scenario_name}]: {desc} "
        f"Assumed rain rate = {p_rate:.2f} mm/day (total = {total_precip:.1f} mm), "
        f"assumed air temp = {t_air:.1f} C. "
        f"Atmospheric recharge deficit = {recharge_deficit_score:.1f}/100, "
        f"atmospheric thermal load = {thermal_load_score:.1f}/100, "
        f"composite atmospheric load = {atm_load_score:.1f}/100. "
        "Strictly exploratory stress-test; no predictive probability claimed."
    )

    resolved_loc = location_id or "Indo-Gangetic Agricultural Plains / Punjab"

    res = OutlookResult(
        index_name=OUTLOOK_INDEX_NAME,
        outlook_type=SCENARIO_LABEL,
        status=SCENARIO_LABEL,
        score=atm_load_score,
        risk_category=SCENARIO_LABEL,
        antecedent_status=ant_status,
        antecedent_date=ant_date_str,
        antecedent_age_days=ant_age_days,
        forecast_source="HYPOTHETICAL_SCENARIO_ENGINE",
        forecast_horizon_days=horizon_days,
        forecast_start_date=None,
        forecast_end_date=None,
        mean_daily_precipitation_mm_day=p_rate,
        total_precipitation_mm=total_precip,
        mean_daily_air_temperature_c=t_air,
        atmospheric_recharge_deficit_score=recharge_deficit_score,
        atmospheric_thermal_load_score=thermal_load_score,
        atmospheric_hydro_thermal_load_score=atm_load_score,
        dynamic_environmental_stress=None,
        baseline_soil_vulnerability=None,
        indicators={
            "scenario_name": scenario_name,
            "prescribed_precipitation_mm_day": p_rate,
            "prescribed_air_temperature_c": t_air,
            "atmospheric_recharge_deficit": {"score": recharge_deficit_score, "note": recharge_note},
            "atmospheric_thermal_load": {"score": thermal_load_score, "note": thermal_note},
        },
        assumptions=assumptions,
        limitations=limitations,
        explanation=explanation,
        scenario_label=SCENARIO_LABEL,
        scenario_name=scenario_name,
        location_id=resolved_loc,
        date=scenario_name
    )

    if audit_log_path is not None:
        log_outlook_entry(
            res.to_dict(),
            source_id=f"hypothetical_scenario_{scenario_name}_{horizon_days}d",
            log_path=audit_log_path
        )

    return res


# ---------------------------------------------------------------------------
# Command-Line Interface
# ---------------------------------------------------------------------------

def main():
    """Command-line interface for the SoilSentinel Outlook & Scenario Engine."""
    parser = argparse.ArgumentParser(
        description="SoilSentinel - Member 2: Weather Forecast Outlook & Hypothetical Scenario Engine"
    )
    parser.add_argument(
        "--lat",
        type=float,
        default=30.7333,
        help="Target latitude in decimal degrees (default: 30.7333 / Chandigarh region)"
    )
    parser.add_argument(
        "--lon",
        type=float,
        default=76.7794,
        help="Target longitude in decimal degrees (default: 76.7794 / Chandigarh region)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_FORECAST_DAYS,
        choices=[7, 14],
        help="Forecast horizon days (7 or 14, default: 7)"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        choices=["dry_spell", "normal_climatology", "heavy_rainfall"],
        help="Run a 30-day hypothetical scenario instead of live forecast API"
    )
    parser.add_argument(
        "--antecedent-csv",
        type=str,
        default="data/feature_table.csv",
        help="Path to feature table containing historical antecedent records (default: data/feature_table.csv)"
    )
    parser.add_argument(
        "--audit-log",
        type=str,
        default=DEFAULT_AUDIT_LOG_PATH,
        help=f"Path to append audit entry (default: {DEFAULT_AUDIT_LOG_PATH})"
    )
    parser.add_argument(
        "--no-audit",
        action="store_true",
        help="Disable audit logging"
    )

    args = parser.parse_args()
    audit_path = None if args.no_audit else args.audit_log

    # Load antecedent record if file exists
    antecedent_rec = None
    if args.antecedent_csv and Path(args.antecedent_csv).exists():
        try:
            df = pd.read_csv(args.antecedent_csv)
            if not df.empty:
                antecedent_rec = df.iloc[-1].to_dict()
        except Exception as e:
            logger.warning("Could not read antecedent CSV: %s", e)

    print("=====================================================================")
    print("SoilSentinel - Member 2: Environmental Risk Outlook Engine")
    print("=====================================================================")

    if args.scenario:
        print(f"Mode: 30-Day Hypothetical Scenario ({args.scenario})")
        res = evaluate_scenario_outlook(
            scenario_name=args.scenario,
            antecedent_record=antecedent_rec,
            audit_log_path=audit_path
        )
    else:
        print(f"Mode: Operational Open-Meteo Weather Forecast ({args.days}-day horizon)")
        print(f"Coordinates: {args.lat} N, {args.lon} E")
        forecast_res = fetch_weather_forecast(lat=args.lat, lon=args.lon, days=args.days)
        res = evaluate_forecast_outlook(
            forecast=forecast_res,
            antecedent_record=antecedent_rec,
            audit_log_path=audit_path
        )

    print(f"\nIndex Name:         {res.index_name}")
    print(f"Outlook Type:       {res.outlook_type}")
    print(f"Status:             {res.status}")
    print(f"Antecedent Status:  {res.antecedent_status} (Observation: {res.antecedent_date}, Age: {res.antecedent_age_days} days)")
    if res.score is not None:
        print(f"Score:              {res.score:.2f}/100")
        print(f"Risk Category:      {res.risk_category}")
    else:
        print("Score:              None (Combined soil state withheld due to stale/missing data)")
        print(f"Risk Category:      {res.risk_category}")

    print(f"\nAtmospheric Forcing Metrics:")
    print(f"  Mean Daily Rain:  {res.mean_daily_precipitation_mm_day} mm/day (Total: {res.total_precipitation_mm} mm)")
    print(f"  Mean 2m Air Temp: {res.mean_daily_air_temperature_c} C")
    print(f"  Recharge Deficit: {res.atmospheric_recharge_deficit_score}/100")
    print(f"  Thermal Load:     {res.atmospheric_thermal_load_score}/100")
    print(f"  Composite Load:   {res.atmospheric_hydro_thermal_load_score}/100")

    print(f"\nExplanation:\n  {res.explanation}")
    print("\nAssumptions:")
    for a in res.assumptions:
        print(f"  - {a}")
    print("=====================================================================")


if __name__ == "__main__":
    main()
