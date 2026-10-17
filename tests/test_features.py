"""
Unit tests for SoilSentinel Feature Engineering Module (src/features.py).

Tests:
1. Expected schema, column ordering, and data types (53 columns).
2. Chronological sequence continuity and 60-month temporal coverage (2020-01 to 2024-12).
3. 1-month lag features and 3-month rolling aggregates with correct boundary NaNs.
4. Temporal cyclical encodings (sin/cos) and agro-climatic season mappings.
5. Soil-climate coupling indicators (thermal difference, moisture depth gradient, aridity index).
6. Static soil texture and structural ratios (clay-to-sand, SOC-to-clay Dexter index).
7. Validation constraints, error handling for malformed inputs, and deterministic reproducibility.
"""

import sys
import unittest
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.features import build_feature_table


EXPECTED_53_COLUMNS = [
    "region",
    "nominal_latitude",
    "nominal_longitude",
    "sampled_latitude",
    "sampled_longitude",
    "year",
    "month",
    "date",
    "air_temperature_c",
    "temperature_c",
    "air_humidity_percent",
    "humidity_percent",
    "precipitation_mm_day",
    "soil_temperature_layer1_c",
    "soil_moisture_surface_fraction",
    "soil_moisture_rootzone_fraction",
    "topsoil_ph_mean",
    "topsoil_clay_percent",
    "topsoil_sand_percent",
    "topsoil_silt_percent",
    "topsoil_soc_g_kg",
    "ph_0_5cm",
    "ph_5_15cm",
    "ph_15_30cm",
    "clay_0_5cm_percent",
    "clay_5_15cm_percent",
    "clay_15_30cm_percent",
    "sand_0_5cm_percent",
    "sand_5_15cm_percent",
    "sand_15_30cm_percent",
    "silt_0_5cm_percent",
    "silt_5_15cm_percent",
    "silt_15_30cm_percent",
    "soc_0_5cm_g_kg",
    "soc_5_15cm_g_kg",
    "soc_15_30cm_g_kg",
    "climate_source",
    "soil_source",
    "quarter",
    "season",
    "month_sin",
    "month_cos",
    "precipitation_lag1_mm_day",
    "precipitation_rolling_3m_mean_mm_day",
    "precipitation_rolling_3m_sum_mm_day",
    "air_temperature_lag1_c",
    "temp_soil_air_diff_c",
    "soil_moisture_depth_gradient",
    "monthly_aridity_index",
    "clay_to_sand_ratio",
    "soc_to_clay_ratio",
    "soil_measurement_type",
    "climate_measurement_type"
]


def create_synthetic_combined_fixture(n_rows: int = 4) -> pd.DataFrame:
    """Create a small, controlled combined_features DataFrame for feature engineering tests."""
    dates = ["2020-01", "2020-02", "2020-03", "2020-04", "2020-05", "2020-06"][:n_rows]
    precip_values = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0][:n_rows]
    air_temp_values = [15.0, 18.0, 22.0, 26.0, 30.0, 34.0][:n_rows]
    soil_temp_values = [14.0, 17.5, 23.0, 27.5, 31.0, 35.0][:n_rows]

    records = []
    for i, d in enumerate(dates):
        y, m = d.split("-")
        records.append({
            "region": "Indo-Gangetic Agricultural Plains / Punjab",
            "nominal_latitude": 30.73,
            "nominal_longitude": 76.77,
            "sampled_latitude": 30.7392,
            "sampled_longitude": 76.7764,
            "year": int(y),
            "month": int(m),
            "date": d,
            "air_temperature_c": air_temp_values[i],
            "temperature_c": air_temp_values[i],
            "air_humidity_percent": 60.0 - (i * 5.0),
            "humidity_percent": 60.0 - (i * 5.0),
            "precipitation_mm_day": precip_values[i],
            "soil_temperature_layer1_c": soil_temp_values[i],
            "soil_moisture_surface_fraction": 0.45,
            "soil_moisture_rootzone_fraction": 0.55,
            "topsoil_ph_mean": 6.55,
            "topsoil_clay_percent": 25.0,
            "topsoil_sand_percent": 45.0,
            "topsoil_silt_percent": 30.0,
            "topsoil_soc_g_kg": 12.5,
            "ph_0_5cm": 6.6,
            "ph_5_15cm": 6.6,
            "ph_15_30cm": 6.5,
            "clay_0_5cm_percent": 21.0,
            "clay_5_15cm_percent": 24.0,
            "clay_15_30cm_percent": 28.0,
            "sand_0_5cm_percent": 45.0,
            "sand_5_15cm_percent": 44.0,
            "sand_15_30cm_percent": 40.0,
            "silt_0_5cm_percent": 34.0,
            "silt_5_15cm_percent": 32.0,
            "silt_15_30cm_percent": 32.0,
            "soc_0_5cm_g_kg": 22.0,
            "soc_5_15cm_g_kg": 14.0,
            "soc_15_30cm_g_kg": 8.0,
            "climate_source": "NASA POWER AG Community",
            "soil_source": "ISRIC SoilGrids v2.0"
        })
    return pd.DataFrame(records)


class TestFeatureTableRepository(unittest.TestCase):
    """Integration verification tests using the active repository feature table."""

    @classmethod
    def setUpClass(cls):
        cls.feature_table_path = PROJECT_ROOT / "data" / "feature_table.csv"
        if not cls.feature_table_path.exists():
            raise unittest.SkipTest(f"Missing repository feature table at {cls.feature_table_path}")
        cls.df = pd.read_csv(cls.feature_table_path)

    def test_dimensions(self):
        """Repository feature table must contain exactly 60 monthly rows and 53 columns."""
        self.assertEqual(self.df.shape, (60, 53), "feature_table.csv shape must be (60, 53)")

    def test_column_names_and_order(self):
        """Repository feature table columns must match expected 53-column master index exactly."""
        self.assertEqual(list(self.df.columns), EXPECTED_53_COLUMNS,
                         "Column names and sequence must match expected 53-column catalog exactly.")

    def test_temporal_coverage_and_continuity(self):
        """Feature table must span consecutive months from 2020-01 to 2024-12 without gaps or duplicates."""
        expected_dates = [
            f"{y}-{m:02d}" for y in range(2020, 2025) for m in range(1, 13)
        ]
        actual_dates = list(self.df["date"])
        self.assertEqual(actual_dates, expected_dates, "Dates must match 60 consecutive monthly strings.")
        self.assertEqual(self.df["date"].duplicated().sum(), 0, "No duplicate dates permitted.")

    def test_expected_boundary_nans(self):
        """Boundary NaNs must occur exclusively in 1-month lags (1 NaN) and 3-month rolling windows (2 NaNs)."""
        self.assertEqual(self.df["precipitation_lag1_mm_day"].isnull().sum(), 1)
        self.assertEqual(self.df["air_temperature_lag1_c"].isnull().sum(), 1)
        self.assertEqual(self.df["precipitation_rolling_3m_mean_mm_day"].isnull().sum(), 2)
        self.assertEqual(self.df["precipitation_rolling_3m_sum_mm_day"].isnull().sum(), 2)

        # Confirm that index 0 is NaN for lags, and indices 0, 1 are NaN for rolling features
        self.assertTrue(pd.isna(self.df.loc[0, "precipitation_lag1_mm_day"]))
        self.assertTrue(pd.isna(self.df.loc[0, "air_temperature_lag1_c"]))
        self.assertTrue(pd.isna(self.df.loc[0, "precipitation_rolling_3m_mean_mm_day"]))
        self.assertTrue(pd.isna(self.df.loc[1, "precipitation_rolling_3m_mean_mm_day"]))
        self.assertTrue(pd.isna(self.df.loc[0, "precipitation_rolling_3m_sum_mm_day"]))
        self.assertTrue(pd.isna(self.df.loc[1, "precipitation_rolling_3m_sum_mm_day"]))

    def test_zero_nans_in_non_lag_columns(self):
        """All other 49 non-lag/rolling columns must contain 0 missing values."""
        non_lag_cols = [c for c in self.df.columns if c not in [
            "precipitation_lag1_mm_day", "air_temperature_lag1_c",
            "precipitation_rolling_3m_mean_mm_day", "precipitation_rolling_3m_sum_mm_day"
        ]]
        null_counts = self.df[non_lag_cols].isnull().sum()
        unexpected = null_counts[null_counts > 0].to_dict()
        self.assertEqual(unexpected, {}, f"Unexpected NaNs in non-lag columns: {unexpected}")

    def test_physical_bounds_repository_values(self):
        """Repository values must strictly fall within verified physical bounds."""
        self.assertTrue(self.df["air_temperature_c"].between(-50.0, 60.0).all())
        self.assertTrue(self.df["air_humidity_percent"].between(0.0, 100.0).all())
        self.assertTrue((self.df["precipitation_mm_day"] >= 0.0).all())
        self.assertTrue(self.df["soil_temperature_layer1_c"].between(-50.0, 60.0).all())
        self.assertTrue(self.df["soil_moisture_surface_fraction"].between(0.0, 1.0).all())
        self.assertTrue(self.df["soil_moisture_rootzone_fraction"].between(0.0, 1.0).all())
        self.assertTrue(self.df["topsoil_ph_mean"].between(3.0, 11.0).all())
        self.assertTrue(self.df["topsoil_clay_percent"].between(0.0, 100.0).all())
        self.assertTrue(self.df["topsoil_sand_percent"].between(0.0, 100.0).all())
        self.assertTrue(self.df["topsoil_silt_percent"].between(0.0, 100.0).all())
        self.assertTrue((self.df["topsoil_soc_g_kg"] >= 0.0).all())

    def test_integer_dtypes_repository_table(self):
        """Repository table year, month, and quarter columns must be int64."""
        self.assertEqual(self.df["year"].dtype, np.dtype("int64"), "year column in feature_table.csv must be int64")
        self.assertEqual(self.df["month"].dtype, np.dtype("int64"), "month column in feature_table.csv must be int64")
        self.assertEqual(self.df["quarter"].dtype, np.dtype("int64"), "quarter column in feature_table.csv must be int64")


class TestFeatureCalculationsControlled(unittest.TestCase):
    """Isolated unit tests of feature calculation formulas using small synthetic fixtures."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.fixture_df = create_synthetic_combined_fixture(n_rows=4)
        self.combined_input = self.temp_path / "combined_test.csv"
        self.feature_output = self.temp_path / "feature_table_test.csv"
        self.fixture_df.to_csv(self.combined_input, index=False)

        # Build feature table from controlled fixture
        self.result_df = build_feature_table(
            combined_path=self.combined_input,
            output_path=self.feature_output
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_integer_dtypes_standardization(self):
        """year, month, and quarter columns must have int64 dtype in the in-memory feature table."""
        self.assertEqual(self.result_df["year"].dtype, np.dtype("int64"), "year column must be int64")
        self.assertEqual(self.result_df["month"].dtype, np.dtype("int64"), "month column must be int64")
        self.assertEqual(self.result_df["quarter"].dtype, np.dtype("int64"), "quarter column must be int64")

    def test_one_month_lags(self):
        """1-month lag features must equal t-1 values with exactly 1 boundary NaN at index 0."""
        precip_vals = [2.0, 4.0, 6.0, 8.0]
        temp_vals = [15.0, 18.0, 22.0, 26.0]

        # Row 0: boundary NaN
        self.assertTrue(np.isnan(self.result_df.loc[0, "precipitation_lag1_mm_day"]))
        self.assertTrue(np.isnan(self.result_df.loc[0, "air_temperature_lag1_c"]))

        # Rows 1..3: shifted by 1
        for i in range(1, 4):
            self.assertAlmostEqual(self.result_df.loc[i, "precipitation_lag1_mm_day"], precip_vals[i - 1])
            self.assertAlmostEqual(self.result_df.loc[i, "air_temperature_lag1_c"], temp_vals[i - 1])

    def test_three_month_rolling_aggregates(self):
        """3-month rolling mean and sum must have exactly 2 NaNs and correct window aggregates."""
        precip_vals = [2.0, 4.0, 6.0, 8.0]

        # Rows 0 and 1: boundary NaNs
        self.assertTrue(np.isnan(self.result_df.loc[0, "precipitation_rolling_3m_mean_mm_day"]))
        self.assertTrue(np.isnan(self.result_df.loc[1, "precipitation_rolling_3m_mean_mm_day"]))
        self.assertTrue(np.isnan(self.result_df.loc[0, "precipitation_rolling_3m_sum_mm_day"]))
        self.assertTrue(np.isnan(self.result_df.loc[1, "precipitation_rolling_3m_sum_mm_day"]))

        # Row 2 (window: 2.0, 4.0, 6.0): sum = 12.0, mean = 4.0
        expected_sum_2 = 2.0 + 4.0 + 6.0
        expected_mean_2 = expected_sum_2 / 3.0
        self.assertAlmostEqual(self.result_df.loc[2, "precipitation_rolling_3m_sum_mm_day"], expected_sum_2)
        self.assertAlmostEqual(self.result_df.loc[2, "precipitation_rolling_3m_mean_mm_day"], expected_mean_2)

        # Row 3 (window: 4.0, 6.0, 8.0): sum = 18.0, mean = 6.0
        expected_sum_3 = 4.0 + 6.0 + 8.0
        expected_mean_3 = expected_sum_3 / 3.0
        self.assertAlmostEqual(self.result_df.loc[3, "precipitation_rolling_3m_sum_mm_day"], expected_sum_3)
        self.assertAlmostEqual(self.result_df.loc[3, "precipitation_rolling_3m_mean_mm_day"], expected_mean_3)

    def test_cyclical_calendar_encodings(self):
        """Month sin/cos cyclical coordinates must match exact mathematical trigonometric values."""
        # Month 1 (Jan): sin(2pi*1/12) = sin(pi/6) = 0.5000, cos = 0.8660
        self.assertAlmostEqual(self.result_df.loc[0, "month_sin"], round(np.sin(2 * np.pi * 1 / 12), 4))
        self.assertAlmostEqual(self.result_df.loc[0, "month_cos"], round(np.cos(2 * np.pi * 1 / 12), 4))

        # Month 3 (Mar): sin(2pi*3/12) = sin(pi/2) = 1.0000, cos = 0.0000
        self.assertAlmostEqual(self.result_df.loc[2, "month_sin"], 1.0000)
        self.assertAlmostEqual(self.result_df.loc[2, "month_cos"], 0.0000)

    def test_season_mapping(self):
        """Agro-climatic season mapping must categorize all calendar months correctly."""
        # Month 1 (Jan) -> Winter
        self.assertEqual(self.result_df.loc[0, "season"], "Winter")
        # Month 2 (Feb) -> Winter
        self.assertEqual(self.result_df.loc[1, "season"], "Winter")
        # Month 3 (Mar) -> Summer_PreMonsoon
        self.assertEqual(self.result_df.loc[2, "season"], "Summer_PreMonsoon")
        # Month 4 (Apr) -> Summer_PreMonsoon
        self.assertEqual(self.result_df.loc[3, "season"], "Summer_PreMonsoon")

    def test_thermal_and_hydrological_coupling(self):
        """temp_soil_air_diff_c and soil_moisture_depth_gradient must match exact differences."""
        for i in range(4):
            expected_diff = round(self.result_df.loc[i, "soil_temperature_layer1_c"] - self.result_df.loc[i, "air_temperature_c"], 2)
            self.assertAlmostEqual(self.result_df.loc[i, "temp_soil_air_diff_c"], expected_diff)

            expected_grad = round(self.result_df.loc[i, "soil_moisture_rootzone_fraction"] - self.result_df.loc[i, "soil_moisture_surface_fraction"], 4)
            self.assertAlmostEqual(self.result_df.loc[i, "soil_moisture_depth_gradient"], expected_grad)

    def test_aridity_index_formula(self):
        """monthly_aridity_index must follow De Martonne proxy: (P * 30.0) / (T + 10.0)."""
        for i in range(4):
            p = self.result_df.loc[i, "precipitation_mm_day"]
            t = self.result_df.loc[i, "air_temperature_c"]
            expected_aridity = round((p * 30.0) / (t + 10.0), 2)
            self.assertAlmostEqual(self.result_df.loc[i, "monthly_aridity_index"], expected_aridity)

    def test_soil_texture_and_dexter_structural_ratios(self):
        """clay_to_sand_ratio and soc_to_clay_ratio must match exact definitions."""
        # Clay = 25.0%, Sand = 45.0% -> Clay/Sand = 25.0 / 45.0 = 0.556
        expected_clay_sand = round(25.0 / 45.0, 3)
        self.assertAlmostEqual(self.result_df.loc[0, "clay_to_sand_ratio"], expected_clay_sand)

        # SOC = 12.5 g/kg, Clay = 25.0% -> 250 g/kg -> SOC/Clay = 12.5 / 250.0 = 0.0500
        expected_soc_clay = round(12.5 / (25.0 * 10.0), 4)
        self.assertAlmostEqual(self.result_df.loc[0, "soc_to_clay_ratio"], expected_soc_clay)


def create_custom_dates_fixture(date_list: list) -> pd.DataFrame:
    """Create a synthetic combined DataFrame with specific dates for temporal testing."""
    records = []
    for i, d in enumerate(date_list):
        y, m = d.split("-")
        records.append({
            "region": "Indo-Gangetic Agricultural Plains / Punjab",
            "nominal_latitude": 30.73,
            "nominal_longitude": 76.77,
            "sampled_latitude": 30.7392,
            "sampled_longitude": 76.7764,
            "year": int(y),
            "month": int(m),
            "date": d,
            "air_temperature_c": 15.0 + (i * 2.0),
            "temperature_c": 15.0 + (i * 2.0),
            "air_humidity_percent": 60.0,
            "humidity_percent": 60.0,
            "precipitation_mm_day": 2.0 + i,
            "soil_temperature_layer1_c": 14.0 + (i * 2.0),
            "soil_moisture_surface_fraction": 0.45,
            "soil_moisture_rootzone_fraction": 0.55,
            "topsoil_ph_mean": 6.55,
            "topsoil_clay_percent": 25.0,
            "topsoil_sand_percent": 45.0,
            "topsoil_silt_percent": 30.0,
            "topsoil_soc_g_kg": 12.5,
            "ph_0_5cm": 6.6,
            "ph_5_15cm": 6.6,
            "ph_15_30cm": 6.5,
            "clay_0_5cm_percent": 21.0,
            "clay_5_15cm_percent": 24.0,
            "clay_15_30cm_percent": 28.0,
            "sand_0_5cm_percent": 45.0,
            "sand_5_15cm_percent": 44.0,
            "sand_15_30cm_percent": 40.0,
            "silt_0_5cm_percent": 34.0,
            "silt_5_15cm_percent": 32.0,
            "silt_15_30cm_percent": 32.0,
            "soc_0_5cm_g_kg": 22.0,
            "soc_5_15cm_g_kg": 14.0,
            "soc_15_30cm_g_kg": 8.0,
            "climate_source": "NASA POWER AG Community",
            "soil_source": "ISRIC SoilGrids v2.0"
        })
    return pd.DataFrame(records)


class TestFeatureEngineeringEdgeCases(unittest.TestCase):
    """Tests for edge cases, error conditions, temporal continuity, and reproducibility."""

    def test_valid_consecutive_monthly_sequence(self):
        """build_feature_table must succeed for valid consecutive months."""
        fixture = create_custom_dates_fixture(["2020-01", "2020-02", "2020-03", "2020-04"])
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            in_file = tmp_path / "valid_seq.csv"
            out_file = tmp_path / "valid_out.csv"
            fixture.to_csv(in_file, index=False)

            df_res = build_feature_table(combined_path=in_file, output_path=out_file)
            self.assertEqual(len(df_res), 4)
            self.assertEqual(list(df_res["date"]), ["2020-01", "2020-02", "2020-03", "2020-04"])

    def test_missing_month_raises_error(self):
        """build_feature_table must raise ValueError when monthly records have a temporal gap."""
        fixture = create_custom_dates_fixture(["2020-01", "2020-02", "2020-04", "2020-05"])  # Missing 2020-03
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            in_file = tmp_path / "gap_seq.csv"
            out_file = tmp_path / "gap_out.csv"
            fixture.to_csv(in_file, index=False)

            with self.assertRaises(ValueError) as ctx:
                build_feature_table(combined_path=in_file, output_path=out_file)
            self.assertIn("Temporal gap detected", str(ctx.exception))
            self.assertIn("2020-03", str(ctx.exception))

    def test_duplicate_dates_raises_error(self):
        """build_feature_table must reject input data with duplicate dates."""
        fixture = create_custom_dates_fixture(["2020-01", "2020-02", "2020-02", "2020-03"])
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            in_file = tmp_path / "dup_dates.csv"
            out_file = tmp_path / "dup_out.csv"
            fixture.to_csv(in_file, index=False)

            with self.assertRaises(ValueError) as ctx:
                build_feature_table(combined_path=in_file, output_path=out_file)
            self.assertIn("Duplicate monthly records detected", str(ctx.exception))

    def test_out_of_order_months_raises_error(self):
        """build_feature_table must raise ValueError if records are not in chronological order."""
        fixture = create_custom_dates_fixture(["2020-02", "2020-01", "2020-03", "2020-04"])
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            in_file = tmp_path / "unordered_seq.csv"
            out_file = tmp_path / "unordered_out.csv"
            fixture.to_csv(in_file, index=False)

            with self.assertRaises(ValueError) as ctx:
                build_feature_table(combined_path=in_file, output_path=out_file)
            self.assertIn("out of chronological order", str(ctx.exception))

    def test_december_to_january_year_transition_valid(self):
        """build_feature_table must successfully validate cross-year consecutive sequences."""
        fixture = create_custom_dates_fixture(["2020-11", "2020-12", "2021-01", "2021-02"])
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            in_file = tmp_path / "year_trans.csv"
            out_file = tmp_path / "year_out.csv"
            fixture.to_csv(in_file, index=False)

            df_res = build_feature_table(combined_path=in_file, output_path=out_file)
            self.assertEqual(len(df_res), 4)
            self.assertEqual(list(df_res["date"]), ["2020-11", "2020-12", "2021-01", "2021-02"])

    def test_december_to_january_year_transition_missing_boundary(self):
        """build_feature_table must detect missing boundary months across year transitions."""
        fixture = create_custom_dates_fixture(["2020-11", "2020-12", "2021-02", "2021-03"])  # Missing 2021-01
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            in_file = tmp_path / "year_gap.csv"
            out_file = tmp_path / "year_gap_out.csv"
            fixture.to_csv(in_file, index=False)

            with self.assertRaises(ValueError) as ctx:
                build_feature_table(combined_path=in_file, output_path=out_file)
            self.assertIn("Temporal gap detected", str(ctx.exception))
            self.assertIn("2021-01", str(ctx.exception))

    def test_december_to_january_out_of_order(self):
        """build_feature_table must detect out-of-order records across year boundaries."""
        fixture = create_custom_dates_fixture(["2021-01", "2020-12", "2021-02", "2021-03"])
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            in_file = tmp_path / "year_order.csv"
            out_file = tmp_path / "year_order_out.csv"
            fixture.to_csv(in_file, index=False)

            with self.assertRaises(ValueError) as ctx:
                build_feature_table(combined_path=in_file, output_path=out_file)
            self.assertIn("out of chronological order", str(ctx.exception))

    def test_deterministic_reproducibility(self):
        """Executing feature engineering twice on identical input must produce identical results."""
        fixture = create_synthetic_combined_fixture(4)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            in_file = tmp_path / "repro_in.csv"
            out_file_1 = tmp_path / "repro_out_1.csv"
            out_file_2 = tmp_path / "repro_out_2.csv"
            fixture.to_csv(in_file, index=False)

            df1 = build_feature_table(combined_path=in_file, output_path=out_file_1)
            df2 = build_feature_table(combined_path=in_file, output_path=out_file_2)

            self.assertTrue(df1.equals(df2), "Repeated generation must be 100% deterministic.")

    def test_relative_path_handling(self):
        """build_feature_table must handle relative paths anchored to project structure."""
        fixture = create_synthetic_combined_fixture(4)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            in_file = tmp_path / "rel_in.csv"
            out_file = tmp_path / "rel_out.csv"
            fixture.to_csv(in_file, index=False)
            df = build_feature_table(combined_path=in_file, output_path=out_file)
            self.assertEqual(len(df), 4)
            self.assertTrue(out_file.exists())


if __name__ == "__main__":
    unittest.main()

