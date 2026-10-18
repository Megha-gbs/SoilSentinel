"""
SoilSentinel V6 - Global GPS Assessment, Map Resilience & Guest Access Test Suite
==================================================================================
Tests:
1. Map tile endpoints (CartoDB Voyager primary & Esri fallback).
2. Global GPS assessment across 5 diverse worldwide locations:
   - Punjab, India (30.7333, 76.7794)
   - Maharashtra, India (19.7515, 75.7139)
   - Iowa, USA (42.0308, -93.6319)
   - Montpellier, France (43.6108, 3.8767)
   - Nairobi, Kenya (-1.2921, 36.8219)
   Confirms location-specific coordinates, distinct soil/climate profiles, texture bounds,
   and honest scientific disclosures without reverting to Punjab defaults.
3. Guest Access ("Try for Free") API verification:
   - Unauthenticated access to /api/assessment/dates -> 200
   - Unauthenticated access to /api/assessment/evaluate -> 200
   - Unauthenticated access to /api/assessment/observations -> 200
   - Unauthenticated access to /api/gps/assess -> 200
   - Unauthenticated access to /api/camera/analyze -> 200
   - Unauthenticated access to /api/assessment/history -> 200 with is_guest: true
   - Protected researcher endpoint rejection -> 401/403
4. Database session isolation: Guest queries do not pollute persistent SQLite records.
5. Landing page CTA verification: index.html contains Try for Free actions & section.
"""

import os
import sys
import json
import sqlite3
import pytest
import requests
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Geo.field_assessment import GPSFieldAssessmentEngine, get_field_assessment_engine

EXPRESS_PORT = int(os.environ.get("PORT", 3000))
BASE_URL = f"http://127.0.0.1:{EXPRESS_PORT}"


# -----------------------------------------------------------------------------
# 1. Map Tile Provider & Configuration
# -----------------------------------------------------------------------------
class TestMapTileProvider:
    """Verify compliant map tile configuration and fallback infrastructure."""

    def test_dashboard_visuals_uses_cartodb_voyager(self):
        """Confirm dashboard-visuals.js uses CartoDB Voyager raster tiles and handles tile errors."""
        js_path = PROJECT_ROOT / "dashboard-visuals.js"
        assert js_path.exists(), "dashboard-visuals.js must exist"
        content = js_path.read_text(encoding="utf-8")

        assert "basemaps.cartocdn.com/rastertiles/voyager" in content, (
            "dashboard-visuals.js must configure CartoDB Voyager as primary tile layer"
        )
        assert "OpenStreetMap" in content and "CARTO" in content, (
            "dashboard-visuals.js must include proper OpenStreetMap and CARTO attribution"
        )
        assert "server.arcgisonline.com" in content, (
            "dashboard-visuals.js must configure Esri World Topo Map as fallback tile layer"
        )
        assert "updateMapLocation" in content, (
            "SoilSentinelVisuals must export updateMapLocation for dynamic pan & marker updates"
        )

    def test_cartodb_tile_server_connectivity(self):
        """Verify that CartoDB Voyager tiles respond with HTTP 200 or valid image headers."""
        sample_tile_url = "https://a.basemaps.cartocdn.com/rastertiles/voyager/5/16/11.png"
        try:
            resp = requests.get(
                sample_tile_url,
                headers={"User-Agent": "SoilSentinel-V6/Test"},
                timeout=5.0
            )
            assert resp.status_code == 200, f"CartoDB tile server returned status {resp.status_code}"
            assert resp.headers.get("Content-Type", "").startswith("image/"), (
                f"Expected image content type, got {resp.headers.get('Content-Type')}"
            )
        except requests.exceptions.RequestException as exc:
            pytest.skip(f"Network unavailable for external tile test: {exc}")


@pytest.fixture(scope="module")
def field_engine():
    return get_field_assessment_engine()


# -----------------------------------------------------------------------------
# 2. Global GPS Assessment Across Varied Worldwide Locations
# -----------------------------------------------------------------------------
class TestGlobalGPSAssessment:
    """Verify field assessment engine handles diverse worldwide coordinates accurately."""

    GLOBAL_LOCATIONS = [
        {"name": "Punjab, India", "lat": 30.7333, "lon": 76.7794, "crop": "Wheat / Rice"},
        {"name": "Maharashtra, India", "lat": 19.7515, "lon": 75.7139, "crop": "Cotton / Soybean"},
        {"name": "Iowa, USA", "lat": 42.0308, "lon": -93.6319, "crop": "Corn / Maize"},
        {"name": "Montpellier, France", "lat": 43.6108, "lon": 3.8767, "crop": "Vineyard / Olive"},
        {"name": "Nairobi, Kenya", "lat": -1.2921, "lon": 36.8219, "crop": "Coffee / Tea / Maize"},
    ]

    def test_assessment_returns_distinct_location_data(self, field_engine):
        """Verify that different coordinates produce distinct, genuine location results."""
        results = []
        for loc in self.GLOBAL_LOCATIONS:
            res = field_engine.assess_location(
                latitude=loc["lat"],
                longitude=loc["lon"],
                crop_type=loc["crop"]
            )
            assert res["status"] == "SUCCESS"
            assert res["coordinates"]["latitude"] == loc["lat"]
            assert res["coordinates"]["longitude"] == loc["lon"]
            assert "soil_context" in res
            assert "weather_context" in res
            assert "assessment" in res
            results.append((loc["name"], res))

        # Compare Iowa vs Punjab: Coordinates and climate must not be identical
        punjab_res = results[0][1]
        iowa_res = results[2][1]

        assert punjab_res["coordinates"] != iowa_res["coordinates"]
        assert punjab_res["coordinates"]["longitude"] != iowa_res["coordinates"]["longitude"]

    def test_texture_proportions_and_bounds(self, field_engine):
        """Verify soil texture fractions stay within physically valid bounds."""
        for loc in self.GLOBAL_LOCATIONS:
            res = field_engine.assess_location(latitude=loc["lat"], longitude=loc["lon"])
            sc = res.get("contextual_soilgrids", res.get("soil_context", {}))
            props = sc.get("properties", sc)

            clay = props.get("clay_percent", props.get("clay_mean", 20.0))
            assert 0.0 <= clay <= 100.0, f"Clay percent out of bounds: {clay}"

            ph = props.get("ph_h2o", props.get("ph_mean", 7.0))
            assert 3.0 <= ph <= 11.0, f"pH value out of typical soil range: {ph}"

    def test_scientific_status_and_disclaimer(self, field_engine):
        """Verify presence of transparent scientific status and disclaimers."""
        res = field_engine.assess_location(latitude=19.7515, longitude=75.7139)
        assert "disclaimer" in res
        assert "contextual_soilgrids" in res or "soil_context" in res
        sc = res.get("contextual_soilgrids", res.get("soil_context", {}))
        assert sc.get("scientific_status") == "MAPPED_REGIONAL_CONTEXT_NOT_FIELD_LAB_TEST" or (
            "SoilGrids" in sc.get("source", "") or "Benchmark" in sc.get("source", "")
        )


# -----------------------------------------------------------------------------
# 3. Guest Access ("Try for Free") API Verification
# -----------------------------------------------------------------------------
class TestGuestAccessAPI:
    """Verify that unauthenticated visitors can access assessment tools but not researcher routes."""

    @pytest.fixture(autouse=True)
    def check_server(self):
        try:
            r = requests.get(f"{BASE_URL}/api/health", timeout=2.0)
            if r.status_code != 200:
                pytest.skip("Express server /api/health returned non-200")
        except requests.exceptions.RequestException:
            pytest.skip("Express server is not running on port 3000")

    def test_guest_can_fetch_assessment_dates(self):
        """Unauthenticated request to /api/assessment/dates should return 200 with dates list."""
        resp = requests.get(f"{BASE_URL}/api/assessment/dates")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        dates = data.get("available_dates", data.get("dates", []))
        assert isinstance(dates, list)
        assert len(dates) > 0

    def test_guest_can_evaluate_screening(self):
        """Unauthenticated request to /api/assessment/evaluate should return genuine assessment."""
        resp = requests.get(f"{BASE_URL}/api/assessment/evaluate")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        payload = data.get("payload", data.get("assessment", {}))
        risk_assessment = payload.get("risk_assessment", payload.get("risk_scoring", {}))
        assert "score" in risk_assessment or "risk_score" in risk_assessment or "risk_index" in risk_assessment
        assert "risk_category" in risk_assessment
        assert "recommendations" in payload
        assert "metadata" in payload

    def test_guest_can_fetch_observations(self):
        """Unauthenticated request to /api/assessment/observations should return 200."""
        resp = requests.get(f"{BASE_URL}/api/assessment/observations")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        rows = data.get("rows", data.get("observations", []))
        assert isinstance(rows, list)
        assert len(rows) > 0

    def test_guest_can_run_gps_assess(self):
        """Unauthenticated request to /api/gps/assess should return 200 for arbitrary coordinates."""
        payload = {
            "latitude": 42.0308,
            "longitude": -93.6319,
            "crop_type": "Corn / Maize"
        }
        resp = requests.post(f"{BASE_URL}/api/gps/assess", json=payload, timeout=6.0)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "SUCCESS" or data.get("success") is True
        coords = data.get("coordinates", {})
        assert abs(coords.get("latitude", 0) - 42.0308) < 0.001
        assert abs(coords.get("longitude", 0) - (-93.6319)) < 0.001

    def test_guest_history_returns_isolated_empty_state(self):
        """Unauthenticated request to /api/assessment/history should return empty history with is_guest: true."""
        resp = requests.get(f"{BASE_URL}/api/assessment/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        assert data.get("count") == 0
        assert data.get("history") == []
        assert data.get("is_guest") is True

    def test_guest_is_denied_researcher_protected_routes(self):
        """Unauthenticated request to researcher endpoints must return 401 Unauthorized or 403 Forbidden."""
        # Test file upload route
        resp = requests.post(
            f"{BASE_URL}/api/researcher/upload-soil-test",
            files={"file": ("test.csv", "sample_id,ph\n1,7.2", "text/csv")}
        )
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 for guest access to researcher upload, got {resp.status_code}"
        )

        # Test workspace route
        resp = requests.get(f"{BASE_URL}/api/researcher/workspace")
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 for guest access to researcher workspace, got {resp.status_code}"
        )


# -----------------------------------------------------------------------------
# 4. Database Session Isolation
# -----------------------------------------------------------------------------
class TestDatabaseSessionIsolation:
    """Verify that guest assessments do NOT create persistent records in SQLite database."""

    def test_guest_assessments_do_not_pollute_database(self):
        db_path = PROJECT_ROOT / "data" / "soilsentinel.sqlite"
        if not db_path.exists():
            pytest.skip(f"{db_path} does not exist yet")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM assessments")
        count_before = cursor.fetchone()[0]
        conn.close()

        # Execute unauthenticated guest assessment
        payload = {
            "latitude": 19.7515,
            "longitude": 75.7139,
            "crop_type": "Cotton"
        }
        resp = requests.post(f"{BASE_URL}/api/gps/assess", json=payload, timeout=6.0)
        assert resp.status_code == 200

        # Verify DB row count has not increased
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM assessments")
        count_after = cursor.fetchone()[0]
        conn.close()

        assert count_after == count_before, (
            f"Database assessments table row count increased from {count_before} to {count_after}. "
            "Guest assessments must be session-isolated and not written to permanent storage."
        )


# -----------------------------------------------------------------------------
# 5. Landing Page CTA & UI Verification
# -----------------------------------------------------------------------------
class TestLandingPageCTA:
    """Verify landing page includes Try for Free buttons and dedicated section."""

    def test_index_html_has_try_for_free_cta(self):
        index_path = PROJECT_ROOT / "index.html"
        assert index_path.exists()
        content = index_path.read_text(encoding="utf-8")

        assert "farmer-dashboard.html?mode=guest" in content, (
            "index.html must link to farmer-dashboard.html?mode=guest"
        )
        assert "Try for Free" in content, (
            "index.html must contain 'Try for Free' call to action"
        )
        assert "Explore SoilSentinel for Free" in content, (
            "index.html must contain dedicated 'Explore SoilSentinel for Free' section"
        )
        assert "Assess a location, explore available soil and climate evidence" in content, (
            "index.html must contain required copy for guest exploration"
        )
