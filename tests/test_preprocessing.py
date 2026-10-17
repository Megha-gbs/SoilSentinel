"""
Unit tests for SoilSentinel Preprocessing & Data Collection Modules.

Covers:
1. Data cleaning routines (deduplication, type conversions, precision rounding).
2. Schema and physical bounds validation (climate, soil, combined).
3. Depth-weighted aggregation (5cm, 10cm, 15cm layer thickness weighting).
4. NASA POWER missing-value convention (-999 / -999.0) and month-13 annual aggregate filtering.
5. ISRIC SoilGrids scale factors and raw extraction validation.
6. Dataset merging and region compatibility verification.
"""

import sys
import unittest
import tempfile
from pathlib import Path
from typing import Dict, Any
import numpy as np
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Preprocessing.clean_data import clean_climate_dataframe, clean_soil_dataframe
from src.Preprocessing.validate_data import (
    validate_climate_data,
    validate_soil_data,
    validate_combined_features,
    validate_feature_table,
)
from src.Preprocessing.merge_data import calculate_topsoil_weighted_averages, merge_datasets
from src.data_collection.soilgrids import SoilGridsCollector
from src.data_collection.nasa_power import NasaPowerCollector


def create_mock_soil_df() -> pd.DataFrame:
    """Create controlled 3-layer soil DataFrame for depth-weighted testing."""
    return pd.DataFrame([
        {
            "region": "Indo-Gangetic Agricultural Plains / Punjab",
            "nominal_latitude": 30.73,
            "nominal_longitude": 76.77,
            "sampled_latitude": 30.7392,
            "sampled_longitude": 76.7764,
            "depth_interval": "0-5cm",
            "soil_ph": 6.0,
            "clay_percent": 20.0,
            "sand_percent": 40.0,
            "silt_percent": 40.0,
            "soc_g_kg": 20.0,
            "data_source": "ISRIC SoilGrids v2.0"
        },
        {
            "region": "Indo-Gangetic Agricultural Plains / Punjab",
            "nominal_latitude": 30.73,
            "nominal_longitude": 76.77,
            "sampled_latitude": 30.7392,
            "sampled_longitude": 76.7764,
            "depth_interval": "5-15cm",
            "soil_ph": 7.0,
            "clay_percent": 30.0,
            "sand_percent": 35.0,
            "silt_percent": 35.0,
            "soc_g_kg": 10.0,
            "data_source": "ISRIC SoilGrids v2.0"
        },
        {
            "region": "Indo-Gangetic Agricultural Plains / Punjab",
            "nominal_latitude": 30.73,
            "nominal_longitude": 76.77,
            "sampled_latitude": 30.7392,
            "sampled_longitude": 76.7764,
            "depth_interval": "15-30cm",
            "soil_ph": 8.0,
            "clay_percent": 40.0,
            "sand_percent": 30.0,
            "silt_percent": 30.0,
            "soc_g_kg": 5.0,
            "data_source": "ISRIC SoilGrids v2.0"
        }
    ])


def create_mock_climate_df() -> pd.DataFrame:
    """Create controlled climate DataFrame."""
    return pd.DataFrame([
        {
            "region": "Indo-Gangetic Agricultural Plains / Punjab",
            "latitude": 30.73,
            "longitude": 76.77,
            "year": 2020,
            "month": 1,
            "date": "2020-01",
            "air_temperature_c": 15.254,
            "temperature_c": 15.254,
            "air_humidity_percent": 65.432,
            "humidity_percent": 65.432,
            "precipitation_mm_day": 2.108,
            "soil_temperature_layer1_c": 14.887,
            "soil_moisture_surface_fraction": 0.45123,
            "soil_moisture_rootzone_fraction": 0.55678,
            "data_source": "NASA POWER AG Community"
        }
    ])


class TestCleaningRoutines(unittest.TestCase):
    """Unit tests for clean_climate_dataframe and clean_soil_dataframe."""

    def test_clean_climate_deduplication(self):
        """clean_climate_dataframe must remove duplicate records on [region, year, month]."""
        df = pd.DataFrame([
            {"region": "RegionA", "year": "2020", "month": "1", "precipitation_mm_day": 2.0},
            {"region": "RegionA", "year": "2020", "month": "1", "precipitation_mm_day": 3.0},
            {"region": "RegionA", "year": "2020", "month": "2", "precipitation_mm_day": 4.0}
        ])
        cleaned = clean_climate_dataframe(df)
        self.assertEqual(len(cleaned), 2, "Duplicate month record must be pruned.")
        self.assertEqual(cleaned.loc[0, "precipitation_mm_day"], 2.0)
        self.assertEqual(cleaned.loc[1, "month"], 2)

    def test_clean_climate_types_and_rounding(self):
        """clean_climate_dataframe must cast year/month to int, format date string, and round floats."""
        df = pd.DataFrame([{
            "region": "RegionA",
            "year": "2021",
            "month": "3",
            "air_temperature_c": 25.1284,
            "air_humidity_percent": 45.6789,
            "precipitation_mm_day": 1.2345,
            "soil_temperature_layer1_c": 24.5678,
            "soil_moisture_surface_fraction": 0.35412,
            "soil_moisture_rootzone_fraction": 0.50129
        }])
        cleaned = clean_climate_dataframe(df)
        self.assertIsInstance(cleaned.loc[0, "year"], (int, np.integer))
        self.assertIsInstance(cleaned.loc[0, "month"], (int, np.integer))
        self.assertEqual(cleaned.loc[0, "date"], "2021-03")
        self.assertEqual(cleaned.loc[0, "air_temperature_c"], 25.13)
        self.assertEqual(cleaned.loc[0, "air_humidity_percent"], 45.68)
        self.assertEqual(cleaned.loc[0, "precipitation_mm_day"], 1.23)
        self.assertEqual(cleaned.loc[0, "soil_temperature_layer1_c"], 24.57)
        self.assertEqual(cleaned.loc[0, "soil_moisture_surface_fraction"], 0.3541)
        self.assertEqual(cleaned.loc[0, "soil_moisture_rootzone_fraction"], 0.5013)

    def test_clean_soil_deduplication_and_rounding(self):
        """clean_soil_dataframe must drop duplicate depth intervals and round values to 2 decimals."""
        df = pd.DataFrame([
            {"region": "RegionA", "depth_interval": "0-5cm", "soil_ph": 6.555, "clay_percent": 22.333},
            {"region": "RegionA", "depth_interval": "0-5cm", "soil_ph": 6.888, "clay_percent": 24.555},
            {"region": "RegionA", "depth_interval": "5-15cm", "soil_ph": 6.666, "clay_percent": 25.111}
        ])
        cleaned = clean_soil_dataframe(df)
        self.assertEqual(len(cleaned), 2)
        self.assertEqual(cleaned.loc[0, "soil_ph"], 6.56)
        self.assertEqual(cleaned.loc[0, "clay_percent"], 22.33)


class TestValidationRoutines(unittest.TestCase):
    """Unit tests for schema, completeness, and physical range validation functions."""

    def test_validate_climate_valid_data(self):
        """validate_climate_data must return True on a fully compliant climate DataFrame."""
        df = create_mock_climate_df()
        is_valid, msg = validate_climate_data(df)
        self.assertTrue(is_valid, f"Expected valid climate data, got error: {msg}")

    def test_validate_climate_missing_columns(self):
        """validate_climate_data must return False if required columns are missing."""
        df = create_mock_climate_df().drop(columns=["air_temperature_c"])
        is_valid, msg = validate_climate_data(df)
        self.assertFalse(is_valid)
        self.assertIn("Missing columns in climate data", msg)

    def test_validate_climate_empty(self):
        """validate_climate_data must return False for empty DataFrame."""
        # Empty DataFrame without columns triggers missing columns
        is_valid1, msg1 = validate_climate_data(pd.DataFrame())
        self.assertFalse(is_valid1)
        self.assertIn("Missing columns", msg1)

        # Empty DataFrame with expected columns triggers 0 rows check
        expected_cols = [
            "region", "latitude", "longitude", "year", "month", "date",
            "air_temperature_c", "air_humidity_percent", "precipitation_mm_day",
            "soil_temperature_layer1_c", "soil_moisture_surface_fraction",
            "soil_moisture_rootzone_fraction", "data_source"
        ]
        is_valid2, msg2 = validate_climate_data(pd.DataFrame(columns=expected_cols))
        self.assertFalse(is_valid2)
        self.assertIn("Climate dataset has 0 rows", msg2)

    def test_validate_climate_null_metadata(self):
        """validate_climate_data must reject nulls in spatial-temporal metadata columns."""
        df = create_mock_climate_df()
        df.loc[0, "date"] = np.nan
        is_valid, msg = validate_climate_data(df)
        self.assertFalse(is_valid)
        self.assertIn("Null values detected in climate metadata", msg)

    def test_validate_climate_physical_bounds(self):
        """validate_climate_data must reject physical range violations."""
        # Temperature out of bounds
        df_temp = create_mock_climate_df()
        df_temp.loc[0, "air_temperature_c"] = 75.0
        is_valid, msg = validate_climate_data(df_temp)
        self.assertFalse(is_valid)
        self.assertIn("Air temperature values found outside realistic physical bounds", msg)

        # Negative precipitation
        df_precip = create_mock_climate_df()
        df_precip.loc[0, "precipitation_mm_day"] = -1.0
        is_valid, msg = validate_climate_data(df_precip)
        self.assertFalse(is_valid)
        self.assertIn("Negative precipitation values detected", msg)

        # Soil moisture out of bounds
        df_moist = create_mock_climate_df()
        df_moist.loc[0, "soil_moisture_surface_fraction"] = 1.5
        is_valid, msg = validate_climate_data(df_moist)
        self.assertFalse(is_valid)
        self.assertIn("Surface soil wetness fraction found outside [0, 1]", msg)

    def test_validate_soil_valid_data(self):
        """validate_soil_data must pass on a compliant 3-layer soil DataFrame."""
        df = create_mock_soil_df()
        is_valid, msg = validate_soil_data(df)
        self.assertTrue(is_valid, f"Expected valid soil data, got error: {msg}")

    def test_validate_soil_missing_columns_or_nulls(self):
        """validate_soil_data must reject missing columns or any null values."""
        df_missing = create_mock_soil_df().drop(columns=["soil_ph"])
        is_valid, msg = validate_soil_data(df_missing)
        self.assertFalse(is_valid)
        self.assertIn("Missing columns in soil data", msg)

        df_null = create_mock_soil_df()
        df_null.loc[0, "soc_g_kg"] = np.nan
        is_valid, msg = validate_soil_data(df_null)
        self.assertFalse(is_valid)
        self.assertIn("Null values detected in soil data", msg)

    def test_validate_soil_physical_bounds(self):
        """validate_soil_data must reject unrealistic soil property bounds."""
        # Unrealistic pH
        df_ph = create_mock_soil_df()
        df_ph.loc[0, "soil_ph"] = 2.0
        is_valid, msg = validate_soil_data(df_ph)
        self.assertFalse(is_valid)
        self.assertIn("Soil pH outside realistic range", msg)

        # Texture fraction > 100%
        df_texture = create_mock_soil_df()
        df_texture.loc[0, "clay_percent"] = 105.0
        is_valid, msg = validate_soil_data(df_texture)
        self.assertFalse(is_valid)
        self.assertIn("clay_percent outside [0, 100] %", msg)

        # Negative SOC
        df_soc = create_mock_soil_df()
        df_soc.loc[0, "soc_g_kg"] = -5.0
        is_valid, msg = validate_soil_data(df_soc)
        self.assertFalse(is_valid)
        self.assertIn("Negative Soil Organic Carbon", msg)

    def test_validate_combined_features(self):
        """validate_combined_features must verify presence of required merged fields."""
        df_comb = pd.DataFrame([{
            "region": "RegionA", "date": "2020-01", "year": 2020, "month": 1,
            "air_temperature_c": 20.0, "air_humidity_percent": 50.0, "precipitation_mm_day": 2.0,
            "soil_temperature_layer1_c": 21.0, "soil_moisture_surface_fraction": 0.4,
            "soil_moisture_rootzone_fraction": 0.5, "topsoil_ph_mean": 6.5,
            "topsoil_clay_percent": 25.0, "topsoil_sand_percent": 40.0,
            "topsoil_silt_percent": 35.0, "topsoil_soc_g_kg": 12.0,
            "climate_source": "NASA POWER", "soil_source": "SoilGrids"
        }])
        is_valid, msg = validate_combined_features(df_comb)
        self.assertTrue(is_valid, f"Expected valid combined features, got: {msg}")

        # Missing required field
        is_valid_bad, msg_bad = validate_combined_features(df_comb.drop(columns=["topsoil_ph_mean"]))
        self.assertFalse(is_valid_bad)
        self.assertIn("Missing columns in combined features", msg_bad)

    def test_validate_feature_table_compliance(self):
        """validate_feature_table must validate active feature table schema and boundary NaNs."""
        csv_path = PROJECT_ROOT / "data" / "feature_table.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            is_valid, msg = validate_feature_table(df)
            self.assertTrue(is_valid, f"Feature table validation failed: {msg}")

    def test_validate_feature_table_rejects_missing_column(self):
        csv_path = PROJECT_ROOT / "data" / "feature_table.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path).drop(columns=["topsoil_soc_g_kg"])
            is_valid, msg = validate_feature_table(df)
            self.assertFalse(is_valid)
            self.assertIn("Missing required columns in feature table", msg)

    def test_validate_feature_table_length_aware_slices(self):
        """validate_feature_table must support valid slices without false NaN-count failures."""
        csv_path = PROJECT_ROOT / "data" / "feature_table.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            df_2rows = df.iloc[:2].copy()
            is_valid, msg = validate_feature_table(df_2rows)
            self.assertTrue(is_valid, f"2-row slice should pass: {msg}")


class TestDepthWeightedAverages(unittest.TestCase):
    """Tests for calculate_topsoil_weighted_averages across 0-30cm."""

    def test_depth_weighted_formula_exact_values(self):
        """
        Weights: 0-5cm (5cm), 5-15cm (10cm), 15-30cm (15cm).
        Total thickness: 30cm.
        Weights: 5/30 (1/6), 10/30 (2/6), 15/30 (3/6).
        """
        df_soil = create_mock_soil_df()
        # Layer 1: pH=6.0, Layer 2: pH=7.0, Layer 3: pH=8.0
        # Expected: (5*6 + 10*7 + 15*8) / 30 = (30 + 70 + 120) / 30 = 220 / 30 = 7.33
        # Clay: (5*20 + 10*30 + 15*40) / 30 = (100 + 300 + 600) / 30 = 1000 / 30 = 33.33%
        # Sand: (5*40 + 10*35 + 15*30) / 30 = (200 + 350 + 450) / 30 = 1000 / 30 = 33.33%
        # Silt: (5*40 + 10*35 + 15*30) / 30 = 33.33%
        # SOC: (5*20 + 10*10 + 15*5) / 30 = (100 + 100 + 75) / 30 = 275 / 30 = 9.17 g/kg
        result = calculate_topsoil_weighted_averages(df_soil)

        self.assertEqual(result["topsoil_ph_mean"], 7.33)
        self.assertEqual(result["topsoil_clay_percent"], 33.33)
        self.assertEqual(result["topsoil_sand_percent"], 33.33)
        self.assertEqual(result["topsoil_silt_percent"], 33.33)
        self.assertEqual(result["topsoil_soc_g_kg"], 9.17)

    def test_layer_specific_pivoting(self):
        """calculate_topsoil_weighted_averages must preserve layer-specific values."""
        df_soil = create_mock_soil_df()
        result = calculate_topsoil_weighted_averages(df_soil)

        # Layer 1 (0-5cm)
        self.assertEqual(result["ph_0_5cm"], 6.0)
        self.assertEqual(result["clay_0_5cm_percent"], 20.0)
        self.assertEqual(result["soc_0_5cm_g_kg"], 20.0)

        # Layer 2 (5-15cm)
        self.assertEqual(result["ph_5_15cm"], 7.0)
        self.assertEqual(result["clay_5_15cm_percent"], 30.0)
        self.assertEqual(result["soc_5_15cm_g_kg"], 10.0)

        # Layer 3 (15-30cm)
        self.assertEqual(result["ph_15_30cm"], 8.0)
        self.assertEqual(result["clay_15_30cm_percent"], 40.0)
        self.assertEqual(result["soc_15_30cm_g_kg"], 5.0)


class TestNasaPowerProcessing(unittest.TestCase):
    """Tests for NasaPowerCollector.process_and_validate without live network queries."""

    def setUp(self):
        self.collector = NasaPowerCollector()

    def test_missing_value_convention_and_month_13_filtering(self):
        """
        NasaPowerCollector must:
        1. Replace -999.0 and -999 fill values with np.nan.
        2. Filter out month '13' (annual summary).
        """
        mock_raw_payload = {
            "properties": {
                "parameter": {
                    "T2M": {"202001": 15.0, "202002": 18.0, "202013": 22.0},
                    "RH2M": {"202001": 50.0, "202002": 55.0, "202013": 52.0},
                    "PRECTOTCORR": {"202001": 2.5, "202002": -999.0, "202013": 3.0},
                    "GWETTOP": {"202001": 0.4, "202002": 0.5, "202013": 0.45},
                    "GWETROOT": {"202001": 0.6, "202002": 0.65, "202013": 0.62},
                    "TSOIL1": {"202001": 14.5, "202002": 17.5, "202013": 21.0}
                }
            }
        }
        df = self.collector.process_and_validate(mock_raw_payload)

        # Month 13 must be filtered out: exactly 2 monthly records
        self.assertEqual(len(df), 2, "Expected 2 monthly records (month 13 annual summary must be excluded).")
        self.assertEqual(list(df["date"]), ["2020-01", "2020-02"])

        # Row 0: valid precipitation
        self.assertEqual(df.loc[0, "precipitation_mm_day"], 2.5)

        # Row 1: -999.0 fill value converted to NaN
        self.assertTrue(np.isnan(df.loc[1, "precipitation_mm_day"]), "NASA -999 fill value must become np.nan.")

    def test_bounds_validation_raises_error(self):
        """process_and_validate must raise ValueError when physical bounds are violated."""
        mock_bad_temp = {
            "properties": {
                "parameter": {
                    "T2M": {"202001": 75.0},  # > 60 C
                    "RH2M": {"202001": 50.0},
                    "PRECTOTCORR": {"202001": 2.5},
                    "GWETTOP": {"202001": 0.4},
                    "GWETROOT": {"202001": 0.6},
                    "TSOIL1": {"202001": 14.5}
                }
            }
        }
        with self.assertRaises(ValueError) as ctx:
            self.collector.process_and_validate(mock_bad_temp)
        self.assertIn("Air temperature out of physical bounds", str(ctx.exception))


class TestSoilGridsProcessing(unittest.TestCase):
    """Tests for SoilGridsCollector scaling and validation without live VRT streaming."""

    def setUp(self):
        self.collector = SoilGridsCollector()

    def test_scale_factors_contract(self):
        """Scale factors must match official ISRIC conversion multipliers."""
        expected_scales = {
            "phh2o": 0.1,
            "clay": 0.1,
            "sand": 0.1,
            "silt": 0.1,
            "soc": 0.1
        }
        self.assertEqual(self.collector.SCALE_FACTORS, expected_scales)

    def test_process_and_validate_scaling(self):
        """Raw DN values must be scaled correctly and formatted into depth layer records."""
        mock_raw_data = {
            "records": [
                {
                    "property_alias": "ph", "soilgrids_code": "phh2o", "depth_interval": "0-5cm",
                    "raw_dn_value": 66.0, "nominal_latitude": 30.73, "nominal_longitude": 76.77,
                    "sampled_latitude": 30.7392, "sampled_longitude": 76.7764, "adjustment_distance_km": 1.0
                },
                {
                    "property_alias": "clay", "soilgrids_code": "clay", "depth_interval": "0-5cm",
                    "raw_dn_value": 250.0, "nominal_latitude": 30.73, "nominal_longitude": 76.77,
                    "sampled_latitude": 30.7392, "sampled_longitude": 76.7764, "adjustment_distance_km": 1.0
                },
                {
                    "property_alias": "sand", "soilgrids_code": "sand", "depth_interval": "0-5cm",
                    "raw_dn_value": 450.0, "nominal_latitude": 30.73, "nominal_longitude": 76.77,
                    "sampled_latitude": 30.7392, "sampled_longitude": 76.7764, "adjustment_distance_km": 1.0
                },
                {
                    "property_alias": "silt", "soilgrids_code": "silt", "depth_interval": "0-5cm",
                    "raw_dn_value": 300.0, "nominal_latitude": 30.73, "nominal_longitude": 76.77,
                    "sampled_latitude": 30.7392, "sampled_longitude": 76.7764, "adjustment_distance_km": 1.0
                },
                {
                    "property_alias": "soc", "soilgrids_code": "soc", "depth_interval": "0-5cm",
                    "raw_dn_value": 150.0, "nominal_latitude": 30.73, "nominal_longitude": 76.77,
                    "sampled_latitude": 30.7392, "sampled_longitude": 76.7764, "adjustment_distance_km": 1.0
                }
            ]
        }
        df = self.collector.process_and_validate(mock_raw_data)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.loc[0, "soil_ph"], 6.6)
        self.assertEqual(df.loc[0, "clay_percent"], 25.0)
        self.assertEqual(df.loc[0, "sand_percent"], 45.0)
        self.assertEqual(df.loc[0, "silt_percent"], 30.0)
        self.assertEqual(df.loc[0, "soc_g_kg"], 15.0)


class TestMergeDatasetsContract(unittest.TestCase):
    """Tests for merge_datasets input checking and contract enforcement."""

    def test_merge_region_mismatch_raises_error(self):
        """merge_datasets must raise ValueError if climate and soil regions do not match."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            clim_path = tmp_path / "clim.csv"
            soil_path = tmp_path / "soil.csv"
            comb_path = tmp_path / "comb.csv"
            cfg_path = tmp_path / "cfg.yaml"

            # Create climate with Region A
            df_clim = create_mock_climate_df()
            df_clim["region"] = "Punjab Agricultural Plain"
            df_clim.to_csv(clim_path, index=False)

            # Create soil with Region B
            df_soil = create_mock_soil_df()
            df_soil["region"] = "Haryana Agricultural Plain"
            df_soil.to_csv(soil_path, index=False)

            # Write temporary config YAML pointing to these paths
            import yaml
            cfg = {
                "climate": {"processed_output_path": str(clim_path)},
                "soil": {"processed_output_path": str(soil_path)},
                "pipeline": {"combined_output_path": str(comb_path)}
            }
            with open(cfg_path, "w", encoding="utf-8") as f:
                yaml.dump(cfg, f)

            with self.assertRaises(ValueError) as ctx:
                merge_datasets(config_path=str(cfg_path))
            self.assertIn("Region mismatch!", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
