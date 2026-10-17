"""
Unit tests for Soil Sentinel Pipeline Orchestration.

Tests:
1. End-to-end pipeline execution (download_all.py:run_pipeline) with all 4 steps:
   - Step 1: Climate data collection
   - Step 2: Soil data collection
   - Step 3: Dataset merging & validation
   - Step 4: Feature engineering & master feature table generation
2. Pipeline return dictionary structure (contains 'climate', 'soil', 'combined', 'feature_table', 'feature_table_path').
3. Pipeline failure handling (aborts if Step 3 validation fails, preventing Step 4 execution).
4. Custom feature table output path override.
5. Entrypoint orchestration in main.py.
6. Safeguard: All tests run in temporary directories without modifying production datasets.
"""

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import yaml
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_collection.download_all import run_pipeline
import main


def create_mock_climate_df(n_months: int = 4) -> pd.DataFrame:
    """Create controlled multi-month climate DataFrame for pipeline testing."""
    dates = ["2020-01", "2020-02", "2020-03", "2020-04", "2020-05", "2020-06"][:n_months]
    records = []
    for i, d in enumerate(dates):
        y, m = d.split("-")
        records.append({
            "region": "Indo-Gangetic Agricultural Plains / Punjab",
            "latitude": 30.73,
            "longitude": 76.77,
            "year": int(y),
            "month": int(m),
            "date": d,
            "air_temperature_c": 15.0 + (i * 3.0),
            "temperature_c": 15.0 + (i * 3.0),
            "air_humidity_percent": 60.0 - (i * 5.0),
            "humidity_percent": 60.0 - (i * 5.0),
            "precipitation_mm_day": 2.0 + (i * 2.0),
            "soil_temperature_layer1_c": 14.5 + (i * 3.0),
            "soil_moisture_surface_fraction": 0.45,
            "soil_moisture_rootzone_fraction": 0.55,
            "data_source": "NASA POWER AG Community"
        })
    return pd.DataFrame(records)


def create_mock_soil_df() -> pd.DataFrame:
    """Create controlled 3-layer soil DataFrame for pipeline testing."""
    return pd.DataFrame([
        {
            "region": "Indo-Gangetic Agricultural Plains / Punjab",
            "nominal_latitude": 30.73,
            "nominal_longitude": 76.77,
            "sampled_latitude": 30.7392,
            "sampled_longitude": 76.7764,
            "depth_interval": "0-5cm",
            "soil_ph": 6.6,
            "clay_percent": 21.5,
            "sand_percent": 43.9,
            "silt_percent": 34.6,
            "soc_g_kg": 23.9,
            "data_source": "ISRIC SoilGrids v2.0"
        },
        {
            "region": "Indo-Gangetic Agricultural Plains / Punjab",
            "nominal_latitude": 30.73,
            "nominal_longitude": 76.77,
            "sampled_latitude": 30.7392,
            "sampled_longitude": 76.7764,
            "depth_interval": "5-15cm",
            "soil_ph": 6.6,
            "clay_percent": 23.7,
            "sand_percent": 42.6,
            "silt_percent": 33.7,
            "soc_g_kg": 14.6,
            "data_source": "ISRIC SoilGrids v2.0"
        },
        {
            "region": "Indo-Gangetic Agricultural Plains / Punjab",
            "nominal_latitude": 30.73,
            "nominal_longitude": 76.77,
            "sampled_latitude": 30.7392,
            "sampled_longitude": 76.7764,
            "depth_interval": "15-30cm",
            "soil_ph": 6.5,
            "clay_percent": 28.6,
            "sand_percent": 39.3,
            "silt_percent": 32.1,
            "soc_g_kg": 8.2,
            "data_source": "ISRIC SoilGrids v2.0"
        }
    ])


class TestPipelineOrchestration(unittest.TestCase):
    """Test full pipeline orchestration from collection through feature engineering."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

        # File paths inside sandbox
        self.clim_csv = self.tmp_path / "climate_data.csv"
        self.soil_csv = self.tmp_path / "soil_data.csv"
        self.comb_csv = self.tmp_path / "combined_features.csv"
        self.feat_csv = self.tmp_path / "feature_table.csv"
        self.cfg_yaml = self.tmp_path / "test_settings.yaml"

        # Mock DataFrames
        self.mock_clim_df = create_mock_climate_df(4)
        self.mock_soil_df = create_mock_soil_df()

        # Build test settings YAML pointing to sandbox
        self.test_config = {
            "study_region": {
                "name": "Indo-Gangetic Agricultural Plains / Punjab",
                "latitude": 30.73,
                "longitude": 76.77,
                "auto_adjust_nodata": True,
                "max_search_radius_km": 10.0,
                "start_year": 2020,
                "end_year": 2020
            },
            "climate": {
                "api_base_url": "https://power.larc.nasa.gov/api/temporal/monthly/point",
                "community": "AG",
                "parameters": ["T2M", "RH2M", "PRECTOTCORR", "GWETTOP", "GWETROOT", "TSOIL1"],
                "raw_output_dir": str(self.tmp_path / "raw_climate"),
                "processed_output_path": str(self.clim_csv)
            },
            "soil": {
                "source": "ISRIC SoilGrids v2.0",
                "vrt_base_url": "https://files.isric.org/soilgrids/latest/data",
                "depths": ["0-5cm", "5-15cm", "15-30cm"],
                "value_type": "mean",
                "raw_output_dir": str(self.tmp_path / "raw_soil"),
                "processed_output_path": str(self.soil_csv)
            },
            "pipeline": {
                "retry_attempts": 1,
                "retry_backoff_factor": 1.0,
                "timeout_seconds": 10,
                "combined_output_path": str(self.comb_csv),
                "feature_table_output_path": str(self.feat_csv)
            }
        }
        with open(self.cfg_yaml, "w", encoding="utf-8") as f:
            yaml.dump(self.test_config, f)

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("src.data_collection.download_all.SoilGridsCollector")
    @patch("src.data_collection.download_all.NasaPowerCollector")
    def test_run_pipeline_end_to_end_orchestration(self, mock_nasa_cls, mock_soil_cls):
        """run_pipeline must execute all 4 steps and return complete results dict including feature table."""
        # Setup mocks to write processed files and return DataFrames
        mock_nasa_inst = MagicMock()
        mock_nasa_inst.run.side_effect = lambda force=False: (
            self.mock_clim_df.to_csv(self.clim_csv, index=False) or self.mock_clim_df
        )
        mock_nasa_cls.return_value = mock_nasa_inst

        mock_soil_inst = MagicMock()
        mock_soil_inst.run.side_effect = lambda force=False: (
            self.mock_soil_df.to_csv(self.soil_csv, index=False) or self.mock_soil_df
        )
        mock_soil_cls.return_value = mock_soil_inst

        # Execute pipeline with sandbox configuration
        results = run_pipeline(config_path=str(self.cfg_yaml))

        # 1. Verify returned result structure
        self.assertIn("climate", results)
        self.assertIn("soil", results)
        self.assertIn("combined", results)
        self.assertIn("feature_table", results)
        self.assertIn("feature_table_path", results)

        # 2. Verify row counts and schema
        self.assertEqual(len(results["climate"]), 4)
        self.assertEqual(len(results["soil"]), 3)
        self.assertEqual(len(results["combined"]), 4)
        self.assertEqual(len(results["feature_table"]), 4)
        self.assertEqual(len(results["feature_table"].columns), 53)

        # 3. Verify files written to disk in sandbox
        self.assertTrue(self.clim_csv.exists(), "Processed climate file must exist.")
        self.assertTrue(self.soil_csv.exists(), "Processed soil file must exist.")
        self.assertTrue(self.comb_csv.exists(), "Processed combined file must exist.")
        self.assertTrue(self.feat_csv.exists(), "Engineered feature table must exist.")

        # 4. Verify feature table content from disk
        df_disk = pd.read_csv(self.feat_csv)
        self.assertEqual(df_disk.shape, (4, 53))
        self.assertEqual(list(df_disk["date"]), ["2020-01", "2020-02", "2020-03", "2020-04"])

    @patch("src.data_collection.download_all.build_feature_table")
    @patch("src.data_collection.download_all.merge_datasets")
    @patch("src.data_collection.download_all.SoilGridsCollector")
    @patch("src.data_collection.download_all.NasaPowerCollector")
    def test_run_pipeline_aborts_before_step_4_on_validation_failure(
        self, mock_nasa_cls, mock_soil_cls, mock_merge, mock_build_features
    ):
        """run_pipeline must raise ValueError and NOT call build_feature_table if combined validation fails."""
        mock_nasa_inst = MagicMock()
        mock_nasa_inst.run.return_value = self.mock_clim_df
        mock_nasa_cls.return_value = mock_nasa_inst

        mock_soil_inst = MagicMock()
        mock_soil_inst.run.return_value = self.mock_soil_df
        mock_soil_cls.return_value = mock_soil_inst

        # Return invalid combined DataFrame (empty, triggers validation failure)
        mock_merge.return_value = pd.DataFrame()

        with self.assertRaises(ValueError) as ctx:
            run_pipeline(config_path=str(self.cfg_yaml))

        self.assertIn("Combined features validation failed", str(ctx.exception))
        mock_build_features.assert_not_called()

    @patch("src.data_collection.download_all.SoilGridsCollector")
    @patch("src.data_collection.download_all.NasaPowerCollector")
    def test_run_pipeline_custom_feature_table_path_override(self, mock_nasa_cls, mock_soil_cls):
        """run_pipeline must honor an explicit feature_table_output_path argument."""
        mock_nasa_inst = MagicMock()
        mock_nasa_inst.run.side_effect = lambda force=False: (
            self.mock_clim_df.to_csv(self.clim_csv, index=False) or self.mock_clim_df
        )
        mock_nasa_cls.return_value = mock_nasa_inst

        mock_soil_inst = MagicMock()
        mock_soil_inst.run.side_effect = lambda force=False: (
            self.mock_soil_df.to_csv(self.soil_csv, index=False) or self.mock_soil_df
        )
        mock_soil_cls.return_value = mock_soil_inst

        custom_output = self.tmp_path / "custom_features_table.csv"
        results = run_pipeline(
            config_path=str(self.cfg_yaml),
            feature_table_output_path=custom_output
        )

        self.assertEqual(results["feature_table_path"], custom_output)
        self.assertTrue(custom_output.exists(), "Custom output path must be populated.")

    @patch("main.run_pipeline")
    def test_main_entrypoint_invokes_pipeline(self, mock_run_pipeline):
        """main.py must invoke run_pipeline and report feature table output without errors."""
        mock_results = {
            "climate": self.mock_clim_df,
            "soil": self.mock_soil_df,
            "combined": pd.DataFrame({"dummy": range(4)}),
            "feature_table": pd.DataFrame({"col": range(53)}).T,
            "feature_table_path": self.feat_csv
        }
        mock_run_pipeline.return_value = mock_results

        captured_stdout = io.StringIO()
        with patch("sys.stdout", captured_stdout):
            main.main()

        mock_run_pipeline.assert_called_once()
        output = captured_stdout.getvalue()
        self.assertIn("Pipeline execution finished successfully.", output)
        self.assertIn("Feature table records:", output)
        self.assertIn("Output path:", output)


if __name__ == "__main__":
    unittest.main()
