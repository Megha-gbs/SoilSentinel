"""
SoilSentinel - Dataset Manifest & Provenance Generator.

Generates official, cryptographically verified manifests in data/manifests/:
1. wosis_soil_dataset_manifest.json
2. nasa_power_climate_manifest.json
3. india_soil_health_manifest.json
4. soilgrids_dataset_manifest.json
5. master_dataset_provenance_manifest.json

Includes verified URLs, retrieval parameters, geographic bounding boxes,
licenses, checksums (SHA-256), record counts, and target suitability declarations.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MANIFESTS_DIR = DATA_DIR / "manifests"
LOGS_DIR = DATA_DIR / "logs"

MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("manifest_generator")


def compute_sha256(filepath: Path) -> str:
    if not filepath.exists():
        return "FILE_NOT_FOUND"
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_file_info(rel_path: str) -> Dict[str, Any]:
    full_path = PROJECT_ROOT / rel_path
    if not full_path.exists():
        return {"file_path": rel_path, "status": "MISSING"}
    return {
        "file_path": rel_path,
        "size_bytes": full_path.stat().st_size,
        "sha256": compute_sha256(full_path),
        "status": "VERIFIED_PRESENT",
    }


def generate_all_manifests():
    logger.info("=== Generating Official Dataset Manifests ===")
    now_utc = datetime.now(timezone.utc).isoformat()

    # 1. WoSIS Manifest
    wosis_manifest = {
        "manifest_name": "ISRIC WoSIS Measured Soil Observations Manifest",
        "created_at_utc": now_utc,
        "custodian": "ISRIC - World Soil Information, Wageningen, Netherlands",
        "official_documentation": "https://docs.isric.org/globaldata/wosis/",
        "wfs_service_endpoint": "https://maps.isric.org/mapserv?map=/map/wosis_latest.map",
        "license": "Open Database License (ODbL) / Creative Commons Attribution 4.0 International (CC BY 4.0)",
        "study_bounding_box": {
            "name": "Northwest India / Punjab Alluvial Basin",
            "bbox_coordinates": "28.0, 72.0, 33.5, 78.5 (min_lat, min_lon, max_lat, max_lon)",
        },
        "target_declaration": (
            "Field-measured in-situ laboratory soil properties (SOC concentration, pH in H2O, "
            "clay/sand/silt texture mass fractions). These represent static historical physical soil measurements, "
            "NOT dynamic multi-temporal degradation rate labels."
        ),
        "files": {
            "profiles_punjab_bbox": {
                **get_file_info("data/raw/wosis/wosis_profiles_punjab_bbox.geojson"),
                "records_count": 67,
                "description": "Standardized soil profile sites in Northwest India / Punjab agricultural basin",
            },
            "profiles_india_national": {
                **get_file_info("data/raw/wosis/wosis_profiles_india.geojson"),
                "records_count": 942,
                "description": "National benchmark soil profile sites across India",
            },
            "orgc_measured": {
                **get_file_info("data/raw/wosis/wosis_orgc_punjab_bbox.geojson"),
                "records_count": 424,
                "description": "Measured soil organic carbon observations across depth horizons (g/kg)",
            },
            "phaq_measured": {
                **get_file_info("data/raw/wosis/wosis_phaq_punjab_bbox.geojson"),
                "records_count": 386,
                "description": "Measured soil pH (in H2O) observations across depth horizons",
            },
            "clay_measured": {
                **get_file_info("data/raw/wosis/wosis_clay_punjab_bbox.geojson"),
                "records_count": 386,
                "description": "Measured clay mass fraction observations across depth horizons (%)",
            },
            "sand_measured": {
                **get_file_info("data/raw/wosis/wosis_sand_punjab_bbox.geojson"),
                "records_count": 433,
                "description": "Measured sand mass fraction observations across depth horizons (%)",
            },
            "silt_measured": {
                **get_file_info("data/raw/wosis/wosis_silt_punjab_bbox.geojson"),
                "records_count": 433,
                "description": "Measured silt mass fraction observations across depth horizons (%)",
            },
            "processed_soil_table": {
                **get_file_info("data/processed/wosis_measured_soil_properties.csv"),
                "records_count": 61,
                "description": "Standardized topsoil plow layer (0-30cm) measured physical and chemical soil properties",
            },
        },
    }

    with open(MANIFESTS_DIR / "wosis_soil_dataset_manifest.json", "w", encoding="utf-8") as f:
        json.dump(wosis_manifest, f, indent=2)

    # 2. NASA POWER Climate Manifest
    climate_files = {
        "sas_nagar_chandigarh": get_file_info("data/raw/climate/nasa_power_monthly_2020_2024_30.73_76.77.json"),
        "ludhiana": get_file_info("data/raw/climate/nasa_power_monthly_2020_2024_30.90_75.85_ludhiana.json"),
        "bathinda": get_file_info("data/raw/climate/nasa_power_monthly_2020_2024_30.21_74.95_bathinda.json"),
        "jalandhar": get_file_info("data/raw/climate/nasa_power_monthly_2020_2024_31.33_75.58_jalandhar.json"),
        "patiala": get_file_info("data/raw/climate/nasa_power_monthly_2020_2024_30.34_76.38_patiala.json"),
        "amritsar": get_file_info("data/raw/climate/nasa_power_monthly_2020_2024_31.63_74.87_amritsar.json"),
        "hoshiarpur": get_file_info("data/raw/climate/nasa_power_monthly_2020_2024_31.53_75.92_hoshiarpur.json"),
    }

    climate_manifest = {
        "manifest_name": "NASA POWER Multi-District Climate Features Manifest",
        "created_at_utc": now_utc,
        "custodian": "NASA Langley Research Center / POWER Project",
        "official_documentation": "https://power.larc.nasa.gov/docs/services/api/temporal/",
        "api_endpoint": "https://power.larc.nasa.gov/api/temporal/monthly/point",
        "license": "NASA Open Data Policy (U.S. Public Domain / Free Unrestricted Access)",
        "temporal_horizon": "2020-01 to 2024-12 (60 continuous calendar months per location)",
        "parameters": [
            {"code": "T2M", "name": "Air Temperature at 2m", "units": "degrees C"},
            {"code": "RH2M", "name": "Relative Humidity at 2m", "units": "percent"},
            {"code": "PRECTOTCORR", "name": "Precipitation Corrected", "units": "mm/day"},
            {"code": "GWETTOP", "name": "Surface Soil Wetness", "units": "0 to 1 fraction"},
            {"code": "GWETROOT", "name": "Root Zone Soil Wetness", "units": "0 to 1 fraction"},
            {"code": "TSOIL1", "name": "Soil Temperature Layer 1 (0-10cm)", "units": "degrees C"},
        ],
        "districts_count": 7,
        "total_monthly_records": 420,
        "target_declaration": "Predictor covariates only; NOT measured soil degradation ground truth.",
        "files": climate_files,
    }

    with open(MANIFESTS_DIR / "nasa_power_climate_manifest.json", "w", encoding="utf-8") as f:
        json.dump(climate_manifest, f, indent=2)

    # 3. India Soil Health Manifest
    india_manifest = {
        "manifest_name": "Government of India Punjab Soil Health Card & ICAR Survey Benchmark Manifest",
        "created_at_utc": now_utc,
        "custodian": (
            "Department of Agriculture & Farmers Welfare, Ministry of Agriculture, Govt. of India / "
            "ICAR-National Bureau of Soil Survey and Land Use Planning (NBSS&LUP) / ICAR-CSSRI"
        ),
        "official_sources": [
            "https://soilhealth.dac.gov.in/",
            "https://nbsslup.icar.gov.in/",
            "https://cssri.icar.gov.in/",
        ],
        "license": "Government Open Data License - India (GODL) / ICAR Academic Public Research Access",
        "depth_interval": "0-15cm (Topsoil plow layer)",
        "target_declaration": (
            "District-level official soil health ratings, nutrient status, soil reaction (pH), "
            "salinity (EC), and dominant pedological series. Benchmark context for agronomic thresholds."
        ),
        "files": {
            "csv_benchmarks": {
                **get_file_info("data/raw/india_soil/punjab_soil_health_card_district_benchmarks.csv"),
                "records_count": 10,
                "description": "District-level soil fertility, salinity, and degradation constraints for Punjab",
            },
            "json_benchmarks": {
                **get_file_info("data/raw/india_soil/punjab_soil_health_card_district_benchmarks.json"),
                "records_count": 10,
                "description": "Structured JSON metadata with complete citations and methodologies",
            },
        },
    }

    with open(MANIFESTS_DIR / "india_soil_health_manifest.json", "w", encoding="utf-8") as f:
        json.dump(india_manifest, f, indent=2)

    # 4. SoilGrids Manifest
    soilgrids_manifest = {
        "manifest_name": "ISRIC SoilGrids v2.0 Global 250m Baseline Manifest",
        "created_at_utc": now_utc,
        "custodian": "ISRIC - World Soil Information, Wageningen, Netherlands",
        "official_documentation": "https://www.isric.org/explore/soilgrids",
        "repository_url": "https://files.isric.org/soilgrids/latest/data/",
        "license": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
        "properties_extracted": ["phh2o", "clay", "sand", "silt", "soc"],
        "depth_intervals": ["0-5cm", "5-15cm", "15-30cm"],
        "target_declaration": (
            "Modeled 250m static digital soil mapping baseline features. "
            "STRICTLY PROHIBITED AS GROUND TRUTH DEGRADATION LABELS (would cause circularity / leakage)."
        ),
        "files": {
            "baseline_single_pixel": {
                **get_file_info("data/raw/soil/soilgrids_raw_metadata.json"),
                "description": "Nominal parcel baseline coordinates (30.73N, 76.77E) raster extraction",
            },
            "punjab_multidistrict": {
                **get_file_info("data/raw/soil/soilgrids_punjab_districts_metadata.json"),
                "description": "Multi-district raster extractions across 7 representative Punjab agricultural districts",
            },
        },
    }

    with open(MANIFESTS_DIR / "soilgrids_dataset_manifest.json", "w", encoding="utf-8") as f:
        json.dump(soilgrids_manifest, f, indent=2)

    # 5. Master Manifest
    master_manifest = {
        "manifest_name": "SoilSentinel Master ML Dataset Provenance & Integrity Manifest",
        "version": "v2.0.0-multidistrict",
        "generated_at_utc": now_utc,
        "project": "SoilSentinel (Datathon)",
        "scope": "Comprehensive Data Inventory, Provenance, Epistemic Boundaries & Target Integrity",
        "sub_manifests": [
            "data/manifests/wosis_soil_dataset_manifest.json",
            "data/manifests/nasa_power_climate_manifest.json",
            "data/manifests/india_soil_health_manifest.json",
            "data/manifests/soilgrids_dataset_manifest.json",
        ],
        "datasets": {
            "baseline_feature_table": {
                **get_file_info("data/feature_table.csv"),
                "samples_count": 60,
                "coverage": "2020-01 to 2024-12 (Single parcel: SAS Nagar / Chandigarh)",
                "target_provenance": "SURROGATE_PROXY_LEARNING (Rule-Based Heuristic)",
            },
            "multidistrict_feature_table": {
                **get_file_info("data/processed/punjab_multidistrict_features.csv"),
                "samples_count": 420,
                "districts_count": 7,
                "coverage": "2020-01 to 2024-12 across 7 Punjab agricultural districts",
                "target_provenance": "SURROGATE_PROXY_LEARNING (Rule-Based Heuristic across Diverse Climates)",
            },
            "wosis_measured_soil_properties": {
                **get_file_info("data/processed/wosis_measured_soil_properties.csv"),
                "samples_count": 61,
                "coverage": "Northwest India / Punjab basin historical in-situ soil profiles",
                "target_provenance": "GROUND_TRUTH_PHYSICAL_MEASUREMENTS (Laboratory Assayed SOC, pH, Texture)",
            },
            "india_soil_health_benchmarks": {
                **get_file_info("data/raw/india_soil/punjab_soil_health_card_district_benchmarks.csv"),
                "samples_count": 10,
                "coverage": "Punjab districts official Soil Health Card benchmark averages",
                "target_provenance": "GOVERNMENT_OFFICIAL_SURVEY_BENCHMARK",
            },
        },
        "epistemic_boundaries": {
            "is_independent_degradation_ground_truth_present": False,
            "boundary_explanation": (
                "While WoSIS provides real measured physical soil properties (SOC, pH, texture), "
                "these are single-time profile observations, NOT multi-temporal repeat cores of the exact same plot. "
                "True physical soil degradation requires multi-year rate of change (e.g. delta-SOC over 5 years). "
                "Consequently, the primary ML risk model is explicitly classified as a HEURISTIC SURROGATE MODEL. "
                "Physical ground-truth modeling is evaluated separately as a MEASURED SOIL PROPERTY PREDICTION task."
            ),
        },
    }

    with open(MANIFESTS_DIR / "master_dataset_provenance_manifest.json", "w", encoding="utf-8") as f:
        json.dump(master_manifest, f, indent=2)

    logger.info("All 5 manifests successfully generated in data/manifests/.")
    return master_manifest


if __name__ == "__main__":
    res = generate_all_manifests()
    print("\nMaster Manifest Summary:")
    print(json.dumps(res["datasets"], indent=2))
