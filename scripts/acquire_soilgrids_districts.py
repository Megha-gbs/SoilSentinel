"""
SoilSentinel - High-Efficiency Multi-District SoilGrids v2.0 Extraction.

Batches requests across 15 official VRT files (5 properties x 3 depths):
- phh2o: pH in H2O solution (raw_dn / 10 = standard pH)
- clay: Clay mass fraction (raw_dn / 10 = %)
- sand: Sand mass fraction (raw_dn / 10 = %)
- silt: Silt mass fraction (raw_dn / 10 = %)
- soc: Soil Organic Carbon (raw_dn / 10 = g/kg)

Depths: 0-5cm, 5-15cm, 15-30cm.
Optimized: Opens each remote VRT exactly ONCE and reads a single buffered bounding window per district.
Nearest agricultural soil pixel resolved entirely in-memory without iterative network roundtrips.

Saves raw metadata to data/raw/soil/soilgrids_punjab_districts_metadata.json.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List
import rasterio
from rasterio.warp import transform
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_SOIL_DIR = PROJECT_ROOT / "data" / "raw" / "soil"
LOGS_DIR = PROJECT_ROOT / "data" / "logs"

RAW_SOIL_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging
log_file = LOGS_DIR / "soilgrids_acquisition.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("soilgrids_acquisition")

VRT_BASE = "https://files.isric.org/soilgrids/latest/data"

PROPERTIES = {
    "ph": "phh2o",
    "clay": "clay",
    "sand": "sand",
    "silt": "silt",
    "soc": "soc",
}

DEPTHS = ["0-5cm", "5-15cm", "15-30cm"]

SCALE_FACTORS = {
    "phh2o": 0.1,    # pH units
    "clay": 0.1,     # %
    "sand": 0.1,     # %
    "silt": 0.1,     # %
    "soc": 0.1,      # g/kg
}

PUNJAB_DISTRICTS = [
    {
        "district_id": "sas_nagar_chandigarh",
        "district_name": "SAS Nagar / Mohali (Baseline Parcel)",
        "latitude": 30.73,
        "longitude": 76.77,
    },
    {
        "district_id": "ludhiana",
        "district_name": "Ludhiana (Central Agricultural Hub)",
        "latitude": 30.90,
        "longitude": 75.85,
    },
    {
        "district_id": "bathinda",
        "district_name": "Bathinda (Cotton / Semi-Arid / Saline Belt)",
        "latitude": 30.21,
        "longitude": 74.95,
    },
    {
        "district_id": "jalandhar",
        "district_name": "Jalandhar (Doaba Cereal / Vegetable Belt)",
        "latitude": 31.33,
        "longitude": 75.58,
    },
    {
        "district_id": "patiala",
        "district_name": "Patiala (Southern Intensive Plain)",
        "latitude": 30.34,
        "longitude": 76.38,
    },
    {
        "district_id": "amritsar",
        "district_name": "Amritsar (Western Plain / Border Belt)",
        "latitude": 31.63,
        "longitude": 74.87,
    },
    {
        "district_id": "hoshiarpur",
        "district_name": "Hoshiarpur (Sub-Mountainous Kandi / Erosion Belt)",
        "latitude": 31.53,
        "longitude": 75.92,
    },
]


def extract_batch_soilgrids() -> Dict[str, Any]:
    out_file = RAW_SOIL_DIR / "soilgrids_punjab_districts_metadata.json"
    logger.info("=== Starting High-Efficiency Multi-District SoilGrids v2.0 Extraction ===")

    # Initialize container for each district
    district_data = {
        d["district_id"]: {
            "district_name": d["district_name"],
            "nominal_latitude": d["latitude"],
            "nominal_longitude": d["longitude"],
            "properties": {},
            "records": [],
        }
        for d in PUNJAB_DISTRICTS
    }

    # Iterate through the 15 VRT files
    total_vrts = len(PROPERTIES) * len(DEPTHS)
    vrt_idx = 0

    for prop_alias, code in PROPERTIES.items():
        for depth in DEPTHS:
            vrt_idx += 1
            vrt_url = f"{VRT_BASE}/{code}/{code}_{depth}_mean.vrt"
            logger.info(f"[{vrt_idx}/{total_vrts}] Querying {code} ({depth}) across 7 districts...")

            try:
                with rasterio.open(vrt_url) as src:
                    nodata_val = src.nodata if src.nodata is not None else -32768
                    crs = src.crs

                    for d in PUNJAB_DISTRICTS:
                        dist_id = d["district_id"]
                        lat = d["latitude"]
                        lon = d["longitude"]

                        # Reproject WGS84 to dataset Goode Homolosine
                        xs, ys = transform("EPSG:4326", crs, [lon], [lat])
                        center_row, center_col = src.index(xs[0], ys[0])

                        # Read a single buffered window of 25x25 pixels (6.25 km x 6.25 km)
                        rad = 12
                        win = rasterio.windows.Window(center_col - rad, center_row - rad, 2 * rad + 1, 2 * rad + 1)
                        win_data = src.read(1, window=win)

                        # Check center pixel
                        center_pixel = win_data[rad, rad]
                        if center_pixel != nodata_val:
                            found_dn = float(center_pixel)
                            s_lat, s_lon = lat, lon
                            dist_km = 0.0
                        else:
                            # In-memory search for nearest valid pixel
                            valid_coords = np.argwhere(win_data != nodata_val)
                            if len(valid_coords) > 0:
                                dists = [((r - rad)**2 + (c - rad)**2, r, c) for r, c in valid_coords]
                                dists.sort()
                                _, best_r, best_c = dists[0]
                                found_dn = float(win_data[best_r, best_c])
                                tr = center_row - rad + best_r
                                tc = center_col - rad + best_c
                                tx, ty = src.xy(tr, tc)
                                tlons, tlats = transform(crs, "EPSG:4326", [tx], [ty])
                                s_lat, s_lon = float(tlats[0]), float(tlons[0])
                                dist_km = round(np.sqrt((best_r - rad)**2 + (best_c - rad)**2) * 0.25, 2)
                            else:
                                found_dn = np.nan
                                s_lat, s_lon = lat, lon
                                dist_km = np.nan

                        physical_val = found_dn * SCALE_FACTORS[code] if np.isfinite(found_dn) else np.nan
                        key = f"{prop_alias}_{depth.replace('-', '_')}"

                        rec = {
                            "property": prop_alias,
                            "code": code,
                            "depth": depth,
                            "raw_dn": found_dn,
                            "physical_value": round(float(physical_val), 2) if np.isfinite(physical_val) else None,
                            "unit": "pH" if code == "phh2o" else ("g/kg" if code == "soc" else "%"),
                            "nominal_lat": lat,
                            "nominal_lon": lon,
                            "sampled_lat": round(s_lat, 4),
                            "sampled_lon": round(s_lon, 4),
                            "adjustment_distance_km": dist_km,
                        }
                        district_data[dist_id]["records"].append(rec)
                        district_data[dist_id]["properties"][key] = rec["physical_value"]

            except Exception as e:
                logger.error(f"Error reading VRT {vrt_url}: {e}")

    # Build final serializable structure
    payload = {
        "source": "ISRIC SoilGrids v2.0 (Official Global 250m VRT File Service)",
        "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
        "region": "Punjab Agro-Climatic Zones, India",
        "districts_count": len(district_data),
        "districts": district_data,
    }

    tmp_path = out_file.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    tmp_path.replace(out_file)

    hasher = hashlib.sha256()
    with open(out_file, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    sha256 = hasher.hexdigest()

    logger.info(f"Saved {out_file.name} ({out_file.stat().st_size} bytes, sha256={sha256})")
    return {
        "status": "SUCCESS",
        "filepath": str(out_file.relative_to(PROJECT_ROOT)),
        "size_bytes": out_file.stat().st_size,
        "sha256": sha256,
        "districts": list(district_data.keys()),
    }


if __name__ == "__main__":
    res = extract_batch_soilgrids()
    print(json.dumps(res, indent=2))
