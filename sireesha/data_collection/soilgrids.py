"""
ISRIC SoilGrids Data Collection Module.

Retrieves official soil property measurements (pH, clay, sand, silt, soil organic carbon)
from official ISRIC SoilGrids v2.0 resources:
- WebDAV / VRT repository: https://files.isric.org/soilgrids/latest/data/
- REST API (fallback/inspection): https://rest.isric.org/soilgrids/v2.0/

SoilGrids Reference:
https://www.isric.org/explore/soilgrids
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import requests
import numpy as np
import pandas as pd
import yaml
import rasterio
from rasterio.warp import transform

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("soilgrids_collector")


def load_config(config_path: str = "config/settings.yaml") -> Dict[str, Any]:
    """Load project settings from YAML file."""
    path = Path(config_path)
    if not path.is_absolute():
        project_root = Path(__file__).resolve().parent.parent.parent
        path = project_root / config_path
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class SoilGridsCollector:
    """Automates soil property extraction from official ISRIC SoilGrids data."""

    # Official ISRIC SoilGrids scale factors to standard physical units
    # - phh2o: raw value in pH*10 -> / 10 = standard pH
    # - clay: raw value in g/kg -> / 10 = % (or keep g/kg)
    # - sand: raw value in g/kg -> / 10 = % (or keep g/kg)
    # - silt: raw value in g/kg -> / 10 = % (or keep g/kg)
    # - soc: raw value in dg/kg -> / 10 = g/kg (mass fraction)
    SCALE_FACTORS = {
        "phh2o": 0.1,    # pH units
        "clay": 0.1,     # %
        "sand": 0.1,     # %
        "silt": 0.1,     # %
        "soc": 0.1       # g/kg
    }

    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config = load_config(config_path)
        self.study_region = self.config["study_region"]
        self.soil_cfg = self.config["soil"]
        self.pipeline_cfg = self.config.get("pipeline", {})

        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.raw_dir = self.project_root / self.soil_cfg.get("raw_output_dir", "data/raw/soil")
        self.processed_file = self.project_root / self.soil_cfg.get("processed_output_path", "data/processed/soil_data.csv")

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_file.parent.mkdir(parents=True, exist_ok=True)

    def _sample_from_vrt(self, vrt_url: str, lon: float, lat: float,
                         auto_adjust: bool = True, max_radius_km: float = 10.0) -> Tuple[float, float, float, float]:
        """
        Extract pixel value from official ISRIC VRT file using rasterio /vsicurl/.
        If the nominal coordinate falls on nodata (e.g., urban masking), searches
        outwards up to max_radius_km for the nearest valid agricultural soil pixel.

        Returns:
            Tuple of (raw_dn_value, sampled_lat, sampled_lon, distance_km)
        """
        with rasterio.open(vrt_url) as src:
            nodata_val = src.nodata if src.nodata is not None else -32768

            # Transform nominal WGS84 coordinate to dataset CRS (Goode Homolosine)
            xs, ys = transform("EPSG:4326", src.crs, [lon], [lat])
            nominal_x, nominal_y = xs[0], ys[0]
            center_row, center_col = src.index(nominal_x, nominal_y)

            # Sample exact target pixel
            center_win = rasterio.windows.Window(center_col, center_row, 1, 1)
            raw_pixel = src.read(1, window=center_win)[0, 0]

            if raw_pixel != nodata_val:
                return float(raw_pixel), lat, lon, 0.0

            if not auto_adjust:
                raise ValueError(f"SoilGrids coordinate ({lat}, {lon}) is masked as NODATA ({nodata_val}).")

            logger.info("Nominal coordinate (%.4f, %.4f) has NODATA (masked urban/water). Searching nearest valid pixel...", lat, lon)

            # SoilGrids resolution is 250m per pixel. 1 km ~ 4 pixels.
            max_pixel_radius = int(max_radius_km * 4) + 1
            for rad in range(1, max_pixel_radius + 1):
                win = rasterio.windows.Window(center_col - rad, center_row - rad, 2 * rad + 1, 2 * rad + 1)
                data = src.read(1, window=win)
                valid_coords = np.argwhere(data != nodata_val)
                if len(valid_coords) > 0:
                    dists = [((r - rad)**2 + (c - rad)**2, r, c) for r, c in valid_coords]
                    dists.sort()
                    _, best_r, best_c = dists[0]

                    target_row = center_row - rad + best_r
                    target_col = center_col - rad + best_c
                    target_x, target_y = src.xy(target_row, target_col)
                    t_lons, t_lats = transform(src.crs, "EPSG:4326", [target_x], [target_y])

                    dist_km = rad * 0.25
                    found_val = float(data[best_r, best_c])
                    logger.info("Found nearest valid soil pixel at %.2f km (lat=%.4f, lon=%.4f): raw_dn=%s",
                                dist_km, t_lats[0], t_lons[0], found_val)
                    return found_val, float(t_lats[0]), float(t_lons[0]), dist_km

            raise ValueError(f"No valid soil pixels found within {max_radius_km} km radius of ({lat}, {lon}).")

    def collect_soil_data(self, force: bool = False) -> Dict[str, Any]:
        """
        Collect soil property measurements across all configured depths.
        Saves raw responses to data/raw/soil/.
        """
        raw_filepath = self.raw_dir / "soilgrids_raw_metadata.json"
        if raw_filepath.exists() and not force:
            logger.info("Using cached raw SoilGrids response from %s", raw_filepath)
            with open(raw_filepath, "r", encoding="utf-8") as f:
                return json.load(f)

        vrt_base = self.soil_cfg.get("vrt_base_url", "https://files.isric.org/soilgrids/latest/data")
        props_map = self.soil_cfg.get("properties", {
            "ph": "phh2o",
            "clay": "clay",
            "sand": "sand",
            "silt": "silt",
            "soc": "soc"
        })
        depths = self.soil_cfg.get("depths", ["0-5cm", "5-15cm", "15-30cm"])
        value_type = self.soil_cfg.get("value_type", "mean")

        nominal_lat = self.study_region["latitude"]
        nominal_lon = self.study_region["longitude"]
        auto_adjust = self.study_region.get("auto_adjust_nodata", True)
        max_radius = self.study_region.get("max_search_radius_km", 10.0)

        logger.info("Collecting SoilGrids properties for %s (Lat: %.4f, Lon: %.4f)...",
                    self.study_region["name"], nominal_lat, nominal_lon)

        raw_records = []
        sampled_coord = None

        # Lock coordinate onto first layer's valid pixel to ensure consistent spatial sampling across all layers
        for prop_key, prop_code in props_map.items():
            for depth in depths:
                vrt_url = f"{vrt_base}/{prop_code}/{prop_code}_{depth}_{value_type}.vrt"
                logger.info("Querying layer: %s (%s, %s)...", prop_code, depth, value_type)

                query_lat = sampled_coord[0] if sampled_coord else nominal_lat
                query_lon = sampled_coord[1] if sampled_coord else nominal_lon

                val, s_lat, s_lon, dist = self._sample_from_vrt(
                    vrt_url, query_lon, query_lat,
                    auto_adjust=auto_adjust, max_radius_km=max_radius
                )

                if sampled_coord is None:
                    sampled_coord = (s_lat, s_lon, dist)

                raw_records.append({
                    "property_alias": prop_key,
                    "soilgrids_code": prop_code,
                    "depth_interval": depth,
                    "value_type": value_type,
                    "raw_dn_value": val,
                    "vrt_url": vrt_url,
                    "nominal_latitude": nominal_lat,
                    "nominal_longitude": nominal_lon,
                    "sampled_latitude": round(s_lat, 4),
                    "sampled_longitude": round(s_lon, 4),
                    "adjustment_distance_km": round(dist, 2),
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                })

        output_payload = {
            "source": "ISRIC SoilGrids v2.0 (Official Files Service)",
            "region": self.study_region["name"],
            "nominal_coordinates": {"latitude": nominal_lat, "longitude": nominal_lon},
            "sampled_coordinates": {
                "latitude": sampled_coord[0] if sampled_coord else nominal_lat,
                "longitude": sampled_coord[1] if sampled_coord else nominal_lon,
                "distance_km": sampled_coord[2] if sampled_coord else 0.0
            },
            "records": raw_records
        }

        with open(raw_filepath, "w", encoding="utf-8") as f:
            json.dump(output_payload, f, indent=2)

        logger.info("Saved raw SoilGrids query metadata to %s", raw_filepath)
        return output_payload

    def process_and_validate(self, raw_data: Dict[str, Any]) -> pd.DataFrame:
        """
        Convert raw SoilGrids records to physical units, validate ranges,
        and construct layer-wise and aggregated depth records.
        """
        region_name = self.study_region["name"]
        records = raw_data.get("records", [])
        if not records:
            raise ValueError("No records found in raw SoilGrids data.")

        # Group by depth_interval
        depth_groups: Dict[str, Dict[str, float]] = {}
        coord_info = None

        for rec in records:
            depth = rec["depth_interval"]
            prop = rec["soilgrids_code"]
            raw_val = rec["raw_dn_value"]
            if coord_info is None:
                coord_info = {
                    "nominal_latitude": rec["nominal_latitude"],
                    "nominal_longitude": rec["nominal_longitude"],
                    "sampled_latitude": rec["sampled_latitude"],
                    "sampled_longitude": rec["sampled_longitude"],
                    "distance_km": rec["adjustment_distance_km"]
                }

            if depth not in depth_groups:
                depth_groups[depth] = {}
            depth_groups[depth][prop] = raw_val

        rows = []
        for depth, vals in depth_groups.items():
            # Apply official scale factors
            ph_raw = vals.get("phh2o")
            clay_raw = vals.get("clay")
            sand_raw = vals.get("sand")
            silt_raw = vals.get("silt")
            soc_raw = vals.get("soc")

            if None in (ph_raw, clay_raw, sand_raw, silt_raw, soc_raw):
                raise ValueError(f"Missing one or more required soil properties for depth {depth}: {vals}")

            ph = round(ph_raw * self.SCALE_FACTORS["phh2o"], 2)
            clay_pct = round(clay_raw * self.SCALE_FACTORS["clay"], 2)
            sand_pct = round(sand_raw * self.SCALE_FACTORS["sand"], 2)
            silt_pct = round(silt_raw * self.SCALE_FACTORS["silt"], 2)
            soc_g_kg = round(soc_raw * self.SCALE_FACTORS["soc"], 2)

            # Validation
            if not (3.0 <= ph <= 11.0):
                raise ValueError(f"Invalid soil pH out of physical range [3.0, 11.0]: {ph}")
            if not (0.0 <= clay_pct <= 100.0):
                raise ValueError(f"Invalid clay %: {clay_pct}")
            if not (0.0 <= sand_pct <= 100.0):
                raise ValueError(f"Invalid sand %: {sand_pct}")
            if not (0.0 <= silt_pct <= 100.0):
                raise ValueError(f"Invalid silt %: {silt_pct}")
            if soc_g_kg < 0.0:
                raise ValueError(f"Invalid SOC: {soc_g_kg}")

            # Soil texture consistency check: clay + sand + silt should sum to ~100%
            texture_sum = clay_pct + sand_pct + silt_pct
            if not (90.0 <= texture_sum <= 110.0):
                logger.warning("Texture components sum to %.1f%% (expected ~100%%) at depth %s", texture_sum, depth)

            rows.append({
                "region": region_name,
                "nominal_latitude": coord_info["nominal_latitude"],
                "nominal_longitude": coord_info["nominal_longitude"],
                "sampled_latitude": coord_info["sampled_latitude"],
                "sampled_longitude": coord_info["sampled_longitude"],
                "depth_interval": depth,
                "soil_ph": ph,
                "clay_percent": clay_pct,
                "sand_percent": sand_pct,
                "silt_percent": silt_pct,
                "soc_g_kg": soc_g_kg,
                "data_source": "ISRIC SoilGrids v2.0"
            })

        df = pd.DataFrame(rows)
        logger.info("Successfully validated %d soil depth layer records.", len(df))
        return df

    def run(self, force: bool = False) -> pd.DataFrame:
        """Execute full soil data collection and processing pipeline."""
        logger.info("--- Starting SoilGrids Soil Data Collection ---")
        raw_data = self.collect_soil_data(force=force)
        df = self.process_and_validate(raw_data)
        df.to_csv(self.processed_file, index=False)
        logger.info("Validated soil dataset written to: %s", self.processed_file)
        logger.info("--- SoilGrids Collection Completed Successfully ---")
        return df


if __name__ == "__main__":
    collector = SoilGridsCollector()
    df_soil = collector.run()
    print("\nSoil Dataset Preview:")
    print(df_soil)
    print(f"\nTotal Rows: {len(df_soil)}")
    print(f"Columns: {list(df_soil.columns)}")
