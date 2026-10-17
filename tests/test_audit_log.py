"""
Unit Tests for Soil Sentinel Prediction Audit Logging.

Verifies:
1. Successful prediction logging (COMPLETE status, valid numeric score, correct category).
2. Provisional prediction logging (PROVISIONAL_PARTIAL_HISTORY status, allow_partial=True).
3. Strict-mode failure logging (INSUFFICIENT_HISTORY status, empty score, UNKNOWN category).
4. Repeated log appends (header written only on creation, records appended cleanly).
5. CSV field schema consistency across all rows.
6. End-to-end integration with predict_from_csv and predict_dataframe (no duplicate entries).
7. Privacy check: no PII, API keys, or raw internal feature payloads stored.
"""

import csv
import sys
import tempfile
import unittest
from pathlib import Path
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Model.audit_log import (
    create_audit_entry,
    write_audit_entries,
    log_prediction_single,
    log_predictions_batch,
    read_audit_log,
    AUDIT_LOG_FIELDS,
    ENGINE_VERSION,
    INDEX_NAME,
)
from src.Model.predict import (
    predict_record,
    predict_dataframe,
    predict_from_csv,
)


class TestAuditLogCreation(unittest.TestCase):
    """Test creation and formatting of single audit log entry dictionaries."""

    def test_successful_prediction_entry(self):
        pred = {
            "date": "2023-07",
            "region": "Indo-Gangetic Agricultural Plains / Punjab",
            "score": 45.50,
            "risk_category": "Medium",
            "status": "COMPLETE",
        }
        entry = create_audit_entry(pred, source_id="test_run", allow_partial=True)

        self.assertEqual(entry["input_date"], "2023-07")
        self.assertEqual(entry["location_id"], "Indo-Gangetic Agricultural Plains / Punjab")
        self.assertEqual(entry["index_name"], INDEX_NAME)
        self.assertEqual(entry["engine_version"], ENGINE_VERSION)
        self.assertEqual(entry["source_id"], "test_run")
        self.assertEqual(entry["allow_partial"], True)
        self.assertEqual(entry["status"], "COMPLETE")
        self.assertEqual(entry["score"], "45.50")
        self.assertEqual(entry["risk_category"], "Medium")
        self.assertIn("T", entry["timestamp_utc"])  # ISO 8601 format

    def test_provisional_prediction_entry(self):
        pred = {
            "date": "2020-01",
            "region": "Indo-Gangetic Agricultural Plains / Punjab",
            "score": 33.49,
            "risk_category": "Low",
            "status": "PROVISIONAL_PARTIAL_HISTORY",
        }
        entry = create_audit_entry(pred, source_id="data/feature_table.csv", allow_partial=True)

        self.assertEqual(entry["status"], "PROVISIONAL_PARTIAL_HISTORY")
        self.assertEqual(entry["score"], "33.49")
        self.assertEqual(entry["allow_partial"], True)

    def test_strict_mode_insufficient_history_entry(self):
        """Strict-mode failure must be logged with empty score and UNKNOWN category."""
        pred = {
            "date": "2020-01",
            "region": "Indo-Gangetic Agricultural Plains / Punjab",
            "score": None,
            "risk_category": "UNKNOWN",
            "status": "INSUFFICIENT_HISTORY",
        }
        entry = create_audit_entry(pred, source_id="strict_run", allow_partial=False)

        self.assertEqual(entry["status"], "INSUFFICIENT_HISTORY")
        self.assertEqual(entry["score"], "")  # Preserved as null / empty
        self.assertEqual(entry["risk_category"], "UNKNOWN")
        self.assertEqual(entry["allow_partial"], False)

    def test_empty_and_non_numeric_score_handled_safely(self):
        """create_audit_entry must never crash on empty string or non-numeric score."""
        for bad_score in ["", "   ", "N/A", "nan", None]:
            pred = {
                "date": "2020-01",
                "region": "Punjab",
                "score": bad_score,
                "risk_category": "UNKNOWN",
                "status": "INVALID_INPUT",
            }
            entry = create_audit_entry(pred, source_id="robustness_test")
            self.assertEqual(entry["score"], "", f"Failed for bad_score: {bad_score}")


class TestAuditLogCSVWriter(unittest.TestCase):
    """Test writing and appending audit records to disk."""

    def test_repeated_appends_and_header_preservation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "logs" / "audit.csv"

            # Batch 1: Write 2 entries
            entry1 = {
                "timestamp_utc": "2026-10-14T04:00:00Z",
                "input_date": "2023-01",
                "location_id": "Punjab",
                "index_name": INDEX_NAME,
                "engine_version": ENGINE_VERSION,
                "source_id": "test",
                "allow_partial": True,
                "status": "COMPLETE",
                "score": "30.00",
                "risk_category": "Low",
            }
            entry2 = {
                "timestamp_utc": "2026-10-14T04:00:01Z",
                "input_date": "2023-02",
                "location_id": "Punjab",
                "index_name": INDEX_NAME,
                "engine_version": ENGINE_VERSION,
                "source_id": "test",
                "allow_partial": True,
                "status": "COMPLETE",
                "score": "40.00",
                "risk_category": "Medium",
            }

            write_audit_entries([entry1, entry2], log_path=log_path)
            self.assertTrue(log_path.exists())

            # Batch 2: Append 1 more entry
            entry3 = {
                "timestamp_utc": "2026-10-14T04:00:02Z",
                "input_date": "2023-03",
                "location_id": "Punjab",
                "index_name": INDEX_NAME,
                "engine_version": ENGINE_VERSION,
                "source_id": "test",
                "allow_partial": True,
                "status": "COMPLETE",
                "score": "50.00",
                "risk_category": "Medium",
            }
            write_audit_entries([entry3], log_path=log_path)

            # Read raw lines to verify header is written only once
            with open(log_path, mode="r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]

            # Total lines should be 1 header + 3 entries = 4 lines
            self.assertEqual(len(lines), 4)
            self.assertEqual(lines[0], ",".join(AUDIT_LOG_FIELDS))

            # Verify field count in every row
            reader = csv.reader(lines)
            for row in reader:
                self.assertEqual(len(row), len(AUDIT_LOG_FIELDS))


class TestPredictionWorkflowAuditIntegration(unittest.TestCase):
    """Test that predict.py seamlessly records audit entries without duplication."""

    def test_predict_record_with_audit_logging(self):
        record = {
            "date": "2024-05",
            "region": "Punjab",
            "soil_moisture_rootzone_fraction": 0.40,
            "soil_temperature_layer1_c": 32.0,
            "topsoil_soc_g_kg": 12.95,
            "topsoil_ph_mean": 6.55,
            "precipitation_rolling_3m_mean_mm_day": 2.0,
            "precipitation_mm_day": 1.5,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.csv"
            pred = predict_record(record, audit_log_path=log_path, source_id="single_test")

            self.assertIsNotNone(pred["score"])
            self.assertTrue(log_path.exists())

            df_log = pd.read_csv(log_path)
            self.assertEqual(len(df_log), 1)
            self.assertEqual(df_log.loc[0, "input_date"], "2024-05")
            self.assertEqual(df_log.loc[0, "status"], "COMPLETE")
            self.assertEqual(df_log.loc[0, "source_id"], "single_test")

    def test_predict_from_csv_no_duplicate_audit_entries(self):
        feature_csv = PROJECT_ROOT / "data" / "feature_table.csv"
        self.assertTrue(feature_csv.exists())

        with tempfile.TemporaryDirectory() as tmpdir:
            out_pred = Path(tmpdir) / "preds.csv"
            out_audit = Path(tmpdir) / "audit.csv"

            # Execute batch prediction from CSV
            predict_from_csv(
                input_path=feature_csv,
                output_path=out_pred,
                allow_partial=True,
                audit_log_path=out_audit
            )

            self.assertTrue(out_pred.exists())
            self.assertTrue(out_audit.exists())

            df_preds = pd.read_csv(out_pred)
            df_audit = pd.read_csv(out_audit)

            # Exactly 60 predictions and exactly 60 audit entries
            self.assertEqual(len(df_preds), 60)
            self.assertEqual(len(df_audit), 60)

            # Verify schema of audit log
            self.assertEqual(list(df_audit.columns), AUDIT_LOG_FIELDS)

            # First two records must reflect provisional status in both files
            self.assertEqual(df_audit.loc[0, "status"], "PROVISIONAL_PARTIAL_HISTORY")
            self.assertEqual(df_audit.loc[1, "status"], "PROVISIONAL_PARTIAL_HISTORY")
            self.assertEqual(df_audit.loc[2, "status"], "COMPLETE")

            # Check that strict mode logs INSUFFICIENT_HISTORY
            out_audit_strict = Path(tmpdir) / "audit_strict.csv"
            predict_from_csv(
                input_path=feature_csv,
                output_path=Path(tmpdir) / "preds_strict.csv",
                allow_partial=False,
                audit_log_path=out_audit_strict
            )
            df_strict_audit = pd.read_csv(out_audit_strict, keep_default_na=False)
            self.assertEqual(df_strict_audit.loc[0, "status"], "INSUFFICIENT_HISTORY")
            self.assertEqual(df_strict_audit.loc[0, "score"], "")
            self.assertEqual(df_strict_audit.loc[0, "risk_category"], "UNKNOWN")


class TestAuditLogPrivacy(unittest.TestCase):
    """Verify that sensitive data and unnecessary raw records are excluded."""

    def test_no_sensitive_or_raw_records_stored(self):
        pred = {
            "date": "2023-08",
            "region": "Punjab",
            "score": 25.0,
            "risk_category": "Low",
            "status": "COMPLETE",
            "api_key": "SECRET_KEY_12345",
            "user_email": "farmer@example.com",
            "raw_satellite_dump": [1, 2, 3, 4],
        }
        entry = create_audit_entry(pred)

        for sensitive_key in ["api_key", "user_email", "raw_satellite_dump"]:
            self.assertNotIn(sensitive_key, entry)
class TestAuditLogCumulativeDesignAndHistoricalDistinction(unittest.TestCase):
    """Verify that audit log is cumulative by design and new records can be isolated from historical records."""

    def test_distinguish_newly_generated_from_historical_records(self):
        """Audit log appends cumulatitively; newly generated records are distinguishable by timestamp and source_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.csv"

            # 1. Populate log with historical records from a previous year/session
            historical_entries = [
                {
                    "timestamp_utc": "2024-01-15T10:00:00+00:00",
                    "input_date": "2023-11",
                    "location_id": "Punjab",
                    "index_name": INDEX_NAME,
                    "engine_version": ENGINE_VERSION,
                    "source_id": "historical_batch_2024",
                    "allow_partial": True,
                    "status": "COMPLETE",
                    "score": "38.20",
                    "risk_category": "Medium",
                },
                {
                    "timestamp_utc": "2024-01-15T10:00:01+00:00",
                    "input_date": "2023-12",
                    "location_id": "Punjab",
                    "index_name": INDEX_NAME,
                    "engine_version": ENGINE_VERSION,
                    "source_id": "historical_batch_2024",
                    "allow_partial": True,
                    "status": "COMPLETE",
                    "score": "41.50",
                    "risk_category": "Medium",
                },
            ]
            write_audit_entries(historical_entries, log_path=log_path)
            initial_count = len(pd.read_csv(log_path))
            self.assertEqual(initial_count, 2)

            # 2. Record run start cutoff
            run_cutoff_iso = "2026-10-16T12:00:00+00:00"

            # 3. Append newly generated execution batch
            new_batch_id = "live_monitoring_run_20261016"
            new_pred_1 = {
                "date": "2024-11",
                "region": "Punjab",
                "score": 32.10,
                "risk_category": "Low",
                "status": "COMPLETE",
            }
            new_pred_2 = {
                "date": "2024-12",
                "region": "Punjab",
                "score": 35.80,
                "risk_category": "Medium",
                "status": "COMPLETE",
            }
            log_predictions_batch(
                predictions=[new_pred_1, new_pred_2],
                source_id=new_batch_id,
                allow_partial=True,
                log_path=log_path
            )

            # 4. Read complete cumulative log
            df_full = pd.read_csv(log_path)
            self.assertEqual(len(df_full), 4, "Total entries must be sum of historical (2) + new (2)")

            # 5. Distinguish new records by source_id
            df_new_by_source = df_full[df_full["source_id"] == new_batch_id]
            self.assertEqual(len(df_new_by_source), 2)
            self.assertEqual(list(df_new_by_source["input_date"]), ["2024-11", "2024-12"])

            # 6. Distinguish new records by timestamp
            df_new_by_time = df_full[df_full["timestamp_utc"] >= run_cutoff_iso]
            self.assertEqual(len(df_new_by_time), 2)

            # 7. Verify historical records remain identical and uncorrupted
            df_historical = df_full[df_full["source_id"] == "historical_batch_2024"]
            self.assertEqual(len(df_historical), 2)
            self.assertEqual(df_historical.iloc[0]["score"], 38.20)
            self.assertEqual(df_historical.iloc[1]["score"], 41.50)


class TestAuditLogTraceabilityAndLegacyMigration(unittest.TestCase):
    """Test assessment_id, recommendation_ids formatting, and legacy CSV backward compatibility."""

    def test_traceability_fields_in_create_audit_entry(self):
        """create_audit_entry must record assessment_id and format recommendation_ids cleanly."""
        pred = {
            "date": "2024-12",
            "region": "Punjab",
            "score": 47.87,
            "risk_category": "Medium",
            "status": "COMPLETE",
        }
        rec_ids = ["REC-PRECIP-CRI", "REC-MOISTURE-HIG", "REC-SOC-HIG"]
        entry = create_audit_entry(
            prediction=pred,
            source_id="dashboard_service",
            assessment_id="ASM-2024-12-TEST001",
            recommendation_ids=rec_ids
        )

        self.assertEqual(entry["assessment_id"], "ASM-2024-12-TEST001")
        self.assertEqual(entry["recommendation_ids"], "REC-PRECIP-CRI;REC-MOISTURE-HIG;REC-SOC-HIG")
        self.assertEqual(entry["score"], "47.87")

    def test_legacy_audit_log_migration_and_reading(self):
        """Appending to an existing 10-column legacy audit CSV safely upgrades schema without corrupting records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit_legacy.csv"

            # 1. Write legacy 10-column CSV
            legacy_header = "timestamp_utc,input_date,location_id,index_name,engine_version,source_id,allow_partial,status,score,risk_category\n"
            legacy_row = "2024-01-01T00:00:00+00:00,2023-12,Punjab,TestIndex,v1.0.0,legacy_src,True,COMPLETE,42.50,Medium\n"
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(legacy_header)
                f.write(legacy_row)

            # 2. Read with read_audit_log before migration (must add empty strings for missing cols)
            df_legacy = read_audit_log(log_path)
            self.assertEqual(len(df_legacy), 1)
            self.assertIn("assessment_id", df_legacy.columns)
            self.assertIn("recommendation_ids", df_legacy.columns)
            self.assertEqual(df_legacy.loc[0, "assessment_id"], "")

            # 3. Append new entry with assessment_id and recommendation_ids
            new_pred = {
                "date": "2024-01",
                "region": "Punjab",
                "score": 35.0,
                "risk_category": "Medium",
                "status": "COMPLETE",
            }
            log_prediction_single(
                prediction=new_pred,
                source_id="test_migration",
                log_path=log_path,
                assessment_id="ASM-2024-01-NEW",
                recommendation_ids=["REC-01", "REC-02"]
            )

            # 4. Read back and verify both legacy and new records
            df_combined = pd.read_csv(log_path, keep_default_na=False)
            self.assertEqual(len(df_combined), 2)
            self.assertEqual(list(df_combined.columns), AUDIT_LOG_FIELDS)

            # Legacy row: preserved data, empty assessment_id/recommendation_ids
            self.assertEqual(df_combined.loc[0, "input_date"], "2023-12")
            self.assertEqual(float(df_combined.loc[0, "score"]), 42.50)
            self.assertEqual(df_combined.loc[0, "assessment_id"], "")
            self.assertEqual(df_combined.loc[0, "recommendation_ids"], "")

            # New row: populated assessment_id and recommendation_ids
            self.assertEqual(df_combined.loc[1, "input_date"], "2024-01")
            self.assertEqual(df_combined.loc[1, "assessment_id"], "ASM-2024-01-NEW")
            self.assertEqual(df_combined.loc[1, "recommendation_ids"], "REC-01;REC-02")


if __name__ == "__main__":
    unittest.main()
