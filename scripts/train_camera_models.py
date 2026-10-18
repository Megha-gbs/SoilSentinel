"""
SoilSentinel V6 Global Product - Camera Model Training & Calibration.
=====================================================================
Trains and serializes calibrated vision classifiers for:
1. Crop Foliar Diagnostic Model (Healthy, Nutrient Chlorosis, Leaf Spot Necrosis)
2. Soil Surface Morphology Model (Crusting/Compaction, Water Rill Erosion, Saline Efflorescence)

Uses agronomically extracted optical descriptors (GLI, VARI, Yellow Index, HSV, Lab, Edge energy, Albedo fraction).
Saves models, scalers, and metadata in models/v6_global_product/.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Tuple, List, Dict, Any
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

RAW_CAMERA_DIR = PROJECT_ROOT / "data" / "raw" / "camera"
MODELS_DIR = PROJECT_ROOT / "models" / "v6_global_product"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("train_camera_models")

from src.Vision.camera_ai import get_camera_diagnostic_engine


def extract_dataset_features(img_dir: Path, class_mapping: dict) -> Tuple[np.ndarray, np.ndarray, list]:
    engine = get_camera_diagnostic_engine()
    engine.blur_threshold = 10.0  # Allow calibrated macro evaluation
    
    X_list = []
    y_list = []
    names = []

    for img_path in sorted(img_dir.glob("*.jpg")) + sorted(img_dir.glob("*.jpeg")) + sorted(img_dir.glob("*.JPG")):
        filename = img_path.name
        label = None
        for key, cls_name in class_mapping.items():
            if key in filename.lower():
                label = cls_name
                break
        
        if label is None:
            continue

        img, err = engine.load_image_cv(img_path)
        if err or img is None:
            continue

        desc = engine.extract_visual_descriptors(img)
        feats = [
            desc["green_leaf_index"],
            desc["vari_index"],
            desc["yellow_index"],
            desc["mean_hue"],
            desc["mean_saturation"],
            desc["mean_lab_l"],
            desc["mean_lab_a"],
            desc["mean_lab_b"],
            desc["edge_energy"],
            desc["high_albedo_fraction"]
        ]
        
        # Add slight optical data augmentations (multi-scale scaling and small exposure jitter)
        X_list.append(feats)
        y_list.append(label)
        names.append(filename)

        # Augmentation 1: slight exposure boost
        feats_boost = list(feats)
        feats_boost[5] = min(255.0, feats[5] * 1.05)  # Lab-L
        X_list.append(feats_boost)
        y_list.append(label)

        # Augmentation 2: slight exposure dim
        feats_dim = list(feats)
        feats_dim[5] = max(0.0, feats[5] * 0.95)
        X_list.append(feats_dim)
        y_list.append(label)

    return np.array(X_list), np.array(y_list), names


def train_crop_model():
    logger.info("Training Crop Foliar Diagnostic Model...")
    crop_mapping = {
        "healthy": "HEALTHY_VIGOROUS_FOLIAGE",
        "chlorosis": "NUTRIENT_CHLOROSIS",
        "chlorotic": "NUTRIENT_CHLOROSIS",
        "spot": "LEAF_SPOT_NECROSIS",
        "necrosis": "LEAF_SPOT_NECROSIS"
    }

    X, y, names = extract_dataset_features(RAW_CAMERA_DIR / "crop", crop_mapping)
    logger.info(f"Crop dataset extracted: {X.shape[0]} samples across {len(np.unique(y))} classes: {np.unique(y)}")

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", RandomForestClassifier(n_estimators=50, random_state=42, class_weight="balanced"))
    ])
    pipe.fit(X, y)
    preds = pipe.predict(X)
    acc = accuracy_score(y, preds)
    logger.info(f"Crop model training accuracy: {acc:.3f}")

    joblib.dump(pipe, MODELS_DIR / "camera_crop_model.joblib")
    meta = {
        "model_name": "SoilSentinel V6 Crop Diagnostic Model",
        "version": "v6.0.0-global-product",
        "classes": list(pipe.classes_),
        "feature_names": [
            "green_leaf_index", "vari_index", "yellow_index",
            "mean_hue", "mean_saturation", "mean_lab_l",
            "mean_lab_a", "mean_lab_b", "edge_energy", "high_albedo_fraction"
        ],
        "training_accuracy": acc,
        "sample_count": int(X.shape[0]),
        "source_license": "Public Domain & CC BY / CC BY-SA (Wikimedia & USDA ARS)"
    }
    with open(MODELS_DIR / "camera_crop_metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def train_soil_model():
    logger.info("Training Soil Surface Morphology Model...")
    soil_mapping = {
        "erosion": "SURFACE_WATER_EROSION_RILL",
        "rill": "SURFACE_WATER_EROSION_RILL",
        "crust": "SURFACE_CRUSTING_AND_COMPACTION",
        "compacted": "SURFACE_CRUSTING_AND_COMPACTION",
        "saline": "SALINE_EFFLORESCENCE_CRUST",
        "solonchak": "SALINE_EFFLORESCENCE_CRUST"
    }

    X, y, names = extract_dataset_features(RAW_CAMERA_DIR / "soil", soil_mapping)
    logger.info(f"Soil dataset extracted: {X.shape[0]} samples across {len(np.unique(y))} classes: {np.unique(y)}")

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", RandomForestClassifier(n_estimators=50, random_state=42, class_weight="balanced"))
    ])
    pipe.fit(X, y)
    preds = pipe.predict(X)
    acc = accuracy_score(y, preds)
    logger.info(f"Soil surface model training accuracy: {acc:.3f}")

    joblib.dump(pipe, MODELS_DIR / "camera_soil_model.joblib")
    meta = {
        "model_name": "SoilSentinel V6 Soil Surface Model",
        "version": "v6.0.0-global-product",
        "classes": list(pipe.classes_),
        "feature_names": [
            "green_leaf_index", "vari_index", "yellow_index",
            "mean_hue", "mean_saturation", "mean_lab_l",
            "mean_lab_a", "mean_lab_b", "edge_energy", "high_albedo_fraction"
        ],
        "training_accuracy": acc,
        "sample_count": int(X.shape[0]),
        "source_license": "Public Domain & CC BY (USDA NRCS & CSIRO Australia)"
    }
    with open(MODELS_DIR / "camera_soil_metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


if __name__ == "__main__":
    train_crop_model()
    train_soil_model()
