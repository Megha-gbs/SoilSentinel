"""
SoilSentinel — Genuine Satellite Spectral Asset Acquisition Script.

Acquires verified Sentinel-2 Level-2A spectral rasters (Band 4 Red, Band 8 NIR, and SCL)
from AWS Earth Search Cloud-Optimized GeoTIFFs (COGs) for the Punjab study region
(Nominal: 30.7300 N, 76.7700 E; Sampled: 30.7392 N, 76.7764 E) across the entire 60-month
study horizon from January 2020 through December 2024.

Outputs:
  - data/raw/satellite/sentinel2_monthly_catalog_2020_2024.json (60-month STAC catalog)
  - data/raw/satellite/spectral_subsets/{scene_id}_{B04|B08|SCL}.tif (1 km x 1 km GeoTIFFs)
  - data/raw/satellite/spectral_acquisition_manifest.json (comprehensive download manifest)
"""

import os
import sys
import json
import time
import calendar
import logging
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import requests
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("acquire_satellite")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_SATELLITE_DIR = PROJECT_ROOT / "data" / "raw" / "satellite"
SUBSETS_DIR = RAW_SATELLITE_DIR / "spectral_subsets"
CATALOG_PATH = RAW_SATELLITE_DIR / "sentinel2_monthly_catalog_2020_2024.json"
MANIFEST_PATH = RAW_SATELLITE_DIR / "spectral_acquisition_manifest.json"

RAW_SATELLITE_DIR.mkdir(parents=True, exist_ok=True)
SUBSETS_DIR.mkdir(parents=True, exist_ok=True)


def to_portable_path(p: Path) -> str:
    """Convert an absolute or relative path to a repository-relative POSIX path for cross-platform portability."""
    try:
        return p.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except Exception:
        return p.as_posix()


STAC_ENDPOINT = "https://earth-search.aws.element84.com/v1/search"
BBOX_LONLAT = [76.7700, 30.7350, 76.7850, 30.7450]

# Sampled agricultural parcel coordinates (1.02 km NE of Chandigarh center)
SAMPLED_LON = 76.7764
SAMPLED_LAT = 30.7392
HALF_WIDTH_METERS = 500.0  # 1.0 km x 1.0 km bounding box (100x100 10m pixels)


def compute_parcel_utm_bounds() -> Tuple[float, float, float, float]:
    """Compute UTM Zone 43N bounding box for the 1 km x 1 km study window."""
    xs, ys = transform("EPSG:4326", "EPSG:32643", [SAMPLED_LON], [SAMPLED_LAT])
    cx, cy = xs[0], ys[0]
    return (
        cx - HALF_WIDTH_METERS,
        cy - HALF_WIDTH_METERS,
        cx + HALF_WIDTH_METERS,
        cy + HALF_WIDTH_METERS
    )


def ensure_stac_catalog() -> Dict[str, Any]:
    """Ensure that the 60-month Sentinel-2 Level-2A STAC catalog is present and valid."""
    total_months = 60
    if CATALOG_PATH.exists():
        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                cat = json.load(f)
            if len(cat.get("records", [])) == total_months:
                logger.info("Found existing STAC catalog with %d records at %s", total_months, CATALOG_PATH)
                return cat
        except Exception as e:
            logger.warning("Error reading existing catalog: %s. Re-querying STAC.", e)

    logger.info("Querying Earth Search STAC for 60 months (2020-01 to 2024-12)...")
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=3)
    session.mount("https://", adapter)

    monthly_records = []
    for year in range(2020, 2025):
        for month in range(1, 13):
            last_day = calendar.monthrange(year, month)[1]
            start_date = f"{year:04d}-{month:02d}-01T00:00:00Z"
            end_date = f"{year:04d}-{month:02d}-{last_day:02d}T23:59:59Z"
            month_str = f"{year:04d}-{month:02d}"

            payload = {
                "collections": ["sentinel-2-l2a"],
                "bbox": BBOX_LONLAT,
                "datetime": f"{start_date}/{end_date}",
                "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
                "limit": 3
            }

            best_scene = None
            try:
                r = session.post(STAC_ENDPOINT, json=payload, timeout=15)
                if r.status_code == 200:
                    feats = r.json().get("features", [])
                    if feats:
                        best_scene = feats[0]
            except Exception as err:
                logger.warning("STAC query exception for %s: %s", month_str, err)

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
            else:
                logger.error("No scene found for month %s", month_str)

            time.sleep(0.1)

    catalog_payload = {
        "title": "SoilSentinel Copernicus Sentinel-2 L2A Monthly Satellite Catalog",
        "study_region": "Indo-Gangetic Agricultural Plains / Punjab",
        "coordinates": {"nominal": [30.73, 76.77], "sampled": [SAMPLED_LAT, SAMPLED_LON]},
        "observation_horizon": {"start": "2020-01", "end": "2024-12", "record_count": len(monthly_records)},
        "licence": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
        "attribution": "Contains modified Copernicus Sentinel data (2020-2024) processed by ESA/Element84",
        "retrieval_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "records": monthly_records
    }

    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog_payload, f, indent=2)

    logger.info("Saved catalog with %d records to %s", len(monthly_records), CATALOG_PATH)
    return catalog_payload


def download_spectral_subset(
    url: str,
    dst_path: Path,
    bbox: Tuple[float, float, float, float],
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    Download a spatial window from remote Cloud-Optimized GeoTIFF and save as a valid local GeoTIFF.
    Uses HTTP range requests via rasterio without downloading full 200MB granulates.
    """
    if dst_path.exists() and dst_path.stat().st_size > 500:
        # Validate existing file
        try:
            with rasterio.open(dst_path) as src:
                if src.width > 0 and src.height > 0:
                    return {
                        "path": to_portable_path(dst_path),
                        "size_bytes": dst_path.stat().st_size,
                        "width": src.width,
                        "height": src.height,
                        "crs": str(src.crs),
                        "status": "VERIFIED_EXISTING"
                    }
        except Exception:
            pass  # Corrupt or incomplete, re-download

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            with rasterio.open(url) as src:
                win = from_bounds(*bbox, transform=src.transform)
                data = src.read(1, window=win)
                win_transform = rasterio.windows.transform(win, src.transform)
                profile = src.profile.copy()
                profile.update({
                    "height": data.shape[0],
                    "width": data.shape[1],
                    "transform": win_transform,
                    "compress": "deflate"
                })
                with rasterio.open(dst_path, "w", **profile) as dst:
                    dst.write(data, 1)

            # Verify downloaded file
            with rasterio.open(dst_path) as verify_src:
                assert verify_src.width > 0 and verify_src.height > 0
                return {
                    "path": to_portable_path(dst_path),
                    "size_bytes": dst_path.stat().st_size,
                    "width": verify_src.width,
                    "height": verify_src.height,
                    "crs": str(verify_src.crs),
                    "status": "DOWNLOADED_SUCCESS"
                }
        except Exception as err:
            last_error = str(err)
            time.sleep(1.0 * attempt)

    return {
        "path": to_portable_path(dst_path),
        "size_bytes": 0,
        "width": 0,
        "height": 0,
        "crs": "",
        "status": f"FAILED: {last_error}"
    }


def acquire_scene_spectral_data(
    rec: Dict[str, Any],
    bbox: Tuple[float, float, float, float]
) -> Dict[str, Any]:
    """Download B04, B08, and SCL rasters for a single monthly record."""
    scene_id = rec["scene_id"]
    month = rec["month"]
    bands = {
        "B04": rec["red_asset_url"],
        "B08": rec["nir_asset_url"],
        "SCL": rec["scl_asset_url"]
    }

    band_manifest = {}
    all_success = True
    for b_name, b_url in bands.items():
        dst_path = SUBSETS_DIR / f"{scene_id}_{b_name}.tif"
        res = download_spectral_subset(b_url, dst_path, bbox)
        band_manifest[b_name] = res
        if "FAILED" in res["status"]:
            all_success = False

    return {
        "month": month,
        "year": rec["year"],
        "month_num": rec["month_num"],
        "scene_id": scene_id,
        "datetime": rec["datetime"],
        "cloud_cover_percent": rec["cloud_cover_percent"],
        "vegetation_percent": rec["vegetation_percent"],
        "bands": band_manifest,
        "overall_status": "DOWNLOADED" if all_success else "FAILED"
    }


def download_all_spectral_assets(
    max_workers: int = 6
) -> Dict[str, Any]:
    """
    Download and verify genuine B04, B08, and SCL GeoTIFF rasters for all 60 months.
    Saves spectral acquisition manifest.
    """
    catalog = ensure_stac_catalog()
    records = catalog["records"]
    bbox = compute_parcel_utm_bounds()

    logger.info("Commencing genuine spectral asset download for %d monthly scenes (workers=%d)...", len(records), max_workers)
    t_start = time.time()
    manifest_records = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(acquire_scene_spectral_data, rec, bbox): rec["month"]
            for rec in records
        }
        for future in concurrent.futures.as_completed(futures):
            m_str = futures[future]
            try:
                result = future.result()
                manifest_records.append(result)
                logger.info(
                    "[%d/%d] Processed %s: %s (Status: %s)",
                    len(manifest_records), len(records), m_str, result["scene_id"], result["overall_status"]
                )
            except Exception as e:
                logger.error("Exception processing %s: %s", m_str, e)
                manifest_records.append({
                    "month": m_str,
                    "scene_id": "UNKNOWN",
                    "overall_status": f"EXCEPTION: {e}"
                })

    # Sort chronologically by month
    manifest_records.sort(key=lambda x: x["month"])

    success_count = sum(1 for m in manifest_records if m.get("overall_status") == "DOWNLOADED")
    elapsed = time.time() - t_start

    manifest_payload = {
        "title": "SoilSentinel Sentinel-2 Level-2A Spectral Asset Acquisition Manifest",
        "description": "Local 1 km x 1 km GeoTIFF subsets of B04 (Red), B08 (NIR), and SCL (Scene Classification)",
        "study_area": {
            "nominal_coordinates": [30.7300, 76.7700],
            "sampled_coordinates": [SAMPLED_LAT, SAMPLED_LON],
            "utm_crs": "EPSG:32643",
            "utm_bounds": list(bbox),
            "window_size_meters": [1000.0, 1000.0]
        },
        "acquisition_summary": {
            "total_months": len(records),
            "successfully_acquired_months": success_count,
            "failed_months": len(records) - success_count,
            "elapsed_seconds": round(elapsed, 2),
            "storage_directory": to_portable_path(SUBSETS_DIR)
        },
        "records": manifest_records
    }

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest_payload, f, indent=2)

    logger.info(
        "Spectral acquisition complete: %d/%d scenes downloaded in %.2fs. Manifest saved to %s",
        success_count, len(records), elapsed, MANIFEST_PATH
    )

    return manifest_payload


if __name__ == "__main__":
    download_all_spectral_assets()
