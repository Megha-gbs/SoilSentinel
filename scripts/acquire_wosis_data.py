"""
SoilSentinel - Automated ISRIC WoSIS (World Soil Information Service) Data Acquisition.

Queries the official OGC-compliant Web Feature Service (WFS) API hosted by ISRIC:
https://maps.isric.org/mapserv?map=/map/wosis_latest.map

Acquires standardized, measured physical and chemical soil profile data:
- Soil profiles (locations, taxonomy, sampling year)
- Soil Organic Carbon (orgc)
- Soil pH in H2O (phaq)
- Soil Texture fractions: Clay, Sand, Silt
- Bulk Density (bdfiod)

for the Northwest India / Punjab / Indo-Gangetic study domain and national context.
Saves raw GeoJSON responses into data/raw/wosis/ and logs to data/logs/.
"""

import hashlib
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_WOSIS_DIR = PROJECT_ROOT / "data" / "raw" / "wosis"
LOGS_DIR = PROJECT_ROOT / "data" / "logs"

RAW_WOSIS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging
log_file = LOGS_DIR / "wosis_acquisition.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("wosis_acquisition")

WOSIS_WFS_URL = "https://maps.isric.org/mapserv?map=/map/wosis_latest.map"

# Spatial bounding boxes: minlon, minlat, maxlon, maxlat
PUNJAB_BBOX = "28.0,72.0,33.5,78.5"
INDIA_BBOX = "6.0,68.0,37.0,97.5"


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def fetch_wfs_layer(
    layer_name: str,
    bbox: str,
    max_features: int = 1000,
    max_retries: int = 3,
    timeout: int = 45,
) -> Optional[Dict[str, Any]]:
    """
    Fetch a layer from WoSIS WFS API as GeoJSON with retry logic.
    """
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": layer_name,
        "BBOX": bbox,
        "COUNT": max_features,
        "OUTPUTFORMAT": "geojson",
    }

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                f"Requesting {layer_name} (BBOX={bbox}, max={max_features}, attempt {attempt}/{max_retries})..."
            )
            resp = requests.get(WOSIS_WFS_URL, params=params, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                features = data.get("features", [])
                logger.info(f"Successfully retrieved {len(features)} features for {layer_name}")
                return data
            else:
                logger.warning(f"HTTP {resp.status_code} on attempt {attempt}: {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"Error on attempt {attempt} for {layer_name}: {e}")

        if attempt < max_retries:
            time.sleep(2.0 * attempt)

    logger.error(f"Failed to fetch {layer_name} after {max_retries} attempts.")
    return None


def acquire_wosis_dataset() -> Dict[str, Any]:
    """
    Execute full WoSIS acquisition suite.
    """
    logger.info("=== Starting ISRIC WoSIS Data Acquisition ===")
    results = {}

    targets = [
        {
            "layer": "ms:wosis_latest_profiles",
            "bbox": PUNJAB_BBOX,
            "filename": "wosis_profiles_punjab_bbox.geojson",
            "count": 500,
            "desc": "Soil profile sites in Northwest India / Punjab agricultural basin",
        },
        {
            "layer": "ms:wosis_latest_profiles",
            "bbox": INDIA_BBOX,
            "filename": "wosis_profiles_india.geojson",
            "count": 2000,
            "desc": "National benchmark soil profile sites across India",
        },
        {
            "layer": "ms:wosis_latest_orgc",
            "bbox": PUNJAB_BBOX,
            "filename": "wosis_orgc_punjab_bbox.geojson",
            "count": 1000,
            "desc": "Measured soil organic carbon observations across depth horizons (Punjab BBOX)",
        },
        {
            "layer": "ms:wosis_latest_phaq",
            "bbox": PUNJAB_BBOX,
            "filename": "wosis_phaq_punjab_bbox.geojson",
            "count": 1000,
            "desc": "Measured soil pH (in H2O) observations across depth horizons (Punjab BBOX)",
        },
        {
            "layer": "ms:wosis_latest_clay",
            "bbox": PUNJAB_BBOX,
            "filename": "wosis_clay_punjab_bbox.geojson",
            "count": 1000,
            "desc": "Measured clay mass fraction observations across depth horizons (Punjab BBOX)",
        },
        {
            "layer": "ms:wosis_latest_sand",
            "bbox": PUNJAB_BBOX,
            "filename": "wosis_sand_punjab_bbox.geojson",
            "count": 1000,
            "desc": "Measured sand mass fraction observations across depth horizons (Punjab BBOX)",
        },
        {
            "layer": "ms:wosis_latest_silt",
            "bbox": PUNJAB_BBOX,
            "filename": "wosis_silt_punjab_bbox.geojson",
            "count": 1000,
            "desc": "Measured silt mass fraction observations across depth horizons (Punjab BBOX)",
        },
    ]

    for t in targets:
        out_path = RAW_WOSIS_DIR / t["filename"]
        geojson_data = fetch_wfs_layer(
            layer_name=t["layer"],
            bbox=t["bbox"],
            max_features=t["count"],
        )

        if geojson_data is not None:
            features = geojson_data.get("features", [])
            # Save atomic
            tmp_path = out_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(geojson_data, f, indent=2)
            tmp_path.replace(out_path)

            sha256 = compute_sha256(out_path)
            size_bytes = out_path.stat().st_size
            results[t["filename"]] = {
                "status": "SUCCESS",
                "layer": t["layer"],
                "features_count": len(features),
                "file_path": str(out_path.relative_to(PROJECT_ROOT)),
                "size_bytes": size_bytes,
                "sha256": sha256,
                "description": t["desc"],
            }
            logger.info(
                f"Saved {t['filename']}: {len(features)} records, {size_bytes} bytes, sha256={sha256[:12]}..."
            )
        else:
            results[t["filename"]] = {
                "status": "FAILED",
                "layer": t["layer"],
                "description": t["desc"],
            }

    logger.info("=== WoSIS Acquisition Complete ===")
    return results


if __name__ == "__main__":
    res = acquire_wosis_dataset()
    print(json.dumps(res, indent=2))
