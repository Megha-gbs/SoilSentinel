"""
NASA POWER Climate and Soil Environmental Data Collection Module.

Collects monthly climate and soil environmental indicators:
- Air Temperature at 2 Meters (T2M)
- Air Relative Humidity at 2 Meters (RH2M)
- Precipitation Corrected (PRECTOTCORR)
- Surface Soil Wetness / Moisture (GWETTOP)
- Root Zone Soil Wetness / Moisture (GWETROOT)
- Soil Temperature Layer 1 (0-10cm) (TSOIL1)

from the official NASA POWER (Prediction of Worldwide Energy Resources) API.
API Reference: https://power.larc.nasa.gov/
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional

import requests
import numpy as np
import pandas as pd
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("nasa_power_collector")


def load_config(config_path: str = "config/settings.yaml") -> Dict[str, Any]:
    """Load project settings from YAML file."""
    path = Path(config_path)
    if not path.is_absolute():
        project_root = Path(__file__).resolve().parent.parent.parent
        path = project_root / config_path
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class NasaPowerCollector:
    """Automates climate and soil environmental data extraction from NASA POWER API."""

    DEFAULT_PARAMETERS = ["T2M", "RH2M", "PRECTOTCORR", "GWETTOP", "GWETROOT", "TSOIL1"]

    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config = load_config(config_path)
        self.study_region = self.config["study_region"]
        self.climate_cfg = self.config["climate"]
        self.pipeline_cfg = self.config.get("pipeline", {})

        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.raw_dir = self.project_root / self.climate_cfg.get("raw_output_dir", "data/raw/climate")
        self.processed_file = self.project_root / self.climate_cfg.get("processed_output_path", "data/processed/climate_data.csv")

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_file.parent.mkdir(parents=True, exist_ok=True)

    def fetch_climate_data(self, force: bool = False) -> Dict[str, Any]:
        """
        Request monthly climate and soil environmental data from NASA POWER API with retries.
        Saves original JSON response to data/raw/climate/.
        """
        start_year = self.study_region["start_year"]
        end_year = self.study_region["end_year"]
        lat = self.study_region["latitude"]
        lon = self.study_region["longitude"]

        raw_filename = f"nasa_power_monthly_{start_year}_{end_year}_{lat}_{lon}.json"
        raw_filepath = self.raw_dir / raw_filename

        base_url = self.climate_cfg.get("api_base_url", "https://power.larc.nasa.gov/api/temporal/monthly/point")
        param_list = self.climate_cfg.get("parameters", self.DEFAULT_PARAMETERS)
        parameters = ",".join(param_list)
        community = self.climate_cfg.get("community", "AG")

        # Check existing cache: only reuse if all required parameters are present in cached response
        if raw_filepath.exists() and not force:
            with open(raw_filepath, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            cached_params = set(cached_data.get("properties", {}).get("parameter", {}).keys())
            required_params = set(param_list)
            if required_params.issubset(cached_params):
                logger.info("Using cached raw NASA POWER response from %s (all %d parameters present).",
                            raw_filepath, len(required_params))
                return cached_data
            else:
                missing_in_cache = required_params - cached_params
                logger.info("Cached raw NASA POWER response missing parameters %s. Fetching fresh payload...",
                            missing_in_cache)

        params = {
            "parameters": parameters,
            "community": community,
            "longitude": lon,
            "latitude": lat,
            "start": str(start_year),
            "end": str(end_year),
            "format": "JSON"
        }

        max_retries = self.pipeline_cfg.get("retry_attempts", 3)
        backoff_factor = self.pipeline_cfg.get("retry_backoff_factor", 2.0)
        timeout = self.pipeline_cfg.get("timeout_seconds", 30)

        logger.info("Requesting NASA POWER data for lat=%.4f, lon=%.4f (%s-%s)...", lat, lon, start_year, end_year)
        logger.info("Parameters: %s", parameters)
        logger.info("Endpoint  : %s", base_url)

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(base_url, params=params, timeout=timeout)
                if response.status_code == 200:
                    data = response.json()
                    # Validate basic payload structure
                    if "properties" not in data or "parameter" not in data["properties"]:
                        raise ValueError("NASA POWER response missing 'properties.parameter' object.")

                    # Save original raw API response
                    with open(raw_filepath, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    logger.info("Successfully fetched and saved raw response to %s", raw_filepath)
                    return data
                elif response.status_code in [429, 500, 502, 503, 504]:
                    logger.warning("NASA POWER server returned %d (Attempt %d/%d). Retrying...",
                                   response.status_code, attempt, max_retries)
                else:
                    raise requests.HTTPError(f"HTTP {response.status_code}: {response.text[:200]}")
            except (requests.RequestException, ValueError) as err:
                last_error = err
                logger.warning("Network/Request error on attempt %d/%d: %s", attempt, max_retries, err)

            if attempt < max_retries:
                sleep_sec = backoff_factor ** attempt
                logger.info("Sleeping %.1f seconds before retry...", sleep_sec)
                time.sleep(sleep_sec)

        raise RuntimeError(f"Failed to fetch data from NASA POWER API after {max_retries} attempts: {last_error}")

    def process_and_validate(self, raw_data: Dict[str, Any]) -> pd.DataFrame:
        """
        Parse raw NASA POWER JSON, extract air and soil environmental parameters,
        handle NASA missing fill values (-999.0), validate physical bounds,
        and output structured DataFrame with explicit column naming.
        """
        region_name = self.study_region["name"]
        lat = self.study_region["latitude"]
        lon = self.study_region["longitude"]

        params = raw_data.get("properties", {}).get("parameter", {})
        param_metadata = raw_data.get("parameters", {})

        # Primary climate parameters
        t2m_dict = params.get("T2M", {})
        rh2m_dict = params.get("RH2M", {})
        prec_dict = params.get("PRECTOTCORR", {})

        # Soil moisture and soil temperature parameters
        gwettop_dict = params.get("GWETTOP", {})
        gwetroot_dict = params.get("GWETROOT", {})
        tsoil1_dict = params.get("TSOIL1", {})

        if not t2m_dict or not rh2m_dict or not prec_dict:
            raise ValueError("Core climate parameters (T2M, RH2M, PRECTOTCORR) missing from NASA POWER response.")

        # Find all keys shared across available parameters
        all_keys = sorted(t2m_dict.keys())
        records = []
        missing_counts = {
            "T2M": 0, "RH2M": 0, "PRECTOTCORR": 0,
            "GWETTOP": 0, "GWETROOT": 0, "TSOIL1": 0
        }

        def parse_val(val_dict: Dict[str, Any], date_key: str, param_name: str) -> Optional[float]:
            """Extract value handling NASA -999 missing-value convention."""
            raw_v = val_dict.get(date_key)
            if raw_v is None or raw_v == -999.0 or raw_v == -999:
                missing_counts[param_name] += 1
                return None
            return float(raw_v)

        for key in all_keys:
            # NASA POWER keys for monthly data are in format YYYYMM (e.g., 202001 .. 202012)
            # YYYY13 represents the annual summary, exclude from monthly time-series
            if len(key) == 6:
                year_str = key[:4]
                month_str = key[4:]
                if month_str == "13":
                    continue

                year = int(year_str)
                month = int(month_str)
                date_str = f"{year_str}-{month_str}"

                t2m = parse_val(t2m_dict, key, "T2M")
                rh2m = parse_val(rh2m_dict, key, "RH2M")
                prec = parse_val(prec_dict, key, "PRECTOTCORR")
                gwettop = parse_val(gwettop_dict, key, "GWETTOP")
                gwetroot = parse_val(gwetroot_dict, key, "GWETROOT")
                tsoil1 = parse_val(tsoil1_dict, key, "TSOIL1")

                # Physical bounds validation
                if t2m is not None and not (-50.0 <= t2m <= 60.0):
                    raise ValueError(f"Air temperature out of physical bounds [-50, 60] C: {t2m} on {date_str}")
                if rh2m is not None and not (0.0 <= rh2m <= 100.0):
                    raise ValueError(f"Air relative humidity out of bounds [0, 100] %: {rh2m} on {date_str}")
                if prec is not None and prec < 0.0:
                    raise ValueError(f"Precipitation cannot be negative: {prec} mm/day on {date_str}")
                if tsoil1 is not None and not (-50.0 <= tsoil1 <= 60.0):
                    raise ValueError(f"Soil temperature layer 1 out of bounds [-50, 60] C: {tsoil1} on {date_str}")
                if gwettop is not None and not (0.0 <= gwettop <= 1.0):
                    raise ValueError(f"Surface soil wetness out of bounds [0, 1]: {gwettop} on {date_str}")
                if gwetroot is not None and not (0.0 <= gwetroot <= 1.0):
                    raise ValueError(f"Root zone soil wetness out of bounds [0, 1]: {gwetroot} on {date_str}")

                records.append({
                    "region": region_name,
                    "latitude": lat,
                    "longitude": lon,
                    "year": year,
                    "month": month,
                    "date": date_str,
                    # Air Climate Observations
                    "air_temperature_c": round(t2m, 2) if t2m is not None else np.nan,
                    "temperature_c": round(t2m, 2) if t2m is not None else np.nan,  # Backward compatibility
                    "air_humidity_percent": round(rh2m, 2) if rh2m is not None else np.nan,
                    "humidity_percent": round(rh2m, 2) if rh2m is not None else np.nan,  # Backward compatibility
                    "precipitation_mm_day": round(prec, 2) if prec is not None else np.nan,
                    # Soil Environmental Observations
                    "soil_temperature_layer1_c": round(tsoil1, 2) if tsoil1 is not None else np.nan,
                    "soil_moisture_surface_fraction": round(gwettop, 4) if gwettop is not None else np.nan,
                    "soil_moisture_rootzone_fraction": round(gwetroot, 4) if gwetroot is not None else np.nan,
                    # Source Attribution
                    "data_source": "NASA POWER AG Community"
                })

        df = pd.DataFrame(records)
        if df.empty:
            raise ValueError("Processed climate dataset is empty after validation!")

        logger.info("Successfully validated %d monthly environmental records (%s to %s).",
                    len(df), df["date"].min(), df["date"].max())
        logger.info("Missing value counts (NASA -999 convention): %s", missing_counts)
        return df

    def run(self, force: bool = False) -> pd.DataFrame:
        """Execute full climate data collection and processing pipeline."""
        logger.info("--- Starting NASA POWER Environmental Data Collection ---")
        raw_data = self.fetch_climate_data(force=force)
        df = self.process_and_validate(raw_data)
        df.to_csv(self.processed_file, index=False)
        logger.info("Validated environmental dataset written to: %s", self.processed_file)
        logger.info("--- NASA POWER Collection Completed Successfully ---")
        return df


if __name__ == "__main__":
    collector = NasaPowerCollector()
    df_climate = collector.run(force=True)
    print("\nEnvironmental Dataset Preview:")
    print(df_climate.head(10))
    print(f"\nTotal Rows: {len(df_climate)}")
    print(f"Columns: {list(df_climate.columns)}")
