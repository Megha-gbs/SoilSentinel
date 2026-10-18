"""
SoilSentinel - Multi-District NASA POWER Climate Data Acquisition across Punjab.

Acquires monthly meteorological and hydrological covariates (2020-01 to 2024-12)
for representative agricultural districts across all agro-climatic zones of Punjab:
1. Central Plain Zone (Ludhiana, Jalandhar, Patiala, SAS Nagar)
2. South-Western Semi-Arid Zone (Bathinda)
3. Western Plain Zone (Amritsar)
4. Sub-Mountainous Kandi Zone (Hoshiarpur)

Parameters:
- T2M: Air Temperature at 2m (C)
- RH2M: Relative Humidity at 2m (%)
- PRECTOTCORR: Precipitation Corrected (mm/day)
- GWETTOP: Surface Soil Wetness fraction (0-1)
- GWETROOT: Root-zone Soil Wetness fraction (0-1)
- TSOIL1: Topsoil Temperature (0-10cm) (C)

Official API: https://power.larc.nasa.gov/api/temporal/monthly/point
"""

import hashlib
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any, Dict
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_CLIMATE_DIR = PROJECT_ROOT / "data" / "raw" / "climate"
LOGS_DIR = PROJECT_ROOT / "data" / "logs"

RAW_CLIMATE_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging
log_file = LOGS_DIR / "climate_acquisition.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("climate_acquisition")

NASA_POWER_BASE = "https://power.larc.nasa.gov/api/temporal/monthly/point"
PARAMETERS = "T2M,RH2M,PRECTOTCORR,GWETTOP,GWETROOT,TSOIL1"
COMMUNITY = "AG"
START_YEAR = 2020
END_YEAR = 2024

PUNJAB_DISTRICTS = [
    {
        "district_id": "sas_nagar_chandigarh",
        "district_name": "SAS Nagar / Mohali (Baseline Parcel)",
        "zone": "Eastern Plain / Foothill Margin",
        "latitude": 30.73,
        "longitude": 76.77,
    },
    {
        "district_id": "ludhiana",
        "district_name": "Ludhiana (Central Agricultural Hub)",
        "zone": "Central Plain Zone",
        "latitude": 30.90,
        "longitude": 75.85,
    },
    {
        "district_id": "bathinda",
        "district_name": "Bathinda (Cotton / Semi-Arid / Saline Belt)",
        "zone": "South-Western Semi-Arid Zone",
        "latitude": 30.21,
        "longitude": 74.95,
    },
    {
        "district_id": "jalandhar",
        "district_name": "Jalandhar (Doaba Cereal / Vegetable Belt)",
        "zone": "Central Plain Zone",
        "latitude": 31.33,
        "longitude": 75.58,
    },
    {
        "district_id": "patiala",
        "district_name": "Patiala (Southern Intensive Plain)",
        "zone": "Central Plain Zone",
        "latitude": 30.34,
        "longitude": 76.38,
    },
    {
        "district_id": "amritsar",
        "district_name": "Amritsar (Western Plain / Border Belt)",
        "zone": "Western Plain Zone",
        "latitude": 31.63,
        "longitude": 74.87,
    },
    {
        "district_id": "hoshiarpur",
        "district_name": "Hoshiarpur (Sub-Mountainous Kandi / Erosion Belt)",
        "zone": "Sub-Mountainous Undulating Kandi Zone",
        "latitude": 31.53,
        "longitude": 75.92,
    },
]


def compute_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def fetch_district_climate(district: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
    dist_id = district["district_id"]
    lat = district["latitude"]
    lon = district["longitude"]
    filename = f"nasa_power_monthly_{START_YEAR}_{END_YEAR}_{lat:.2f}_{lon:.2f}_{dist_id}.json"
    filepath = RAW_CLIMATE_DIR / filename

    # Check if existing raw file exists and is valid
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                cached = json.load(f)
            params = cached.get("properties", {}).get("parameter", {})
            if len(params) >= 6:
                logger.info(f"Using cached valid climate data for {dist_id} at {filepath.name}")
                return {
                    "district": district,
                    "filepath": str(filepath.relative_to(PROJECT_ROOT)),
                    "sha256": compute_sha256(filepath),
                    "size_bytes": filepath.stat().st_size,
                    "status": "CACHED_VALID",
                }
        except Exception:
            pass

    # If original baseline file exists without district suffix, check that
    baseline_filename = f"nasa_power_monthly_{START_YEAR}_{END_YEAR}_{lat}_{lon}.json"
    baseline_filepath = RAW_CLIMATE_DIR / baseline_filename
    if baseline_filepath.exists():
        try:
            with open(baseline_filepath, "r", encoding="utf-8") as f:
                cached = json.load(f)
            params = cached.get("properties", {}).get("parameter", {})
            if len(params) >= 6:
                logger.info(f"Using existing project baseline file for {dist_id}: {baseline_filename}")
                return {
                    "district": district,
                    "filepath": str(baseline_filepath.relative_to(PROJECT_ROOT)),
                    "sha256": compute_sha256(baseline_filepath),
                    "size_bytes": baseline_filepath.stat().st_size,
                    "status": "BASELINE_REUSED",
                }
        except Exception:
            pass

    query_params = {
        "parameters": PARAMETERS,
        "community": COMMUNITY,
        "longitude": lon,
        "latitude": lat,
        "start": str(START_YEAR),
        "end": str(END_YEAR),
        "format": "JSON",
    }

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Requesting NASA POWER for {dist_id} ({lat}, {lon}) (attempt {attempt}/{max_retries})...")
            resp = requests.get(NASA_POWER_BASE, params=query_params, timeout=35)
            if resp.status_code == 200:
                data = resp.json()
                if "properties" in data and "parameter" in data["properties"]:
                    tmp_path = filepath.with_suffix(".tmp")
                    with open(tmp_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    tmp_path.replace(filepath)
                    sha256 = compute_sha256(filepath)
                    logger.info(f"Saved {filepath.name} ({filepath.stat().st_size} bytes)")
                    return {
                        "district": district,
                        "filepath": str(filepath.relative_to(PROJECT_ROOT)),
                        "sha256": sha256,
                        "size_bytes": filepath.stat().st_size,
                        "status": "DOWNLOADED_SUCCESS",
                    }
                else:
                    logger.warning(f"Response missing parameter block for {dist_id}")
            else:
                logger.warning(f"HTTP {resp.status_code} for {dist_id}: {resp.text[:150]}")
        except Exception as e:
            logger.warning(f"Error fetching {dist_id}: {e}")

        if attempt < max_retries:
            time.sleep(2.0 * attempt)

    return {
        "district": district,
        "status": "FAILED",
    }


def acquire_all_district_climates() -> Dict[str, Any]:
    logger.info("=== Starting Multi-District NASA POWER Acquisition across Punjab ===")
    results = {}
    for dist in PUNJAB_DISTRICTS:
        res = fetch_district_climate(dist)
        results[dist["district_id"]] = res
        time.sleep(1.0)  # Gentle spacing between API calls
    logger.info("=== Multi-District NASA POWER Acquisition Finished ===")
    return results


if __name__ == "__main__":
    res = acquire_all_district_climates()
    print(json.dumps(res, indent=2))
