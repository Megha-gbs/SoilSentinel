"""
Comprehensive Test Suite for SoilSentinel V6 Camera Diagnostic Workflow.
========================================================================
Validates:
1. Crop Leaf screening (uploaded image, camera capture data URI, raw base64).
2. Soil Surface screening (surface morphology, erosion rills, salt crust).
3. Field aliasing (image, image_data, image_base64, imageData, modality, target_mode, mode).
4. Validation & error states (missing image, invalid binary, corrupted base64).
5. Quality guard (Laplacian variance blur detection, blur scores, retry recommendations).
6. Out-of-distribution rejection (non-agricultural photos).
7. Normalized contract responses (diagnosis string, confidence, probabilities, causes, next steps).
8. Scientific honesty disclaimers (optical camera limitations).
9. Express HTTP endpoint (/api/camera/analyze) authenticated session flow & status codes.
"""

import os
import sys
import json
import base64
import tempfile
from pathlib import Path
import numpy as np
import cv2
import pytest
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Vision.camera_ai import CameraDiagnosticEngine, get_camera_diagnostic_engine
from src.Model.bridge import handle_camera_analyze

DATA_RAW_CAMERA = PROJECT_ROOT / "data" / "raw" / "camera"


def load_file_as_data_uri(path: Path) -> str:
    """Load an image file from disk and encode as base64 data URI."""
    with open(path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode("utf-8")
    ext = path.suffix.lower()
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
    return f"data:{mime};base64,{b64}"


def create_high_contrast_non_crop_image() -> np.ndarray:
    """Create a sharp, high-contrast non-crop image (metallic navy / purple pattern)."""
    img = np.zeros((256, 256, 3), dtype=np.uint8)
    img[:, :] = (130, 70, 30)  # Metallic navy blue
    for x in range(20, 240, 30):
        cv2.line(img, (x, 0), (x, 256), (30, 30, 200), 3)
    cv2.circle(img, (128, 128), 60, (200, 30, 180), -1)
    cv2.circle(img, (128, 128), 60, (20, 20, 20), 3)
    return img


def to_data_uri(img_bgr: np.ndarray, mime: str = "image/jpeg") -> str:
    """Convert BGR numpy image to Base64 data URI."""
    ext = ".jpg" if "jpeg" in mime or "jpg" in mime else ".png"
    _, buf = cv2.imencode(ext, img_bgr)
    b64 = base64.b64encode(buf).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def to_raw_b64(img_bgr: np.ndarray) -> str:
    """Convert BGR numpy image to raw Base64 without data URI prefix."""
    _, buf = cv2.imencode(".png", img_bgr)
    return base64.b64encode(buf).decode("utf-8")


class TestCameraDiagnosticWorkflow:
    """Test suite covering the complete Camera AI diagnostic lifecycle."""

    @classmethod
    def setup_class(cls):
        cls.engine = get_camera_diagnostic_engine()

    def test_crop_foliar_healthy_diagnosis(self):
        """Test crop foliage diagnosis with authentic healthy tomato foliage photo."""
        img_path = DATA_RAW_CAMERA / "crop" / "healthy_tomato_foliage_01.jpg"
        assert img_path.exists(), f"Image not found at {img_path}"
        data_uri = load_file_as_data_uri(img_path)

        payload = {"image_data": data_uri, "target_mode": "crop"}
        res = handle_camera_analyze(payload)

        assert res["success"] is True
        assert res["status"] == "SUCCESS"
        assert res["modality"] == "crop"
        assert isinstance(res["diagnosis"], str)
        assert res["diagnosis"] == "HEALTHY_VIGOROUS_FOLIAGE"
        assert isinstance(res["confidence"], float)
        assert res["confidence"] >= 0.5
        assert isinstance(res["probabilities"], dict)
        assert len(res["probabilities"]) > 0
        assert len(res["possible_causes"]) > 0
        assert len(res["recommended_next_steps"]) > 0
        assert res["quality"]["status"] == "OK"
        assert res["quality"]["laplacian_variance"] >= 25.0

    def test_crop_foliar_chlorosis_diagnosis(self):
        """Test crop leaf diagnosis with authentic chlorotic leaf photo."""
        img_path = DATA_RAW_CAMERA / "crop" / "leaf_interveinal_chlorosis_01.jpg"
        assert img_path.exists()
        data_uri = load_file_as_data_uri(img_path)

        res = handle_camera_analyze({"image": data_uri, "modality": "crop"})
        assert res["success"] is True
        assert res["diagnosis"] == "NUTRIENT_CHLOROSIS"
        assert "chlorosis" in res["explanation"].lower() or "yellow" in res["explanation"].lower()
        assert len(res["possible_causes"]) >= 2
        assert len(res["recommended_next_steps"]) >= 2

    def test_soil_surface_saline_efflorescence(self):
        """Test soil surface screening with authentic saline efflorescence photo."""
        img_path = DATA_RAW_CAMERA / "soil" / "soil_saline_efflorescence_01.jpg"
        assert img_path.exists()
        data_uri = load_file_as_data_uri(img_path)

        res = handle_camera_analyze({"imageData": data_uri, "mode": "soil"})
        assert res["success"] is True
        assert res["modality"] == "soil"
        assert res["diagnosis"] == "SALINE_EFFLORESCENCE_CRUST"
        assert "salt" in res["explanation"].lower() or "efflorescence" in res["explanation"].lower()
        assert "scientific_disclaimer" in res
        assert "laboratory" in res["scientific_disclaimer"].lower()

    def test_soil_surface_water_erosion_rill(self):
        """Test soil surface screening with authentic erosion rill photo."""
        img_path = DATA_RAW_CAMERA / "soil" / "soil_rill_erosion_01.jpg"
        assert img_path.exists()
        data_uri = load_file_as_data_uri(img_path)

        res = handle_camera_analyze({"image_data": data_uri, "target_mode": "soil"})
        assert res["success"] is True
        assert res["diagnosis"] == "SURFACE_WATER_EROSION_RILL"
        assert len(res["recommended_next_steps"]) >= 2

    def test_soil_surface_crusting_compaction(self):
        """Test soil surface screening with authentic compacted crust photo."""
        img_path = DATA_RAW_CAMERA / "soil" / "compacted_soil_crust_02.jpg"
        assert img_path.exists()
        data_uri = load_file_as_data_uri(img_path)

        res = handle_camera_analyze({"image_data": data_uri, "target_mode": "soil"})
        assert res["success"] is True
        assert res["diagnosis"] == "SURFACE_CRUSTING_AND_COMPACTION"
        assert len(res["recommended_next_steps"]) >= 2

    def test_raw_base64_decoding(self):
        """Test decoding raw Base64 strings without data:image prefix."""
        img_path = DATA_RAW_CAMERA / "crop" / "healthy_tomato_foliage_01.jpg"
        img = cv2.imread(str(img_path))
        raw_b64 = to_raw_b64(img)

        res = handle_camera_analyze(raw_b64, modality="crop")
        assert res["success"] is True
        assert res["status"] == "SUCCESS"
        assert isinstance(res["diagnosis"], str)

    def test_quality_guard_rejects_blurry_image(self):
        """Test that Laplacian variance flags blurred, out-of-focus images."""
        img_path = DATA_RAW_CAMERA / "crop" / "chlorotic_lemon_leaf_02.jpg"
        assert img_path.exists()
        data_uri = load_file_as_data_uri(img_path)

        res = handle_camera_analyze({"image_data": data_uri, "target_mode": "crop"})
        assert res["status"] == "QUALITY_CHECK_FAILED"
        assert res["diagnosis"] == "UNSUITABLE_IMAGE"
        assert res["quality"]["status"] == "POOR"
        assert res["quality"]["laplacian_variance"] < 25.0
        assert len(res["possible_causes"]) > 0
        assert len(res["recommended_next_steps"]) > 0

    def test_out_of_distribution_rejection(self):
        """Test rejection of non-agricultural, non-vegetative photos."""
        non_crop = create_high_contrast_non_crop_image()
        data_uri = to_data_uri(non_crop)

        res = handle_camera_analyze({"image_data": data_uri, "target_mode": "crop"})
        assert res["status"] == "OUT_OF_DISTRIBUTION"
        assert res["diagnosis"] == "NON_CROP_IMAGE"
        assert "not appear to contain recognizable crop" in res["explanation"]
        assert len(res["recommended_next_steps"]) > 0

    def test_missing_image_validation(self):
        """Test that missing or empty image inputs raise clear ValueError."""
        with pytest.raises(ValueError, match="Please capture or upload an image"):
            handle_camera_analyze("")

        with pytest.raises(ValueError, match="Please capture or upload an image"):
            handle_camera_analyze(None)

        with pytest.raises(ValueError, match="Please capture or upload an image"):
            handle_camera_analyze({"image": "   ", "modality": "crop"})

    def test_corrupted_image_handling(self):
        """Test graceful handling of corrupt or invalid image data."""
        corrupted_b64 = "data:image/jpeg;base64,NotAValidImageBase64Payload123456"
        res = handle_camera_analyze(corrupted_b64, modality="crop")
        assert res["status"] == "ERROR"
        assert res["success"] is False
        assert "error" in res or "Unable to decode" in res.get("explanation", "")

    def test_field_alias_compatibility(self):
        """Test all frontend JSON alias permutations."""
        img_path = DATA_RAW_CAMERA / "crop" / "healthy_tomato_foliage_01.jpg"
        data_uri = load_file_as_data_uri(img_path)

        permutations = [
            {"image_data": data_uri, "target_mode": "crop"},
            {"image": data_uri, "modality": "crop"},
            {"image_base64": data_uri, "mode": "crop"},
            {"imageData": data_uri, "target_mode": "soil"},
            {"image_path": data_uri, "modality": "soil"}
        ]
        for p in permutations:
            res = handle_camera_analyze(p)
            assert res["success"] is True
            assert isinstance(res["diagnosis"], str)

    def test_cli_execution_with_temp_file(self):
        """Test Python CLI fallback execution with --image-file argument."""
        import subprocess

        img_path = DATA_RAW_CAMERA / "crop" / "healthy_tomato_foliage_01.jpg"
        data_uri = load_file_as_data_uri(img_path)

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as tf:
            tf.write(data_uri)
            temp_path = tf.name

        try:
            cmd = [
                sys.executable,
                "-m",
                "src.Model.bridge",
                "camera-analyze",
                "--image-file",
                temp_path,
                "--modality",
                "crop"
            ]
            proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
            assert proc.returncode == 0, f"CLI stderr: {proc.stderr}"
            output = json.loads(proc.stdout)
            assert output["success"] is True
            assert output["status"] == "SUCCESS"
            assert isinstance(output["diagnosis"], str)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestExpressCameraHttpEndpoint:
    """Test the live Express HTTP API /api/camera/analyze."""

    BASE_URL = "http://127.0.0.1:3000"

    @classmethod
    def setup_class(cls):
        cls.session = requests.Session()
        # Login as farmer
        login_res = cls.session.post(
            f"{cls.BASE_URL}/api/auth/login",
            json={"email": "farmer.demo@soilsentinel.local", "password": "DemoSoil2026!"},
            timeout=10
        )
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"

    def test_http_analyze_crop_with_image_data(self):
        """Verify POST /api/camera/analyze works with frontend alias 'image_data'."""
        img_path = DATA_RAW_CAMERA / "crop" / "healthy_tomato_foliage_01.jpg"
        data_uri = load_file_as_data_uri(img_path)

        payload = {
            "image_data": data_uri,
            "target_mode": "crop"
        }
        resp = self.session.post(f"{self.BASE_URL}/api/camera/analyze", json=payload, timeout=15)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["status"] == "SUCCESS"
        assert isinstance(data["diagnosis"], str)
        assert len(data["possible_causes"]) > 0
        assert len(data["recommended_next_steps"]) > 0

    def test_http_analyze_soil_with_image(self):
        """Verify POST /api/camera/analyze works with 'image' and 'modality' in soil mode."""
        img_path = DATA_RAW_CAMERA / "soil" / "soil_saline_efflorescence_01.jpg"
        data_uri = load_file_as_data_uri(img_path)

        payload = {
            "image": data_uri,
            "modality": "soil"
        }
        resp = self.session.post(f"{self.BASE_URL}/api/camera/analyze", json=payload, timeout=15)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["modality"] == "soil"
        assert data["diagnosis"] == "SALINE_EFFLORESCENCE_CRUST"

    def test_http_missing_image_returns_400(self):
        """Verify POST /api/camera/analyze returns 400 with helpful error message when image is missing."""
        resp = self.session.post(
            f"{self.BASE_URL}/api/camera/analyze",
            json={"image_data": "", "target_mode": "crop"},
            timeout=10
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data["success"] is False
        assert "Please capture or upload an image." in data["error"]

    def test_http_invalid_modality_returns_400(self):
        """Verify POST /api/camera/analyze returns 400 if modality is neither crop nor soil."""
        img_path = DATA_RAW_CAMERA / "crop" / "healthy_tomato_foliage_01.jpg"
        data_uri = load_file_as_data_uri(img_path)

        resp = self.session.post(
            f"{self.BASE_URL}/api/camera/analyze",
            json={"image": data_uri, "modality": "invalid_mode"},
            timeout=10
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "Modality must be 'crop' or 'soil'" in data["error"]

    def test_http_guest_allowed_and_researcher_protected(self):
        """Verify unauthenticated guests can use camera diagnostics, but protected researcher routes reject them."""
        anon_session = requests.Session()
        # Camera diagnostic allows guest requests (Try SoilSentinel for Free feature)
        resp = anon_session.post(
            f"{self.BASE_URL}/api/camera/analyze",
            json={"image": "dummy", "modality": "crop"},
            timeout=10
        )
        assert resp.status_code == 200, f"Expected 200 for guest camera analysis, got {resp.status_code}"

        # Protected researcher route requires authentication
        resp_protected = anon_session.get(f"{self.BASE_URL}/api/researcher/workspace", timeout=10)
        assert resp_protected.status_code in (401, 403), f"Expected 401/403 for protected route, got {resp_protected.status_code}"

