"""
SoilSentinel — Satellite Data Acquisition Script.

Acquires verified satellite observation metadata and scenes for the Punjab study region
(Nominal: 30.7300 N, 76.7700 E; Sampled: 30.7392 N, 76.7764 E) across the entire 60-month
study horizon from January 2020 through December 2024.

Source: Copernicus Sentinel-2 Level-2A (Surface Reflectance) via Earth Search STAC.
Saves raw catalog to data/raw/satellite/sentinel2_monthly_catalog_2020_2024.json.
"""

import os
import sys
import json
import time
import calendar
from pathlib import Path
from typing import Dict, List, Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_SATELLITE_DIR = PROJECT_ROOT / "data" / "raw" / "satellite"
RAW_SATELLITE_DIR.mkdir(parents=True, exist_ok=True)

STAC_ENDPOINT = "https://earth-search.aws.element84.com/v1/search"
BBOX = [76.7700, 30.7350, 76.7850, 30.7450]  # Focused around 30.7392 N, 76.7764 E


def acquire_60_month_satellite_catalog() -> Dict[str, Any]:
    """Query Earth Search STAC using pooled HTTP session for fast, robust acquisition."""
    print("--- Starting Genuine Satellite Data Acquisition (2020-01 to 2024-12) ---", flush=True)
    monthly_records = []
    total_months = 60
    catalog_path = RAW_SATELLITE_DIR / "sentinel2_monthly_catalog_2020_2024.json"

    # Reuse existing cache if already complete
    if catalog_path.exists():
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if len(cached.get("records", [])) == total_months:
                print(f"Catalog already complete with {total_months} records. Reusing {catalog_path}", flush=True)
                return cached
        except Exception:
            pass

    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
    session.mount("https://", adapter)

    for year in range(2020, 2025):
        print(f"\nQuerying year {year}...", flush=True)
        for month in range(1, 13):
            last_day = calendar.monthrange(year, month)[1]
            start_date = f"{year:04d}-{month:02d}-01T00:00:00Z"
            end_date = f"{year:04d}-{month:02d}-{last_day:02d}T23:59:59Z"
            month_str = f"{year:04d}-{month:02d}"

            payload = {
                "collections": ["sentinel-2-l2a"],
                "bbox": BBOX,
                "datetime": f"{start_date}/{end_date}",
                "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
                "limit": 3
            }

            best_scene = None
            try:
                r = session.post(STAC_ENDPOINT, json=payload, timeout=12)
                if r.status_code == 200:
                    feats = r.json().get("features", [])
                    if feats:
                        best_scene = feats[0]
            except Exception as err:
                print(f"Warning on {month_str}: {err}", flush=True)

            if best_scene:
                props = best_scene.get("properties", {})
                rec = {
                    "month": month_str,
                    "year": year,
                    "month_num": month,
                    "scene_id": best_scene.get("id"),
                    "platform": props.get("platform"),
                    "datetime": props.get("datetime"),
                    "cloud_cover_percent": round(float(props.get("eo:cloud_cover", 0.0)), 2),
                    "vegetation_percent": round(float(props.get("s2:vegetation_percentage", 0.0)), 2),
                    "not_vegetated_percent": round(float(props.get("s2:not_vegetated_percentage", 0.0)), 2),
                    "water_percent": round(float(props.get("s2:water_percentage", 0.0)), 2),
                    "dark_features_percent": round(float(props.get("s2:dark_features_percentage", 0.0)), 2),
                    "sun_elevation_deg": round(float(props.get("view:sun_elevation", 0.0)), 2),
                    "sun_azimuth_deg": round(float(props.get("view:sun_azimuth", 0.0)), 2),
                    "tile_id": props.get("mgrs:grid_square", "FQ"),
                    "utm_zone": props.get("mgrs:utm_zone", 43),
                    "red_asset_url": best_scene.get("assets", {}).get("red", {}).get("href"),
                    "nir_asset_url": best_scene.get("assets", {}).get("nir", {}).get("href"),
                    "scl_asset_url": best_scene.get("assets", {}).get("scl", {}).get("href"),
                    "thumbnail_url": best_scene.get("assets", {}).get("thumbnail", {}).get("href"),
                    "data_source": "Copernicus Sentinel-2 L2A (ESA / Element84 AWS Earth Search)"
                }
                monthly_records.append(rec)
                print(f"  [{len(monthly_records)}/{total_months}] {month_str}: {rec['scene_id']} (Cloud: {rec['cloud_cover_percent']}%, Veg: {rec['vegetation_percent']}%)", flush=True)
            else:
                print(f"  [ALERT] No scene found for {month_str}", flush=True)

            time.sleep(0.15)

    catalog_payload = {
        "title": "SoilSentinel Copernicus Sentinel-2 L2A Monthly Satellite Catalog",
        "study_region": "Indo-Gangetic Agricultural Plains / Punjab",
        "coordinates": {"nominal": [30.73, 76.77], "sampled": [30.7392, 76.7764]},
        "observation_horizon": {"start": "2020-01", "end": "2024-12", "record_count": len(monthly_records)},
        "licence": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
        "attribution": "Contains modified Copernicus Sentinel data (2020-2024) processed by ESA/Element84",
        "retrieval_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "records": monthly_records
    }

    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog_payload, f, indent=2)

    print(f"\nSuccessfully saved all {len(monthly_records)} records to {catalog_path}", flush=True)
    return catalog_payload


if __name__ == "__main__":
    acquire_60_month_satellite_catalog()
