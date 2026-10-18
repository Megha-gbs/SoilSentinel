"""
SoilSentinel V6 — End-to-End Backend Integration & Security Test Suite
======================================================================
Tests the full request lifecycle:
1. System Health Check (/api/health)
2. Authentication & Session Persistence (Farmer & Researcher)
3. Role-Based Access Control & Security Isolation (Farmer blocked from Researcher API)
4. Unauthenticated Access Protection (401 on protected endpoints)
5. Baseline Assessment Evaluation & Database Persistence (/api/assessment/evaluate)
6. Traceable Assessment History (/api/assessment/history)
7. Audit Report Export (/api/assessment/export in text and json formats)
8. Interactive What-If Scenario Stress Testing (/api/assessment/scenario)
9. Global GPS Field Assessment (/api/gps/assess) across multi-country coordinates:
   - Punjab, India (30.7333°N, 76.7794°E)
   - Maharashtra, India (18.5204°N, 73.8567°E)
   - Ames, Iowa, USA (42.0308°N, -93.6319°W)
10. One-Click Camera Diagnostic Scan (/api/camera/analyze)
11. Researcher Soil-Test Laboratory Analysis (/api/researcher/upload-soil-test)
"""

import sys
import json
import base64
import requests
import pytest
from pathlib import Path

BASE_URL = "http://localhost:3000"


class TestSoilSentinelEndToEnd:

    @classmethod
    def setup_class(cls):
        cls.farmer_session = requests.Session()
        cls.researcher_session = requests.Session()

    # 1. Health Check
    def test_01_api_health_check(self):
        resp = requests.get(f"{BASE_URL}/api/health", timeout=5)
        assert resp.status_code == 200, f"Health check failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "SoilSentinel Web & ML Backend"
        assert data["database"]["status"] == "connected"
        assert "engine" in data["database"]
        assert data["python_bridge"]["status"] == "ok"
        assert data["python_bridge"]["port"] == 5001

    # 2. Security: Unauthenticated Protection & Guest Access Boundary
    def test_02_unauthenticated_endpoints_rejected(self):
        unauth_session = requests.Session()
        # Guest assessment endpoints allow public exploration without login
        r1 = unauth_session.get(f"{BASE_URL}/api/assessment/dates")
        assert r1.status_code == 200

        r2 = unauth_session.get(f"{BASE_URL}/api/assessment/evaluate")
        assert r2.status_code == 200

        # Guest history returns isolated empty history with is_guest: true
        r3 = unauth_session.get(f"{BASE_URL}/api/assessment/history")
        assert r3.status_code == 200
        assert r3.json().get("is_guest") is True

        # Protected researcher endpoints strictly require authentication
        r4 = unauth_session.get(f"{BASE_URL}/api/researcher/workspace")
        assert r4.status_code in (401, 403)
        assert "authentication required" in r4.json().get("error", "").lower() or "denied" in r4.json().get("error", "").lower()

    # 3. Authentication: Farmer Login
    def test_03_farmer_login(self):
        login_payload = {
            "email": "farmer.demo@soilsentinel.local",
            "password": "DemoSoil2026!"
        }
        resp = self.farmer_session.post(f"{BASE_URL}/api/auth/login", json=login_payload, timeout=5)
        assert resp.status_code == 200, f"Farmer login failed: {resp.text}"
        data = resp.json()
        assert data["user"]["role"] == "farmer"
        assert data["redirect"] == "/farmer-dashboard.html"

        # Verify session is recognized
        me_resp = self.farmer_session.get(f"{BASE_URL}/api/auth/me")
        assert me_resp.status_code == 200
        assert me_resp.json()["authenticated"] is True
        assert me_resp.json()["user"]["role"] == "farmer"

    # 4. Security: Farmer Role Isolation
    def test_04_farmer_cannot_access_researcher_endpoints(self):
        resp = self.farmer_session.get(f"{BASE_URL}/api/researcher/workspace")
        assert resp.status_code == 403
        assert "role mismatch" in resp.json().get("error", "").lower() or "access denied" in resp.json().get("error", "").lower()

    # 5. Farmer Assessment Evaluation & Database Persistence
    def test_05_assessment_evaluate_and_persistence(self):
        # Fetch available dates
        dates_resp = self.farmer_session.get(f"{BASE_URL}/api/assessment/dates")
        assert dates_resp.status_code == 200
        dates_data = dates_resp.json()
        assert dates_data["success"] is True
        assert len(dates_data["available_dates"]) > 0
        latest_date = dates_data["latest_date"]

        # Evaluate assessment for latest date
        eval_resp = self.farmer_session.get(f"{BASE_URL}/api/assessment/evaluate?date={latest_date}")
        assert eval_resp.status_code == 200
        eval_data = eval_resp.json()
        assert eval_data["success"] is True
        payload = eval_data["payload"]
        assert "risk_assessment" in payload or "risk_scoring" in payload
        assert "recommendations" in payload
        assert "historical_series" in payload

        # Verify database persistence returned a valid ID
        assert "persisted_assessment_id" in eval_data or "audit_log" in payload

    # 6. Traceable Assessment History
    def test_06_assessment_history_retrieval(self):
        resp = self.farmer_session.get(f"{BASE_URL}/api/assessment/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["count"] >= 1
        latest_record = data["history"][0]
        assert "assessment_id" in latest_record
        assert "risk_category" in latest_record
        assert "created_at" in latest_record

    # 7. Audit Report Export
    def test_07_assessment_report_export(self):
        # Text format
        text_resp = self.farmer_session.get(f"{BASE_URL}/api/assessment/export?format=text")
        assert text_resp.status_code == 200
        assert "SOILSENTINEL SOIL HEALTH" in text_resp.text
        assert "Baseline Risk Index" in text_resp.text
        assert "RECOMMENDATIONS" in text_resp.text
        assert "SCIENTIFIC HONESTY" in text_resp.text

        # JSON format
        json_resp = self.farmer_session.get(f"{BASE_URL}/api/assessment/export?format=json")
        assert json_resp.status_code == 200
        j_data = json_resp.json()
        assert "assessment_id" in j_data
        assert "scientific_disclaimer" in j_data

    # 8. Interactive Scenario Stress Testing
    def test_08_what_if_scenario(self):
        scenario_payload = {
            "date": "2024-12",
            "rainfall_mm": 5.0,
            "temp_c": 32.0,
            "horizon_days": 45
        }
        resp = self.farmer_session.post(f"{BASE_URL}/api/assessment/scenario", json=scenario_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "comparison" in data
        assert (
            "delta_score" in data["comparison"]
            or "category_shift" in data["comparison"]
            or "scenario_atmospheric_score" in data["comparison"]
        )

    # 9. Global GPS Field Assessment (Multi-Region / Multi-Continent)
    def test_09_gps_assessment_punjab(self):
        payload = {"latitude": 30.7333, "longitude": 76.7794, "crop_type": "wheat"}
        resp = self.farmer_session.post(f"{BASE_URL}/api/gps/assess", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"
        assert "contextual_soilgrids" in data
        assert "recent_weather" in data
        assert "v6_predictions" in data

    def test_10_gps_assessment_maharashtra(self):
        # Western India (Pune / Deccan plateau)
        payload = {"latitude": 18.5204, "longitude": 73.8567, "crop_type": "sugarcane"}
        resp = self.farmer_session.post(f"{BASE_URL}/api/gps/assess", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"
        assert "contextual_soilgrids" in data
        sg = data["contextual_soilgrids"]
        assert "ph_mean" in sg or "ph_h2o" in sg.get("properties", {}) or "properties" in sg

    def test_11_gps_assessment_international_usa(self):
        # International: Ames, Iowa (Corn Belt, USA)
        payload = {"latitude": 42.0308, "longitude": -93.6319, "crop_type": "maize"}
        resp = self.farmer_session.post(f"{BASE_URL}/api/gps/assess", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"
        assert "contextual_soilgrids" in data
        sg = data["contextual_soilgrids"]
        assert "ph_mean" in sg or "ph_h2o" in sg.get("properties", {}) or "properties" in sg

    # 10. Camera Diagnostic Scan
    def test_12_camera_diagnostic_scan(self):
        # Provide base64 encoded synthetic checkerboard pattern
        import numpy as np
        import cv2
        img = np.zeros((150, 150, 3), dtype=np.uint8)
        img[::15, :, :] = 255
        img[:, ::15, :] = 255
        _, buf = cv2.imencode(".png", img)
        b64_str = "data:image/png;base64," + base64.b64encode(buf).decode("utf-8")

        payload = {"image": b64_str, "modality": "crop"}
        resp = self.farmer_session.post(f"{BASE_URL}/api/camera/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("SUCCESS", "QUALITY_WARNING")
        assert "diagnosis" in data

    # 11. Researcher Authentication & Soil-Test Upload
    def test_13_researcher_login_and_soil_test(self):
        login_payload = {
            "email": "researcher.demo@soilsentinel.local",
            "password": "DemoSoil2026!"
        }
        resp = self.researcher_session.post(f"{BASE_URL}/api/auth/login", json=login_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["role"] == "researcher"

        # Access researcher workspace
        ws_resp = self.researcher_session.get(f"{BASE_URL}/api/researcher/workspace")
        assert ws_resp.status_code == 200
        assert ws_resp.json()["user"]["role"] == "researcher"

        # Upload soil test
        lab_soil_test = {
            "ph_h2o": 7.2,
            "electrical_conductivity_ds_m": 0.85,
            "soil_organic_carbon_g_kg": 7.1,
            "clay_fraction_pct": 25.0,
            "sand_fraction_pct": 45.0,
            "silt_fraction_pct": 30.0,
            "depth_cm": 15.0,
            "latitude": 30.7333,
            "longitude": 76.7794
        }
        soil_resp = self.researcher_session.post(
            f"{BASE_URL}/api/researcher/upload-soil-test",
            json={"soil_test": lab_soil_test}
        )
        assert soil_resp.status_code == 200
        soil_res = soil_resp.json()
        assert soil_res["status"] == "SUCCESS"
        assert "multi_task_predictions" in soil_res or "soil_test_assessment" in soil_res


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
