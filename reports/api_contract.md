# SoilSentinel — Backend API & Dashboard Handoff Contract Specification

**Document Status:** Authoritative API Contract  
**Version:** `v1.2.0-post-integration`  
**Date:** October 2026  
**Backward Compatibility Guarantee:** 100% Non-Breaking Extension  
**Integration Endpoints:** Python Service (`src.Model.service`), HTTP Bridge (`src.Model.bridge`), Node.js Express Server (`server.js`)  

---

## 1. Overview & Architectural Principles

The SoilSentinel API provides the single, consolidated data interface connecting validated data pipelines, deterministic risk scoring, empirical machine learning surrogate inference, SHAP explanations, longitudinal recovery tracking, scenario simulations, and crop eligibility checks to both frontend dashboards (`farmer-dashboard.html`, `researcher-dashboard.html`) and external clients.

### Core Compatibility Principles:
1. **Preservation of Existing Schemas:** All existing 8 top-level keys (`metadata`, `risk_assessment`, `recommendations`, `recovery_tracking`, `crop_eligibility`, `scenario_comparison`, `historical_series`, `audit_reference`) remain completely untouched in name, type, and semantic structure.
2. **Explicit Independent Assessment Block:** A separate, dedicated block `independent_degradation_assessment` is appended to the payload. When independent ground truth is unavailable, it returns an explicit `PENDING_INDEPENDENT_GROUND_TRUTH` status, preventing any ambiguity or false claims of physical degradation.
3. **Zero Arbitrary Execution:** All endpoints consume strictly typed, sanitized inputs with exhaustive boundary guards.

---

## 2. Master Endpoints Table

| Route | HTTP Method | Auth Role | Description | Backend Source |
| :--- | :---: | :---: | :--- | :--- |
| `/api/assessment/dates` | `GET` | Authenticated | Lists all available 60 monthly assessment dates (`YYYY-MM`). | `bridge.py::handle_get_dates` |
| `/api/assessment/evaluate` | `GET` | Authenticated | Retrieves consolidated dashboard payload for a specific date (or latest). | `service.py::get_dashboard_payload` |
| `/api/assessment/scenario` | `POST` | Authenticated | Simulates interactive what-if weather stress scenarios against baseline. | `service.py::evaluate_custom_scenario` |
| `/api/farmer/workspace` | `GET` | `farmer` | Farmer role dashboard summary and latest evaluation. | `server.js` + bridge |
| `/api/auth/register` | `POST` | Public | Registers a new farmer or researcher account. | SQLite `users` table |
| `/api/auth/login` | `POST` | Public | Authenticates user credentials and establishes cookie session. | bcrypt + express-session |
| `/api/auth/me` | `GET` | Public | Returns current session status and user profile. | Session store |
| `/api/auth/logout` | `POST` | Authenticated | Terminates active session. | Session store |

---

## 3. Detailed Request & Response Specifications

### 3.1 Endpoint: `/api/assessment/dates`
Retrieves the list of validated monthly dates available in the underlying feature table.

- **Request:**
  ```http
  GET /api/assessment/dates HTTP/1.1
  Cookie: soilsentinel.sid=...
  ```
- **Response (200 OK):**
  ```json
  {
    "success": true,
    "available_dates": [
      "2020-01", "2020-02", "...", "2024-11", "2024-12"
    ],
    "latest_date": "2024-12",
    "count": 60
  }
  ```

---

### 3.2 Endpoint: `/api/assessment/evaluate`
Retrieves the consolidated evaluation payload for a target month.

- **Query Parameters:**
  - `date` *(optional, string)*: Target month in format `YYYY-MM`. If omitted, defaults to the latest available month (`2024-12`). Must match `^\d{4}-\d{2}$`.
- **Request:**
  ```http
  GET /api/assessment/evaluate?date=2024-06 HTTP/1.1
  Cookie: soilsentinel.sid=...
  ```

- **Response Payload Schema (200 OK):**
```json
{
  "success": true,
  "payload": {
    "metadata": {
      "assessment_id": "ASM-2024-06-20261017193000",
      "assessment_status": "VALID",
      "generated_at_utc": "2026-10-17T14:00:00.000000+00:00",
      "engine_version": "v1.0.0-baseline",
      "index_name": "Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index",
      "assumptions_label": "PROVISIONAL_ENGINEERING_HEURISTIC",
      "evaluation_date": "2024-06",
      "audit_logged": true
    },
    "risk_assessment": {
      "score": 67.8,
      "risk_category": "High",
      "status": "VALID",
      "dynamic_environmental_stress": 82.4,
      "baseline_soil_vulnerability": 33.7,
      "top_risk_drivers": ["Moisture Deficit", "Thermal Stress", "Precipitation Deficit"],
      "explanation": "Elevated dynamic hydro-thermal stress driven by acute moisture deficit.",
      "data_quality": {
        "status": "COMPLETE",
        "evidence_tier": "TIER_1_EMPIRICAL",
        "observation_completeness": 1.0,
        "missing_features": [],
        "data_sources": ["NASA POWER (Meteorology)", "SoilGrids 250m (Pedology)"]
      },
      "indicators": {
        "moisture_deficit": { "name": "Moisture Deficit", "sub_score": 95.0, "weight": 0.30, "weighted_score": 28.5, "raw_value": 0.112 },
        "precipitation_deficit": { "name": "Precipitation Deficit", "sub_score": 75.0, "weight": 0.25, "weighted_score": 18.75, "moisture_buffering_factor": 0.048 },
        "thermal_stress": { "name": "Thermal Stress", "sub_score": 62.0, "weight": 0.15, "weighted_score": 9.3, "raw_value": 39.5 },
        "soc_vulnerability": { "name": "SOC Vulnerability", "sub_score": 45.0, "weight": 0.15, "weighted_score": 6.75, "raw_value": 9.6 },
        "ph_deviation": { "name": "pH Deviation", "sub_score": 30.0, "weight": 0.15, "weighted_score": 4.5, "raw_value": 7.42 }
      }
    },
    "recommendations": {
      "status": "VALID",
      "overall_risk_score": 67.8,
      "overall_risk_category": "High",
      "primary_stressor": "Moisture Deficit",
      "top_three_recommendations": [
        {
          "recommendation_id": "REC-MOISTURE-CRI",
          "indicator_key": "moisture_deficit",
          "title": "Immediate Supplementary Micro-Irrigation & Deep Mulching",
          "urgency": "CRITICAL",
          "action_type": "RESTORATION",
          "expected_impact": "Prevents catastrophic root wilting and preserves capillary moisture."
        }
      ]
    },
    "recovery_tracking": {
      "recovery_status": "STABLE",
      "mom_delta": 4.2,
      "yoy_delta": 1.5,
      "historical_percentile": 92.0,
      "historical_mean": 42.1,
      "historical_max": 67.8
    },
    "crop_eligibility": {
      "is_eligible": true,
      "season": "Kharif",
      "recommended_crops": ["Pigeon Pea (Arhar)", "Pearl Millet (Bajra)", "Sorghum"],
      "restricted_crops": ["Paddy Rice (transplanted)"],
      "disclaimer": "Agronomic suitability advisory based on hydro-thermal stress and soil texture."
    },
    "scenario_comparison": {
      "baseline_date": "2024-06",
      "comparisons": {
        "dry_spell": { "delta_score": 8.5, "category_shift": "High -> High" },
        "normal_climatology": { "delta_score": -12.4, "category_shift": "High -> Medium" },
        "heavy_rainfall": { "delta_score": -22.1, "category_shift": "High -> Low" }
      }
    },
    "historical_series": [
      { "date": "2020-01", "score": 28.4, "risk_category": "Low" },
      { "date": "2024-12", "score": 41.2, "risk_category": "Medium" }
    ],
    "ml_prediction": {
      "status": "VALID",
      "model_version": "v1.0.0-rf-proxy",
      "model_type": "Random Forest Classifier",
      "predicted_category": "High",
      "class_probabilities": { "High": 0.72, "Medium": 0.25, "Low": 0.03 },
      "target_provenance": "SURROGATE_PROXY_LEARNING",
      "disclaimer": "Proxy model approximating rule-based index."
    },
    "ml_explanation": {
      "status": "VALID",
      "model_version": "v1.0.0-rf-proxy",
      "explained_class": "High",
      "prediction_probability": 0.72,
      "base_value": 0.02,
      "sum_shap_values": 0.702,
      "reconstituted_probability": 0.722,
      "additivity_discrepancy": 0.002,
      "additivity_tolerance": 0.02,
      "output_space": "probability",
      "top_features": [
        { "feature": "soil_moisture_rootzone_fraction", "impact": 0.284, "direction": "increases_risk" },
        { "feature": "air_temperature_c", "impact": 0.192, "direction": "increases_risk" }
      ],
      "methodology": "TreeSHAP (interventional perturbation with training partition background)",
      "causation_warning": "SHAP explains surrogate model approximations, not physical causation."
    },
    "independent_degradation_assessment": {
      "status": "PENDING_INDEPENDENT_GROUND_TRUTH",
      "target_definition": {
        "primary_target": "PHYSICAL_SOIL_ORGANIC_CARBON_DEPLETION",
        "metric": "delta_soc_percent_change",
        "threshold": "decline > 10% over 5-year baseline",
        "units": "g/kg",
        "required_protocol": "Dry combustion elemental analysis (ISO 10694) or Walkley-Black wet oxidation"
      },
      "validation_status": "NOT_VALIDATED_AGAINST_PHYSICAL_GROUND_TRUTH",
      "model_execution": "BLOCKED_PENDING_INDEPENDENT_LABELS",
      "surrogate_comparison": {
        "surrogate_model_role": "Rule-based screening index proxy (v1.0.0-rf-proxy)",
        "surrogate_status": "OPERATIONAL_EMPIRICAL_SURROGATE",
        "independent_model_status": "UNAVAILABLE"
      },
      "evidence": {
        "meteorological_observations": "NASA POWER MERRA-2 (Monthly 2020-2024)",
        "static_pedology_baseline": "ISRIC SoilGrids 250m (2020 snapshot)",
        "satellite_canopy_vigor": "Sentinel-2 L2A BOA NDVI (10m)",
        "field_soil_cores": "ZERO_OBSERVATIONS_IN_PUBLIC_DOMAIN"
      },
      "limitations": [
        "Current risk score reflects seasonal hydro-thermal pressure, not confirmed physical degradation.",
        "Sentinel-2 NDVI captures surface vegetative vigor, which is sensitive to crop phenology, irrigation, and harvest rather than direct soil structural loss.",
        "ISRIC SoilGrids represents a spatial machine-learning estimate, not multi-temporal in-situ soil sampling.",
        "Physical validation requires repeated georeferenced laboratory core samples."
      ]
    },
    "audit_reference": {
      "assessment_id": "ASM-2024-06-20261017193000",
      "audit_logged": true,
      "log_path": "logs/audit_log.csv",
      "engine_version": "v1.0.0-baseline",
      "source_id": "dashboard_service",
      "recommendation_ids": ["REC-MOISTURE-CRI"],
      "pii_redacted": true
    }
  }
}
```

---

### 3.3 Endpoint: `/api/assessment/scenario`
Simulates a hypothetical weather scenario against a baseline record.

- **Request Body (JSON):**
  ```json
  {
    "date": "2024-06",
    "rainfall_mm": 0.2,
    "temp_c": 42.0,
    "horizon_days": 30
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "success": true,
    "evaluation_date": "2024-06",
    "inputs": {
      "custom_precipitation_mm_day": 0.2,
      "custom_temperature_c": 42.0,
      "horizon_days": 30
    },
    "comparison": {
      "scenario_name": "custom",
      "scenario_atmospheric_score": 92.4,
      "baseline_atmospheric_score": 82.4,
      "delta_score": 10.0,
      "category_shift": "High -> High",
      "resilience_assessment": "Soil vulnerability remains constant; acute heat stress exacerbates moisture deficit."
    }
  }
  ```

---

## 4. Error Code & Status Mappings

| Error Condition | HTTP Code | Error Response Structure | Example Scenario |
| :--- | :---: | :--- | :--- |
| **Invalid Date Format** | `400 Bad Request` | `{"success": false, "error": "Invalid date format. Expected YYYY-MM."}` | Requesting `?date=2024-13-99` |
| **Invalid Scenario Value** | `400 Bad Request` | `{"success": false, "error": "Hypothetical temperature must be between -50.0 and 70.0 degrees Celsius."}` | Submitting `temp_c: 120.0` |
| **Date Not in Dataset** | `404 Not Found` | `{"success": false, "error": "Requested date '2019-12' is not in available dataset records."}` | Requesting date outside 2020–2024 |
| **Unauthenticated Request**| `401 Unauthorized` | `{"error": "Authentication required. Please sign in."}` | Session cookie missing or expired |
| **Role Forbidden** | `403 Forbidden` | `{"error": "Access denied: role mismatch."}` | Farmer accessing researcher admin routes |
| **Backend Internal Fault** | `500 Internal Error` | `{"success": false, "error": "Internal backend error: ..."}` | Python interpreter failure or missing file |

---

## 5. Backward Compatibility Verification Guarantee

1. **Frontend Isolation:** The JavaScript code in `farmer-dashboard.html` and `researcher-dashboard.html` explicitly destructures only the specific keys it renders. Adding `independent_degradation_assessment` introduces zero syntax or runtime conflicts.
2. **Schema Invariance:** The 14-feature ML schema and the 5-indicator risk scoring schema remain identical.
3. **Rollback Simplicity:** Removing the `independent_degradation_assessment` block would require changing only 4 lines of Python code in `src/Model/service.py`, with zero changes needed in any database or frontend template.


## Website visualizations: authenticated observations endpoint

`GET /api/assessment/observations` requires an authenticated session and returns a read-only allow-list from `data/feature_table.csv` through the Python bridge. It exposes only fields needed by the dashboards: monthly date, study region/coordinates, climate time-series variables, depth-specific modeled soil properties, and source/measurement-type metadata.

The endpoint is for rendering charts and a study-area locator. It must not be used to imply parcel-level precision. The current study point is regional; SoilGrids depth-specific values are modeled baselines. The frontend must show a clear unavailable state if this endpoint fails rather than substituting demo numbers.
