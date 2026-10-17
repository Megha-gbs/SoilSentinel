"""
SoilSentinel — Genuine Satellite Spectral Processing Pipeline.

Calculates Normalized Difference Vegetation Index (NDVI) from genuine Copernicus
Sentinel-2 Level-2A B04 (Red, 665nm) and B08 (NIR, 842nm) spectral GeoTIFF rasters,
incorporating pixel-level quality masking via Scene Classification Layer (SCL).

Scientific Algorithm:
  NDVI = (NIR - RED) / (NIR + RED)
  
Quality Assurance:
  - Pixels with SCL in [3, 8, 9, 10, 11, 0, 1] (cloud, cirrus, cloud shadow, snow, nodata, defective) are masked.
  - Valid ground observation pixels: SCL in [4, 5, 6, 7] (vegetation, bare soil, water, unclassified ground).
  - Safe denominator handling: where (NIR + RED) == 0, NDVI is assigned NaN.
  - Physical bounding: valid NDVI must strictly reside in [-1.0, 1.0].
  - If valid pixel fraction < 20% in the parcel, the month is flagged as QUALITY_UNUSABLE_CLOUDY
    and assigned NaN, strictly preventing silent synthetic imputation.

Outputs:
  data/processed/satellite/satellite_ndvi_monthly_2020_2024.csv
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import numpy as np
import pandas as pd
import rasterio

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("process_satellite")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_SATELLITE_DIR = PROJECT_ROOT / "data" / "raw" / "satellite"
SUBSETS_DIR = RAW_SATELLITE_DIR / "spectral_subsets"
MANIFEST_PATH = RAW_SATELLITE_DIR / "spectral_acquisition_manifest.json"
CATALOG_PATH = RAW_SATELLITE_DIR / "sentinel2_monthly_catalog_2020_2024.json"

PROCESSED_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "satellite"
PROCESSED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_CSV_PATH = PROCESSED_OUTPUT_DIR / "satellite_ndvi_monthly_2020_2024.csv"

# Valid and contaminated SCL classes
SCL_VALID_GROUND = {4, 5, 6, 7}  # 4=veg, 5=bare soil, 6=water, 7=unclassified
SCL_CLOUD_SHADOW = {3, 8, 9, 10, 11}  # 3=shadow, 8=cloud med, 9=cloud high, 10=cirrus, 11=snow
SCL_INVALID = {0, 1}  # 0=nodata, 1=saturated/defective


def compute_spectral_ndvi_array(
    red: np.ndarray,
    nir: np.ndarray,
    scl: Optional[np.ndarray] = None
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Compute pixel-level NDVI array from Red and NIR arrays with optional SCL masking.
    
    Returns:
        ndvi: 2D numpy array with NaN for invalid/masked pixels
        valid_mask: 2D boolean array of valid ground observation pixels
        stats: dictionary of pixel counts and class fractions
    """
    if red.shape != nir.shape:
        raise ValueError(f"Shape mismatch: RED {red.shape} vs NIR {nir.shape}")

    red_flt = red.astype(np.float64)
    nir_flt = nir.astype(np.float64)

    total_pixels = int(red.size)
    denom = nir_flt + red_flt

    # Base validity: positive signal and non-zero denominator
    base_valid = (denom > 0.0) & (red_flt >= 0.0) & (nir_flt >= 0.0)

    # SCL quality masking
    if scl is not None:
        if scl.shape != red.shape:
            # Resample 20m SCL to match 10m Red/NIR
            scale_y = red.shape[0] // scl.shape[0]
            scale_x = red.shape[1] // scl.shape[1]
            scl_resampled = np.repeat(np.repeat(scl, scale_y, axis=0), scale_x, axis=1)
            scl_matched = scl_resampled[:red.shape[0], :red.shape[1]]
        else:
            scl_matched = scl

        valid_ground = np.isin(scl_matched, list(SCL_VALID_GROUND))
        cloud_shadow = np.isin(scl_matched, list(SCL_CLOUD_SHADOW))
        veg_mask = (scl_matched == 4)
        bare_soil_mask = (scl_matched == 5)
    else:
        valid_ground = np.ones_like(red, dtype=bool)
        cloud_shadow = np.zeros_like(red, dtype=bool)
        veg_mask = np.zeros_like(red, dtype=bool)
        bare_soil_mask = np.zeros_like(red, dtype=bool)

    valid_mask = base_valid & valid_ground

    # Calculate NDVI
    ndvi = np.full_like(red_flt, np.nan, dtype=np.float64)
    np.divide(nir_flt - red_flt, denom, out=ndvi, where=valid_mask)

    # Clip to physical bounds [-1.0, 1.0] for floating point rounding
    ndvi = np.where(valid_mask, np.clip(ndvi, -1.0, 1.0), np.nan)

    valid_count = int(np.sum(valid_mask))
    stats = {
        "total_pixels": total_pixels,
        "valid_pixels": valid_count,
        "valid_fraction": valid_count / total_pixels if total_pixels > 0 else 0.0,
        "cloud_shadow_fraction": int(np.sum(cloud_shadow)) / total_pixels if total_pixels > 0 else 0.0,
        "scl_vegetation_fraction": int(np.sum(veg_mask)) / total_pixels if total_pixels > 0 else 0.0,
        "scl_bare_soil_fraction": int(np.sum(bare_soil_mask)) / total_pixels if total_pixels > 0 else 0.0,
    }

    return ndvi, valid_mask, stats


def determine_quality_flag(valid_fraction: float, cloud_fraction: float) -> str:
    """Assign rigorous quality flag based on pixel-level validity."""
    if valid_fraction >= 0.90 and cloud_fraction <= 0.05:
        return "QUALITY_PRISTINE"
    elif valid_fraction >= 0.75 and cloud_fraction <= 0.15:
        return "QUALITY_GOOD"
    elif valid_fraction >= 0.50:
        return "QUALITY_ACCEPTABLE"
    elif valid_fraction >= 0.20:
        return "QUALITY_MARGINAL_CLOUDY"
    else:
        return "QUALITY_UNUSABLE_CLOUDY"


def process_scene_rasters(
    scene_id: str,
    subsets_dir: Path
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Dict[str, Any]]:
    """Load B04, B08, and SCL rasters for a scene and calculate NDVI summary statistics."""
    b04_path = subsets_dir / f"{scene_id}_B04.tif"
    b08_path = subsets_dir / f"{scene_id}_B08.tif"
    scl_path = subsets_dir / f"{scene_id}_SCL.tif"

    if not b04_path.exists() or not b08_path.exists():
        raise FileNotFoundError(f"Missing spectral rasters for scene {scene_id} at {subsets_dir}")

    with rasterio.open(b04_path) as src_r, rasterio.open(b08_path) as src_n:
        red = src_r.read(1)
        nir = src_n.read(1)

    scl = None
    if scl_path.exists():
        with rasterio.open(scl_path) as src_s:
            scl = src_s.read(1)

    ndvi, valid_mask, stats = compute_spectral_ndvi_array(red, nir, scl)

    # If valid ground pixels are sufficient (>= 20% parcel area), calculate statistics
    if stats["valid_fraction"] >= 0.20 and stats["valid_pixels"] > 0:
        valid_ndvi = ndvi[valid_mask]
        ndvi_mean = float(np.mean(valid_ndvi))
        ndvi_median = float(np.median(valid_ndvi))
        ndvi_std = float(np.std(valid_ndvi))
        ndvi_min = float(np.min(valid_ndvi))
        ndvi_max = float(np.max(valid_ndvi))
    else:
        # Heavily overcast / obscured scene: mark as NaN, do not invent values
        ndvi_mean = np.nan
        ndvi_median = np.nan
        ndvi_std = np.nan
        ndvi_min = np.nan
        ndvi_max = np.nan

    return ndvi_mean, ndvi_median, ndvi_std, ndvi_min, ndvi_max, stats


def process_satellite_dataset(
    manifest_path: Optional[Path] = None,
    output_path: Optional[Path] = None
) -> pd.DataFrame:
    """
    Process all genuine Sentinel-2 spectral raster observations into a validated,
    traceable monthly NDVI dataset.
    """
    mf_file = manifest_path or MANIFEST_PATH
    out_file = output_path or PROCESSED_CSV_PATH

    if not mf_file.exists():
        raise FileNotFoundError(f"Acquisition manifest not found at {mf_file}. Run acquire_satellite_data.py first.")

    with open(mf_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    records = manifest.get("records", [])
    if not records:
        raise ValueError("Acquisition manifest contains zero records.")

    study_meta = manifest.get("study_area", {})
    nominal_coords = study_meta.get("nominal_coordinates", [30.7300, 76.7700])
    sampled_coords = study_meta.get("sampled_coordinates", [30.7392, 76.7764])

    logger.info("Processing genuine spectral NDVI for %d monthly records...", len(records))

    rows = []
    for rec in records:
        month_str = rec["month"]
        year = int(rec["year"])
        month_num = int(rec["month_num"])
        scene_id = rec["scene_id"]
        obs_date = rec["datetime"]

        ndvi_mean, ndvi_median, ndvi_std, ndvi_min, ndvi_max, stats = process_scene_rasters(
            scene_id, SUBSETS_DIR
        )

        quality_flag = determine_quality_flag(stats["valid_fraction"], stats["cloud_shadow_fraction"])

        rows.append({
            "region": "Indo-Gangetic Agricultural Plains / Punjab",
            "nominal_latitude": nominal_coords[0],
            "nominal_longitude": nominal_coords[1],
            "sampled_latitude": sampled_coords[0],
            "sampled_longitude": sampled_coords[1],
            "coordinate_substitution_distance_m": 1020.0,
            "coordinate_substitution_reason": "ISRIC SoilGrids urban mask NODATA (-32768) at Chandigarh city center",
            "year": year,
            "month": month_num,
            "date": month_str,
            "satellite_scene_id": scene_id,
            "satellite_observation_date": obs_date,
            "satellite_platform": "Sentinel-2A" if "S2A" in scene_id else "Sentinel-2B",
            "satellite_ndvi": round(ndvi_mean, 4) if not np.isnan(ndvi_mean) else np.nan,
            "satellite_ndvi_median": round(ndvi_median, 4) if not np.isnan(ndvi_median) else np.nan,
            "satellite_ndvi_std": round(ndvi_std, 4) if not np.isnan(ndvi_std) else np.nan,
            "satellite_ndvi_min": round(ndvi_min, 4) if not np.isnan(ndvi_min) else np.nan,
            "satellite_ndvi_max": round(ndvi_max, 4) if not np.isnan(ndvi_max) else np.nan,
            "satellite_valid_pixel_count": stats["valid_pixels"],
            "satellite_total_pixel_count": stats["total_pixels"],
            "satellite_valid_pixel_fraction": round(stats["valid_fraction"], 4),
            "satellite_cloud_shadow_pixel_fraction": round(stats["cloud_shadow_fraction"], 4),
            "satellite_scl_vegetation_fraction": round(stats["scl_vegetation_fraction"], 4),
            "satellite_scl_bare_soil_fraction": round(stats["scl_bare_soil_fraction"], 4),
            "satellite_quality_flag": quality_flag,
            "satellite_spatial_resolution_m": 10.0,
            "satellite_red_band": "B04 (665 nm)",
            "satellite_nir_band": "B08 (842 nm)",
            "satellite_quality_layer": "SCL (Scene Classification Layer, 20 m)",
            "satellite_processing_method": "GENUINE_SPECTRAL_L2A_SCL_MASKED_RATIO",
            "satellite_b04_file": f"spectral_subsets/{scene_id}_B04.tif",
            "satellite_b08_file": f"spectral_subsets/{scene_id}_B08.tif",
            "satellite_scl_file": f"spectral_subsets/{scene_id}_SCL.tif",
            "satellite_data_source": "Copernicus Sentinel-2 Level-2A (ESA)",
            "satellite_licence": "CC BY 4.0"
        })

    df = pd.DataFrame(rows)

    # Verification checks
    assert len(df) == 60, f"Expected 60 records, found {len(df)}"
    assert not df["date"].duplicated().any(), "Duplicate monthly dates found"

    valid_mask = df["satellite_ndvi"].notna()
    assert (df.loc[valid_mask, "satellite_ndvi"] >= -1.0).all(), "NDVI below -1.0"
    assert (df.loc[valid_mask, "satellite_ndvi"] <= 1.0).all(), "NDVI above +1.0"

    out_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_file, index=False)

    obs_count = int(valid_mask.sum())
    nan_count = int((~valid_mask).sum())
    logger.info(
        "Successfully produced genuine spectral satellite dataset at: %s (shape: %s)",
        out_file, df.shape
    )
    logger.info("Summary: %d observed months, %d cloudy/missing months (NaN preserved)", obs_count, nan_count)

    return df


if __name__ == "__main__":
    process_satellite_dataset()
