"""
SoilSentinel - Production Python Backend Bridge Service.

Provides both an HTTP microservice and a CLI adapter for Node.js integration.
Exposes strictly controlled, validated endpoints to:
1. List available assessment dates from actual project data.
2. Retrieve consolidated assessment dashboard payload for any date according
   to docs/dashboard_handoff_contract.md.
3. Simulate custom meteorological scenarios (rainfall, temperature, horizon)
   against actual baseline records.

Zero arbitrary execution: only predefined, validated actions and types.
Pure Python, NumPy, Pandas (LinuxONE s390x & Windows compatible).
"""

import os
import sys
import json
import argparse
import csv
import logging
import numpy as np
import pandas as pd
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

def to_serializable(val):
    if isinstance(val, dict):
        return {str(k) if not isinstance(k, (str, int, float, bool, type(None))) else k: to_serializable(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple, set)):
        return [to_serializable(v) for v in val]
    elif isinstance(val, (np.integer, np.int64, np.int32)):
        return int(val)
    elif isinstance(val, (np.floating, np.float64, np.float32)):
        return float(val)
    elif isinstance(val, np.ndarray):
        return to_serializable(val.tolist())
    elif isinstance(val, (np.bool_, bool)):
        return bool(val)
    elif hasattr(pd, "isna") and pd.isna(val):
        return None
    return val

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Model.service import SoilSentinelService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("soilsentinel_bridge")

# Global cached service instance
_SERVICE = None


def get_service():
    global _SERVICE
    if _SERVICE is None:
        logger.info("Initializing SoilSentinelService in bridge...")
        _SERVICE = SoilSentinelService()
    return _SERVICE


def handle_get_dates():
    svc = get_service()
    dates = svc.get_available_dates()
    latest = svc.get_latest_date()
    return {
        "success": True,
        "available_dates": dates,
        "latest_date": latest,
        "count": len(dates),
    }


def handle_get_assessment(date_str=None):
    svc = get_service()
    available = svc.get_available_dates()
    if not available:
        raise ValueError("No assessment dates available in dataset.")

    eval_date = date_str if (date_str and date_str.strip()) else svc.get_latest_date()
    if eval_date not in available:
        raise KeyError(f"Requested date '{eval_date}' is not in available dataset records ({available[0]} to {available[-1]}).")

    payload = svc.get_dashboard_payload(date=eval_date, log_audit=True, include_scenarios=True)
    return {
        "success": True,
        "payload": payload,
    }


def handle_get_v6_assessment(date_str=None):
    svc = get_service()
    eval_date = date_str if (date_str and date_str.strip()) else svc.get_latest_date()
    assessment = svc.get_v6_audited_assessment(date=eval_date)
    return {
        "success": True,
        "evaluation_date": eval_date,
        "v6_assessment": assessment,
    }


def handle_camera_analyze(image_input, modality="crop"):
    """Run accessible camera screening for crop symptoms or soil surface morphology."""
    if isinstance(image_input, dict):
        d = image_input
        modality = d.get("modality") or d.get("target_mode") or d.get("mode") or modality
        image_input = (
            d.get("image")
            or d.get("image_data")
            or d.get("image_base64")
            or d.get("imageData")
            or d.get("image_path")
            or ""
        )
    if not image_input or (isinstance(image_input, str) and not image_input.strip()):
        raise ValueError("Please capture or upload an image.")

    mod = str(modality).lower().strip()
    try:
        from src.Vision.camera_ai import get_camera_diagnostic_engine, HAS_CV2
        if not HAS_CV2:
            return {
                "status": "DEPENDENCY_ERROR",
                "success": False,
                "error": "OpenCV ('cv2') is not installed in the active Python runtime. Please install 'opencv-python-headless' to enable optical camera analysis.",
                "modality": mod,
                "diagnosis": "OPENCV_NOT_INSTALLED",
                "diagnosis_category": "DEPENDENCY_ERROR",
                "confidence": 0.0,
                "possible_causes": ["Missing 'opencv-python-headless' dependency in backend environment."],
                "recommended_next_steps": ["Install opencv-python-headless in the server Python environment."],
                "quality": {"status": "UNAVAILABLE", "quality_passed": False, "issues": ["cv2 not installed"]},
                "quality_report": {"status": "UNAVAILABLE", "quality_passed": False, "issues": ["cv2 not installed"]},
                "scientific_disclaimer": "Optical camera diagnostic requires OpenCV for image decoding and quality checks."
            }
        engine = get_camera_diagnostic_engine()
        if mod in ("soil", "soil_surface", "morphology"):
            diag = engine.diagnose(image_input, target_mode="soil")
        else:
            diag = engine.diagnose(image_input, target_mode="crop")
    except Exception as e:
        logger.exception("Camera diagnosis error:")
        return {
            "status": "ERROR",
            "success": False,
            "error": str(e),
            "modality": mod,
            "diagnosis": "PROCESSING_ERROR",
            "diagnosis_category": "ERROR",
            "confidence": 0.0,
            "explanation": f"Diagnostic processing failed: {str(e)}",
            "possible_causes": ["Internal computer vision processing error."],
            "recommended_next_steps": ["Retry capture or select a different photograph."]
        }

    status = diag.get("status", "SUCCESS")
    is_success = status in ("SUCCESS", "QUALITY_WARNING", "QUALITY_CHECK_FAILED", "OUT_OF_DISTRIBUTION") and status != "ERROR"
    cat = str(diag.get("diagnosis") or diag.get("diagnosis_category") or "Undetermined")

    conf = diag.get("confidence")
    if conf is None and diag.get("probabilities"):
        conf = max(diag["probabilities"].values())
    elif conf is None:
        conf = 0.0

    return {
        "status": status,
        "success": is_success,
        "modality": mod,
        "diagnosis": cat,
        "diagnosis_category": cat,
        "confidence": round(float(conf), 4),
        "probabilities": diag.get("probabilities", {}),
        "explanation": diag.get("explanation", ""),
        "possible_causes": diag.get("possible_causes", []),
        "recommended_next_steps": diag.get("recommended_next_steps", []),
        "quality": diag.get("quality_report", diag.get("quality", {})),
        "quality_report": diag.get("quality_report", diag.get("quality", {})),
        "scientific_disclaimer": diag.get("scientific_disclaimer", diag.get("scientific_honesty_statement", diag.get("agronomic_disclaimer", ""))),
        "optical_indices": diag.get("optical_indices", diag.get("visual_descriptors", {})),
        "payload": diag,
        "raw_diagnosis": diag
    }


def handle_get_spatial_layers(lat=None, lon=None, date_str=None):
    """Retrieve Sentinel-2 NDVI raster, AOI footprint, grid cell bounds, and layer legends."""
    from src.Geo.spatial_satellite import get_spatial_layers_payload
    lat_f = float(lat) if lat is not None else 30.7333
    lon_f = float(lon) if lon is not None else 76.7794
    d_str = str(date_str).strip() if (date_str and str(date_str).strip()) else "2024-12"
    return get_spatial_layers_payload(lat=lat_f, lon=lon_f, date_str=d_str)


def handle_gps_assess(latitude, longitude=None, crop_type=None, irrigation_type=None, field_soil_test=None):
    """Run real-time GPS field assessment with SoilGrids context, weather, V6 models, risk score, recommendations, SHAP explanation, and spatial layers."""
    if isinstance(latitude, dict):
        d = latitude
        latitude = d.get("latitude", d.get("lat"))
        longitude = d.get("longitude", d.get("lon"))
        crop_type = d.get("crop_type", crop_type)
        irrigation_type = d.get("irrigation_type", irrigation_type)
        field_soil_test = d.get("field_soil_test", field_soil_test)
    from src.Geo.field_assessment import get_field_assessment_engine
    engine = get_field_assessment_engine()
    lat = float(latitude)
    lon = float(longitude)
    assessment = engine.assess_field_location(
        lat=lat,
        lon=lon,
        crop_type=crop_type,
        irrigation_type=irrigation_type,
        field_soil_test=field_soil_test
    )
    sc = assessment.get("soil_context", {})
    props = sc.get("properties", {})
    if "ph_mean" not in sc:
        sc["ph_mean"] = props.get("ph_h2o", 7.2)
    if "soc_mean" not in sc:
        sc["soc_mean"] = props.get("soc_g_kg", 5.0)
    if "clay_mean" not in sc:
        sc["clay_mean"] = props.get("clay_percent", 25.0)
    if "scientific_status" not in sc:
        sc["scientific_status"] = "MAPPED_REGIONAL_CONTEXT_NOT_FIELD_LAB_TEST"

    # Compute rule-based risk score for this location
    wx = assessment.get("weather_context", {})
    mean_temp = float(wx.get("temperature_c_mean", 27.5))
    precip_mm = float(wx.get("precipitation_total_mm", 25.0)) / 30.0  # convert 30-day sum to mm/day rate
    ph_val = float(props.get("ph_h2o", 7.2))
    soc_val = float(props.get("soc_g_kg", 5.0))
    clay_val = float(props.get("clay_percent", 25.0))

    # Soil moisture estimate from precipitation and temperature
    est_moisture = max(0.05, min(0.95, 0.25 + (precip_mm * 0.05) - (mean_temp * 0.003)))

    loc_record = {
        "date": "2024-12",
        "region": f"GPS Coordinate ({lat:.4f}, {lon:.4f})",
        "sampled_latitude": lat,
        "sampled_longitude": lon,
        "air_temperature_c": mean_temp,
        "soil_temperature_layer1_c": mean_temp,
        "precipitation_mm_day": precip_mm,
        "soil_moisture_rootzone_fraction": est_moisture,
        "soil_moisture_surface_fraction": est_moisture * 0.9,
        "topsoil_soc_g_kg": soc_val,
        "topsoil_ph_mean": ph_val,
        "ph_0_5cm": ph_val,
        "ph_5_15cm": ph_val,
        "ph_15_30cm": ph_val,
        "soc_0_5cm_g_kg": soc_val,
        "soc_5_15cm_g_kg": soc_val * 0.8,
        "soc_15_30cm_g_kg": soc_val * 0.6,
        "clay_0_5cm_percent": clay_val,
        "clay_5_15cm_percent": clay_val,
        "clay_15_30cm_percent": clay_val,
        "sand_0_5cm_percent": float(props.get("sand_fraction", 50.0)),
        "silt_0_5cm_percent": float(props.get("silt_fraction", 25.0)),
    }

    # 1. Location Rule-Based Risk Assessment
    from src.Model.risk_scoring import calculate_baseline_risk_score
    risk_res = calculate_baseline_risk_score(loc_record, allow_partial=True)
    risk_dict = risk_res.to_dict()

    # 2. Location Recommendations
    from src.Model.recommendations import generate_ranked_recommendations
    rec_plan = generate_ranked_recommendations(scoring_result=risk_res, record=loc_record)
    rec_dict = rec_plan.to_dict()

    # 3. Location SHAP Explanation (using loaded surrogate model)
    svc = get_service()
    ml_explanation = None
    try:
        from src.Model.model import explain_prediction
        if svc.ml_model is not None and svc.ml_explainer is not None:
            ml_explanation = explain_prediction(
                record=loc_record,
                model=svc.ml_model,
                explainer=svc.ml_explainer,
                preprocessor=svc.ml_preprocessor,
                metadata=svc.ml_metadata
            )
    except Exception as e_shap:
        logger.warning(f"Could not compute SHAP for GPS assessment: {e_shap}")
        ml_explanation = {"status": "UNAVAILABLE", "error": str(e_shap)}

    # 4. Spatial layers payload for this location
    spatial_layers = None
    try:
        from src.Geo.spatial_satellite import get_spatial_layers_payload
        spatial_layers = get_spatial_layers_payload(lat=lat, lon=lon, date_str="2024-12")
    except Exception as e_sp:
        logger.warning(f"Could not load spatial layers for GPS location: {e_sp}")
        spatial_layers = {"error": str(e_sp)}

    return {
        "status": "SUCCESS",
        "success": True,
        "coordinates": {"latitude": lat, "longitude": lon},
        "field_assessment": assessment,
        "contextual_soilgrids": sc,
        "recent_weather": assessment.get("weather_context", {}),
        "v6_predictions": assessment.get("assessment", {}).get("evaluations", {}),
        "risk_assessment": risk_dict,
        "recommendations": rec_dict,
        "ml_explanation": ml_explanation,
        "spatial_layers": spatial_layers,
        "evaluation_record": loc_record,
        "disclaimer": (
            "Regional SoilGrids 250m estimates provide context. "
            "Where lab soil tests or in-situ sensors are uploaded, assessment precision increases."
        )
    }


def handle_soil_test_assess(soil_test_data):
    """Run researcher laboratory soil test analysis with V6 multi-task models."""
    from src.Model.v6_inference import get_v6_engine
    engine = get_v6_engine()
    if isinstance(soil_test_data, str):
        try:
            soil_test_data = json.loads(soil_test_data)
        except Exception:
            pass
    if not isinstance(soil_test_data, dict):
        raise ValueError("soil_test_data must be a valid dictionary of soil parameters.")
    eval_res = engine.predict_multitask(soil_test_data)
    from datetime import datetime, timezone
    return {
        "status": "SUCCESS",
        "success": True,
        "soil_test_assessment": eval_res,
        "multi_task_predictions": eval_res,
        "payload": {
            "multi_task_predictions": eval_res,
            "soil_test_assessment": eval_res,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "engine_version": "v6.0.0-audited"
            }
        }
    }




def handle_get_observations():
    """Return an allow-listed, read-only set of real study-area observations for charts."""
    feature_path = PROJECT_ROOT / "data" / "processed" / "satellite" / "aligned_feature_table_with_satellite.csv"
    if not feature_path.exists():
        feature_path = PROJECT_ROOT / "data" / "feature_table.csv"
    if not feature_path.exists():
        raise FileNotFoundError("Feature table is unavailable; climate and soil charts cannot be loaded.")

    allowed = [
        "date", "region", "nominal_latitude", "nominal_longitude",
        "sampled_latitude", "sampled_longitude",
        "air_temperature_c", "air_humidity_percent", "precipitation_mm_day",
        "soil_temperature_layer1_c", "soil_moisture_surface_fraction",
        "soil_moisture_rootzone_fraction",
        "ph_0_5cm", "ph_5_15cm", "ph_15_30cm",
        "soc_0_5cm_g_kg", "soc_5_15cm_g_kg", "soc_15_30cm_g_kg",
        "clay_0_5cm_percent", "clay_5_15cm_percent", "clay_15_30cm_percent",
        "sand_0_5cm_percent", "sand_5_15cm_percent", "sand_15_30cm_percent",
        "silt_0_5cm_percent", "silt_5_15cm_percent", "silt_15_30cm_percent",
        "climate_source", "soil_source", "climate_measurement_type", "soil_measurement_type",
        "satellite_ndvi", "satellite_ndvi_median", "satellite_ndvi_std",
        "satellite_valid_pixel_fraction", "satellite_cloud_shadow_pixel_fraction",
        "satellite_scl_vegetation_fraction", "satellite_scl_bare_soil_fraction",
        "satellite_quality_flag", "satellite_scene_id", "satellite_observation_date",
        "satellite_platform", "satellite_processing_method", "satellite_data_source"
    ]
    rows = []
    with feature_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [key for key in ("date", "air_temperature_c", "precipitation_mm_day") if key not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("Feature table is missing required chart columns: " + ", ".join(missing))
        for row in reader:
            item = {}
            for key in allowed:
                value = row.get(key)
                if value is None or value == "":
                    item[key] = None
                    continue
                if key in ("date", "region", "climate_source", "soil_source", "climate_measurement_type", "soil_measurement_type",
                           "satellite_quality_flag", "satellite_scene_id", "satellite_observation_date",
                           "satellite_platform", "satellite_processing_method", "satellite_data_source"):
                    item[key] = value
                else:
                    try:
                        number = float(value)
                        item[key] = number if number == number and abs(number) != float("inf") else None
                    except (TypeError, ValueError):
                        item[key] = None
            rows.append(item)
    rows.sort(key=lambda row: row.get("date") or "")
    if not rows:
        raise ValueError("Feature table contains no chartable observations.")
    first = rows[0]
    return {
        "success": True,
        "region": first.get("region") or "Configured study region",
        "coordinates": {
            "latitude": first.get("sampled_latitude") or first.get("nominal_latitude"),
            "longitude": first.get("sampled_longitude") or first.get("nominal_longitude")
        },
        "date_start": rows[0].get("date"),
        "date_end": rows[-1].get("date"),
        "count": len(rows),
        "climate_source": first.get("climate_source") or "Climate source not specified",
        "soil_source": first.get("soil_source") or "Soil source not specified",
        "satellite_source": first.get("satellite_data_source") or "Copernicus Sentinel-2 L2A (10m)",
        "rows": rows
    }


def handle_evaluate_scenario(date_str, custom_precip, custom_temp, horizon_days=30):
    svc = get_service()
    available = svc.get_available_dates()
    if not available:
        raise ValueError("No assessment dates available in dataset.")

    eval_date = date_str if (date_str and date_str.strip()) else svc.get_latest_date()
    if eval_date not in available:
        raise KeyError(f"Requested date '{eval_date}' is not in available dataset records.")

    # Validate numeric parameters
    precip = float(custom_precip)
    if precip < 0.0 or precip > 200.0:
        raise ValueError("Precipitation must be between 0.0 and 200.0 mm/day.")

    temp = float(custom_temp)
    if temp < -50.0 or temp > 70.0:
        raise ValueError("Temperature must be between -50.0 and 70.0 degrees Celsius.")

    horizon = int(horizon_days)
    if horizon < 1 or horizon > 365:
        raise ValueError("Horizon days must be between 1 and 365.")

    comparison = svc.evaluate_custom_scenario(
        date=eval_date,
        custom_precipitation=precip,
        custom_temperature=temp,
        horizon_days=horizon,
    )

    baseline_rec = svc.get_scored_record(eval_date)
    return {
        "success": True,
        "evaluation_date": eval_date,
        "inputs": {
            "custom_precipitation_mm_day": precip,
            "custom_temperature_c": temp,
            "horizon_days": horizon,
        },
        "comparison": comparison,
    }


class BridgeHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override to use logger instead of stderr
        logger.info("%s - %s", self.address_string(), format % args)

    def _send_json(self, status_code, data):
        response_bytes = json.dumps(to_serializable(data), indent=None, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.send_header("Access-Control-Allow-Origin", "http://localhost:3000")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(response_bytes)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "http://localhost:3000")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        try:
            if path in ("/health", "/api/health"):
                self._send_json(200, {"status": "ok", "service": "SoilSentinel Python Backend"})

            elif path in ("/dates", "/api/dates"):
                result = handle_get_dates()
                self._send_json(200, result)

            elif path in ("/assessment", "/api/assessment"):
                date_val = params.get("date", [None])[0]
                result = handle_get_assessment(date_val)
                self._send_json(200, result)

            elif path in ("/v6-assessment", "/api/v6-assessment"):
                date_val = params.get("date", [None])[0]
                result = handle_get_v6_assessment(date_val)
                self._send_json(200, result)

            elif path in ("/observations", "/api/observations"):
                result = handle_get_observations()
                self._send_json(200, result)

            elif path in ("/spatial-layers", "/api/spatial-layers", "/api/spatial/layers"):
                lat_val = params.get("lat", [None])[0] or params.get("latitude", [None])[0]
                lon_val = params.get("lon", [None])[0] or params.get("longitude", [None])[0]
                date_val = params.get("date", [None])[0]
                result = handle_get_spatial_layers(lat_val, lon_val, date_val)
                self._send_json(200, result)

            else:
                self._send_json(404, {"success": False, "error": f"Endpoint '{path}' not found."})

        except KeyError as ke:
            self._send_json(404, {"success": False, "error": str(ke)})
        except ValueError as ve:
            self._send_json(400, {"success": False, "error": str(ve)})
        except Exception as e:
            logger.exception("Bridge GET error:")
            self._send_json(500, {"success": False, "error": f"Internal backend error: {str(e)}"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            body = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}

            if path in ("/scenario", "/api/scenario"):
                date_val = body.get("date")
                precip = body.get("custom_precipitation", body.get("rainfall_mm", 0.5))
                temp = body.get("custom_temperature", body.get("temp_c", 38.0))
                horizon = body.get("horizon_days", 30)
                result = handle_evaluate_scenario(date_val, precip, temp, horizon)
                self._send_json(200, result)

            elif path in ("/camera-analyze", "/api/camera-analyze", "/api/camera/analyze"):
                image_input = (
                    body.get("image")
                    or body.get("image_data")
                    or body.get("image_base64")
                    or body.get("imageData")
                    or body.get("image_path")
                    or ""
                )
                modality = body.get("modality") or body.get("target_mode") or body.get("mode") or "crop"
                result = handle_camera_analyze(image_input, modality)
                status_code = 200 if result.get("success", True) else 400
                self._send_json(status_code, result)

            elif path in ("/gps-assess", "/api/gps-assess", "/api/gps/assess"):
                lat = body.get("latitude", body.get("lat"))
                lon = body.get("longitude", body.get("lon"))
                if lat is None or lon is None:
                    raise ValueError("Both 'latitude' and 'longitude' are required for GPS field assessment.")
                crop = body.get("crop_type")
                irrigation = body.get("irrigation_type")
                soil_test = body.get("field_soil_test")
                result = handle_gps_assess(lat, lon, crop, irrigation, soil_test)
                self._send_json(200, result)

            elif path in ("/spatial-layers", "/api/spatial-layers", "/api/spatial/layers"):
                lat = body.get("latitude", body.get("lat"))
                lon = body.get("longitude", body.get("lon"))
                date_val = body.get("date")
                result = handle_get_spatial_layers(lat, lon, date_val)
                self._send_json(200, result)

            elif path in ("/soil-test-assess", "/api/soil-test-assess", "/api/researcher/upload-soil-test"):
                soil_data = body.get("soil_test", body.get("measurements", body))
                result = handle_soil_test_assess(soil_data)
                self._send_json(200, result)

            else:
                self._send_json(404, {"success": False, "error": f"Endpoint '{path}' not found."})

        except KeyError as ke:
            self._send_json(404, {"success": False, "error": str(ke)})
        except ValueError as ve:
            self._send_json(400, {"success": False, "error": str(ve)})
        except Exception as e:
            logger.exception("Bridge POST error:")
            self._send_json(500, {"success": False, "error": f"Internal backend error: {str(e)}"})


def run_server(port=5001, host="127.0.0.1"):
    server_address = (host, port)
    httpd = HTTPServer(server_address, BridgeHTTPRequestHandler)
    logger.info("SoilSentinel Python HTTP Bridge listening on http://%s:%d", host, port)
    # Preload dataset so first request is immediate
    get_service()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Bridge server shutting down.")
    finally:
        httpd.server_close()


def run_cli():
    parser = argparse.ArgumentParser(description="SoilSentinel Python Backend Bridge CLI")
    parser.add_argument(
        "command",
        choices=["dates", "assessment", "v6-assessment", "scenario", "observations", "camera-analyze", "gps-assess", "spatial-layers", "soil-test-assess", "serve"],
        help="Command to execute"
    )
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM")
    parser.add_argument("--precip", type=float, default=0.5, help="Custom precipitation (mm/day)")
    parser.add_argument("--temp", type=float, default=38.0, help="Custom temperature (C)")
    parser.add_argument("--horizon", type=int, default=30, help="Horizon days (default: 30)")
    parser.add_argument("--image", type=str, default="", help="Image filepath or base64 string")
    parser.add_argument("--image-file", type=str, default=None, help="Filepath containing image data")
    parser.add_argument("--modality", type=str, default="crop", help="Modality: 'crop' or 'soil'")
    parser.add_argument("--lat", type=float, default=None, help="Latitude for GPS field assessment")
    parser.add_argument("--lon", type=float, default=None, help="Longitude for GPS field assessment")
    parser.add_argument("--crop", type=str, default=None, help="Crop type for GPS field assessment")
    parser.add_argument("--irrigation", type=str, default=None, help="Irrigation type for GPS field assessment")
    parser.add_argument("--soil-data", type=str, default=None, help="JSON-encoded soil test record")
    parser.add_argument("--port", type=int, default=5001, help="Port for --serve mode")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for --serve mode")

    args = parser.parse_args()

    if args.command == "serve":
        run_server(port=args.port, host=args.host)
        return

    try:
        if args.command == "dates":
            res = handle_get_dates()
        elif args.command == "assessment":
            res = handle_get_assessment(args.date)
        elif args.command == "v6-assessment":
            res = handle_get_v6_assessment(args.date)
        elif args.command == "scenario":
            res = handle_evaluate_scenario(args.date, args.precip, args.temp, args.horizon)
        elif args.command == "observations":
            res = handle_get_observations()
        elif args.command == "spatial-layers":
            res = handle_get_spatial_layers(args.lat, args.lon, args.date)
        elif args.command == "camera-analyze":
            img_val = args.image
            if args.image_file and os.path.exists(args.image_file):
                with open(args.image_file, "r", encoding="utf-8") as f:
                    img_val = f.read().strip()
            res = handle_camera_analyze(img_val, args.modality)
        elif args.command == "gps-assess":
            if args.lat is None or args.lon is None:
                raise ValueError("--lat and --lon are required for gps-assess")
            soil_test = json.loads(args.soil_data) if args.soil_data else None
            res = handle_gps_assess(args.lat, args.lon, args.crop, args.irrigation, soil_test)
        elif args.command == "soil-test-assess":
            if not args.soil_data:
                raise ValueError("--soil-data JSON string is required for soil-test-assess")
            soil_data = json.loads(args.soil_data)
            res = handle_soil_test_assess(soil_data)
        print(json.dumps(to_serializable(res), ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("dates", "assessment", "v6-assessment", "scenario", "observations", "camera-analyze", "gps-assess", "spatial-layers", "soil-test-assess", "serve"):
        run_cli()
    elif "--serve" in sys.argv:
        port = 5001
        if "--port" in sys.argv:
            idx = sys.argv.index("--port")
            if idx + 1 < len(sys.argv):
                port = int(sys.argv[idx + 1])
        run_server(port=port)
    else:
        run_cli()
