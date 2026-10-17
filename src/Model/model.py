"""
Soil Sentinel - Model Architecture, Artifact Management & ML Prediction Interface.

Provides safe loading, validation, and inference for the genuinely trained
SoilSentinel machine learning surrogate model artifact (`models/soil_risk_model.joblib`),
while preserving the transparent, rule-based baseline scoring engine in
`src.Model.risk_scoring`.

Safety Guards & Design Principles:
1. SAFE ARTIFACT LOADING:
   - Validates that artifact file exists and is strictly non-zero bytes.
   - Refuses to silently load empty placeholders or corrupted binaries.
   - Asserts the loaded object implements the scikit-learn estimator interface (`predict`).
2. ZERO LEAKAGE INFERENCE:
   - Evaluates predictions using strictly the 14 raw physical and temporal features.
   - Never accesses or requires rule-based sub-scores or composite score.
3. PROXY LEARNING TRANSPARENCY:
   - Exposes predicted class, class probabilities, model version, and target provenance.
   - Distinguishes surrogate approximation from independent physical degradation measurements.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Union

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger("model")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "soil_risk_model.joblib"
DEFAULT_PREPROCESSOR_PATH = PROJECT_ROOT / "models" / "soil_risk_preprocessor.joblib"
DEFAULT_EXPLAINER_PATH = PROJECT_ROOT / "models" / "soil_risk_explainer.joblib"
DEFAULT_METADATA_PATH = PROJECT_ROOT / "models" / "model_metadata.json"

FEATURE_COLUMNS: List[str] = [
    "air_temperature_c",
    "air_humidity_percent",
    "precipitation_mm_day",
    "soil_temperature_layer1_c",
    "soil_moisture_surface_fraction",
    "soil_moisture_rootzone_fraction",
    "precipitation_lag1_mm_day",
    "air_temperature_lag1_c",
    "precipitation_rolling_3m_mean_mm_day",
    "temp_soil_air_diff_c",
    "soil_moisture_depth_gradient",
    "monthly_aridity_index",
    "month_sin",
    "month_cos",
]


def load_model_metadata(metadata_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Load model metadata manifest from JSON.

    Returns empty dictionary if manifest is unavailable.
    """
    path = Path(metadata_path) if metadata_path else DEFAULT_METADATA_PATH
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load model metadata from {path}: {e}")
        return {}


def load_preprocessor(preprocessor_path: Optional[Union[str, Path]] = None) -> Any:
    """
    Safely load and validate the trained preprocessor transformer artifact.

    Safety Guards:
    - Verifies file exists (raises FileNotFoundError if missing).
    - Verifies file is NOT empty / zero bytes (raises RuntimeError if 0 bytes).
    - Verifies deserialized object implements transform method.
    """
    path = Path(preprocessor_path) if preprocessor_path else DEFAULT_PREPROCESSOR_PATH
    if not path.exists():
        raise FileNotFoundError(f"Preprocessor artifact file does not exist at: {path}")

    file_size = path.stat().st_size
    if file_size == 0:
        raise RuntimeError(
            f"SoilSentinel does not load unpopulated preprocessor binaries. "
            f"The file '{path}' is an unpopulated placeholder (0 bytes)."
        )

    try:
        prep = joblib.load(path)
    except Exception as e:
        raise RuntimeError(f"Failed to deserialize preprocessor binary at '{path}': {e}") from e

    if not hasattr(prep, "transform"):
        raise RuntimeError(f"Loaded object from '{path}' is not a valid transformer (missing 'transform').")

    return prep


def load_explainer(explainer_path: Optional[Union[str, Path]] = None) -> Any:
    """
    Safely load and validate the serialized SHAP TreeExplainer artifact.

    Safety Guards:
    - Verifies file exists (raises FileNotFoundError if missing).
    - Verifies file is NOT empty / zero bytes (raises RuntimeError if 0 bytes).
    - Verifies deserialized object implements SHAP explainer interface (e.g. shap_values or callable).
    """
    path = Path(explainer_path) if explainer_path else DEFAULT_EXPLAINER_PATH
    if not path.exists():
        raise FileNotFoundError(f"SHAP explainer artifact file does not exist at: {path}")

    file_size = path.stat().st_size
    if file_size == 0:
        raise RuntimeError(
            f"SoilSentinel does not load or execute unpopulated SHAP explainer binaries. "
            f"The file '{path}' is an unpopulated placeholder (0 bytes). "
            f"Run `python src/Model/train_model.py` to train and serialize the explainer."
        )

    try:
        explainer = joblib.load(path)
    except Exception as e:
        raise RuntimeError(f"Failed to deserialize SHAP explainer binary at '{path}': {e}") from e

    if not (hasattr(explainer, "shap_values") or callable(explainer)):
        raise RuntimeError(
            f"Loaded object from '{path}' is not a valid SHAP explainer (missing 'shap_values' or __call__)."
        )

    return explainer


def load_trained_model(model_path: Optional[Union[str, Path]] = None) -> Any:
    """
    Safely load and validate the trained machine learning model artifact.

    Safety Guards:
    - Verifies file exists (raises FileNotFoundError if missing).
    - Verifies file is NOT empty / zero bytes (raises RuntimeError if 0 bytes).
    - Verifies deserialized object is a valid estimator with a `predict` method.
    """
    path = Path(model_path) if model_path else DEFAULT_MODEL_PATH

    if not path.exists():
        raise FileNotFoundError(f"Model artifact file does not exist at: {path}")

    file_size = path.stat().st_size
    if file_size == 0:
        raise RuntimeError(
            f"SoilSentinel does not load or execute unpopulated ML model binaries. "
            f"The file '{path}' is an unpopulated placeholder (0 bytes). "
            f"Run `python src/Model/train_model.py` to train and serialize a genuine model."
        )

    try:
        model = joblib.load(path)
    except Exception as e:
        raise RuntimeError(f"Failed to deserialize model binary at '{path}': {e}") from e

    if not hasattr(model, "predict"):
        raise RuntimeError(
            f"Loaded object from '{path}' is not a valid scikit-learn estimator "
            f"(missing required 'predict' method)."
        )

    return model


def predict_ml(
    record: Union[Dict[str, Any], pd.Series, pd.DataFrame],
    model: Optional[Any] = None,
    metadata: Optional[Dict[str, Any]] = None,
    model_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Generate an ML surrogate prediction for an environmental feature record.

    Parameters:
        record: Dictionary, pd.Series, or pd.DataFrame containing feature columns.
        model: Pre-loaded estimator pipeline. If None, attempts to load from model_path.
        metadata: Pre-loaded metadata dict. If None, loads from default metadata path.
        model_path: Optional custom path to model artifact.

    Returns:
        Structured dictionary conforming to the dashboard handoff specification:
        {
            "status": "AVAILABLE" | "UNAVAILABLE" | "ERROR",
            "model_version": str,
            "model_type": str,
            "predicted_category": "Low" | "Medium" | "High",
            "class_probabilities": {"High": 0.02, "Low": 0.01, "Medium": 0.97},
            "target_provenance": "SURROGATE_PROXY_LEARNING",
            "top_drivers": list[str],
            "disclaimer": str
        }
    """
    if metadata is None:
        metadata = load_model_metadata()

    if model is None:
        try:
            model = load_trained_model(model_path)
        except Exception as e:
            return {
                "status": "UNAVAILABLE",
                "error": str(e),
                "model_version": metadata.get("model_version", "v1.0.0-rf-proxy"),
                "model_type": metadata.get("algorithm", "Random Forest Classifier"),
                "predicted_category": None,
                "class_probabilities": None,
                "target_provenance": metadata.get("target_provenance", "SURROGATE_PROXY_LEARNING"),
                "top_drivers": [],
                "disclaimer": (
                    "Proxy surrogate prediction approximating the rule-based hydro-thermal risk index. "
                    "Not an independently measured physical soil degradation metric."
                ),
            }

    # Extract 14 features into DataFrame row
    if isinstance(record, pd.DataFrame):
        df_row = record
    elif isinstance(record, pd.Series):
        df_row = pd.DataFrame([record.to_dict()])
    elif isinstance(record, dict):
        df_row = pd.DataFrame([record])
    else:
        raise TypeError(f"Unsupported record type: {type(record)}")

    features_dict = {}
    for col in FEATURE_COLUMNS:
        if col in df_row.columns:
            val = df_row[col].values[0]
            features_dict[col] = float(val) if pd.notna(val) else np.nan
        else:
            features_dict[col] = np.nan

    X = pd.DataFrame([features_dict], columns=FEATURE_COLUMNS)

    try:
        pred_class = model.predict(X)[0]
        probs_dict = None
        if hasattr(model, "predict_proba"):
            probs = model.predict_proba(X)[0]
            classes = list(getattr(model, "classes_", ["High", "Low", "Medium"]))
            probs_dict = {str(c): round(float(p), 4) for c, p in zip(classes, probs)}

        top_drivers = [f["feature"] for f in metadata.get("top_features", [])[:3]]

        return {
            "status": "AVAILABLE",
            "model_version": metadata.get("model_version", "v1.0.0-rf-proxy"),
            "model_type": metadata.get("algorithm", "Random Forest Classifier"),
            "predicted_category": str(pred_class),
            "class_probabilities": probs_dict,
            "target_provenance": metadata.get("target_provenance", "SURROGATE_PROXY_LEARNING"),
            "top_drivers": top_drivers,
            "disclaimer": (
                "Proxy surrogate prediction approximating the rule-based hydro-thermal risk index. "
                "Not an independently measured physical soil degradation metric."
            ),
        }
    except Exception as e:
        logger.warning(f"Error during ML prediction execution: {e}")
        return {
            "status": "ERROR",
            "error": str(e),
            "model_version": metadata.get("model_version", "v1.0.0-rf-proxy"),
            "model_type": metadata.get("algorithm", "Random Forest Classifier"),
            "predicted_category": None,
            "class_probabilities": None,
            "target_provenance": metadata.get("target_provenance", "SURROGATE_PROXY_LEARNING"),
            "top_drivers": [],
            "disclaimer": "Proxy model approximating rule-based index.",
        }


def explain_prediction(
    record: Union[Dict[str, Any], pd.Series, pd.DataFrame],
    model: Optional[Any] = None,
    explainer: Optional[Any] = None,
    preprocessor: Optional[Any] = None,
    metadata: Optional[Dict[str, Any]] = None,
    target_class: Optional[str] = None,
    top_n: int = 5,
    tolerance: float = 0.02,
    model_path: Optional[Union[str, Path]] = None,
    explainer_path: Optional[Union[str, Path]] = None,
    preprocessor_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Generate local SHAP explanations for an environmental record approximating the surrogate model.

    Safety Guards & Multiclass Protocol:
    1. ZERO FABRICATIONS: Returns explicit 'UNAVAILABLE' if artifacts or library are missing,
       and 'ERROR' if additivity check fails; never fabricates values.
    2. EXPLICIT MULTICLASS MAPPING: Explicitly maps class indices to `model.classes_`;
       never assumes alphabetical or numerical class ordering.
    3. ADDITIVITY VALIDATION: Verifies that base_value + sum(shap_values) matches the
       model-estimated class probability within tolerance (default: 0.02).
    4. SURROGATE PROVENANCE: Explicitly clarifies that attributions explain the ML surrogate
       approximation, NOT physical causation or ground-truth soil degradation mechanisms.

    Returns:
        JSON-native dictionary conforming to dashboard handoff specification.
    """
    if metadata is None:
        metadata = load_model_metadata()

    model_version = metadata.get("model_version", "v1.0.0-rf-proxy")
    model_type = metadata.get("algorithm", "Random Forest Classifier")

    # Extract 14 features into DataFrame row and preserve original physical values
    if isinstance(record, pd.DataFrame):
        df_row = record
    elif isinstance(record, pd.Series):
        df_row = pd.DataFrame([record.to_dict()])
    elif isinstance(record, dict):
        df_row = pd.DataFrame([record])
    else:
        raise TypeError(f"Unsupported record type: {type(record)}")

    features_dict = {}
    for col in FEATURE_COLUMNS:
        if col in df_row.columns:
            val = df_row[col].values[0]
            features_dict[col] = float(val) if pd.notna(val) else np.nan
        else:
            features_dict[col] = np.nan

    X_df = pd.DataFrame([features_dict], columns=FEATURE_COLUMNS)
    original_features = {
        k: (round(float(v), 4) if pd.notna(v) else None)
        for k, v in features_dict.items()
    }

    # Helper for fallback unavailable payload
    def _unavailable_payload(err_msg: str) -> Dict[str, Any]:
        return {
            "status": "UNAVAILABLE",
            "error": err_msg,
            "model_version": model_version,
            "model_type": model_type,
            "predicted_class": None,
            "explained_class": None,
            "prediction_probability": None,
            "base_value": None,
            "sum_shap_values": None,
            "reconstituted_probability": None,
            "additivity_discrepancy": None,
            "additivity_tolerance": tolerance,
            "output_space": "probability",
            "top_features": [],
            "all_feature_impacts": {},
            "original_features": original_features,
            "methodology": "TreeSHAP (interventional perturbation with training partition background)",
            "causation_warning": (
                "SHAP values quantify statistical feature attributions toward the surrogate model's "
                "predicted class probability. They do NOT represent physical causation or ground-truth "
                "soil degradation mechanisms."
            ),
            "disclaimer": "Surrogate model explanation approximating rule-based Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index.",
        }

    # 1. Ensure Model is Loaded
    if model is None:
        try:
            model = load_trained_model(model_path)
        except Exception as e:
            logger.warning(f"Model unavailable for SHAP explanation: {e}")
            return _unavailable_payload(f"Model artifact unavailable: {e}")

    # 2. Ensure SHAP Explainer is Loaded
    if explainer is None:
        try:
            explainer = load_explainer(explainer_path)
        except Exception as e:
            logger.warning(f"SHAP explainer unavailable: {e}")
            return _unavailable_payload(f"SHAP explainer artifact unavailable: {e}")

    # 3. Ensure Preprocessor is Loaded
    if preprocessor is None:
        try:
            preprocessor = load_preprocessor(preprocessor_path)
        except Exception:
            # Fallback to pipeline steps if preprocessor artifact missing
            if hasattr(model, "named_steps") and "imputer" in model.named_steps and "scaler" in model.named_steps:
                from sklearn.pipeline import Pipeline
                preprocessor = Pipeline([
                    ("imputer", model.named_steps["imputer"]),
                    ("scaler", model.named_steps["scaler"]),
                ])
            else:
                return _unavailable_payload("Preprocessor artifact unavailable for feature transformation.")

    # 4. Perform Prediction & Probability Estimation
    try:
        pred_class = str(model.predict(X_df)[0])
        probs = model.predict_proba(X_df)[0]
        # Resolve class names explicitly from model
        if hasattr(model, "classes_"):
            classes = [str(c) for c in model.classes_]
        elif hasattr(model, "named_steps") and hasattr(model.named_steps.get("classifier"), "classes_"):
            classes = [str(c) for c in model.named_steps["classifier"].classes_]
        else:
            classes = ["High", "Low", "Medium"]
    except Exception as e:
        logger.warning(f"Model prediction failed during explanation: {e}")
        return {
            "status": "ERROR",
            "error": f"Model inference failed: {e}",
            "model_version": model_version,
            "model_type": model_type,
            "predicted_class": None,
            "explained_class": None,
            "prediction_probability": None,
            "base_value": None,
            "sum_shap_values": None,
            "reconstituted_probability": None,
            "additivity_discrepancy": None,
            "additivity_tolerance": tolerance,
            "output_space": "probability",
            "top_features": [],
            "all_feature_impacts": {},
            "original_features": original_features,
            "methodology": "TreeSHAP (interventional perturbation with training partition background)",
            "causation_warning": "SHAP explains surrogate model approximations, not physical causation.",
            "disclaimer": "Surrogate model explanation approximating rule-based index.",
        }

    # 5. Resolve Target Class and Explicit Multiclass Index
    explained_class = str(target_class) if target_class is not None else pred_class
    if explained_class not in classes:
        return {
            "status": "ERROR",
            "error": f"Target class '{explained_class}' not found in model classes: {classes}",
            "model_version": model_version,
            "model_type": model_type,
            "predicted_class": pred_class,
            "explained_class": explained_class,
            "prediction_probability": None,
            "base_value": None,
            "sum_shap_values": None,
            "reconstituted_probability": None,
            "additivity_discrepancy": None,
            "additivity_tolerance": tolerance,
            "output_space": "probability",
            "top_features": [],
            "all_feature_impacts": {},
            "original_features": original_features,
            "methodology": "TreeSHAP (interventional perturbation with training partition background)",
            "causation_warning": "SHAP explains surrogate model approximations, not physical causation.",
            "disclaimer": "Surrogate model explanation approximating rule-based index.",
        }

    class_idx = classes.index(explained_class)
    pred_prob = float(probs[class_idx])

    # 6. Transform Features and Compute SHAP Values
    try:
        X_trans = preprocessor.transform(X_df)
        raw_shap = explainer.shap_values(X_trans)
    except Exception as e:
        logger.warning(f"SHAP computation failed: {e}")
        return {
            "status": "ERROR",
            "error": f"SHAP value computation failed: {e}",
            "model_version": model_version,
            "model_type": model_type,
            "predicted_class": pred_class,
            "explained_class": explained_class,
            "prediction_probability": round(pred_prob, 4),
            "base_value": None,
            "sum_shap_values": None,
            "reconstituted_probability": None,
            "additivity_discrepancy": None,
            "additivity_tolerance": tolerance,
            "output_space": "probability",
            "top_features": [],
            "all_feature_impacts": {},
            "original_features": original_features,
            "methodology": "TreeSHAP (interventional perturbation with training partition background)",
            "causation_warning": "SHAP explains surrogate model approximations, not physical causation.",
            "disclaimer": "Surrogate model explanation approximating rule-based index.",
        }

    # 7. Extract Class Slice and Validate Output Shape
    if isinstance(raw_shap, list):
        if class_idx >= len(raw_shap):
            return {
                "status": "ERROR",
                "error": f"SHAP list output index {class_idx} out of range (length {len(raw_shap)})",
                "model_version": model_version,
                "model_type": model_type,
                "predicted_class": pred_class,
                "explained_class": explained_class,
                "prediction_probability": round(pred_prob, 4),
                "base_value": None,
                "sum_shap_values": None,
                "reconstituted_probability": None,
                "additivity_discrepancy": None,
                "additivity_tolerance": tolerance,
                "output_space": "probability",
                "top_features": [],
                "all_feature_impacts": {},
                "original_features": original_features,
                "methodology": "TreeSHAP",
                "causation_warning": "SHAP explains surrogate model approximations, not physical causation.",
                "disclaimer": "Surrogate model explanation approximating rule-based index.",
            }
        class_shap = raw_shap[class_idx][0]
    elif isinstance(raw_shap, np.ndarray):
        if raw_shap.ndim == 3:
            class_shap = raw_shap[0, :, class_idx]
        elif raw_shap.ndim == 2:
            class_shap = raw_shap[0]
        else:
            return {
                "status": "ERROR",
                "error": f"Unexpected SHAP array dimensionality: {raw_shap.ndim}",
                "model_version": model_version,
                "model_type": model_type,
                "predicted_class": pred_class,
                "explained_class": explained_class,
                "prediction_probability": round(pred_prob, 4),
                "base_value": None,
                "sum_shap_values": None,
                "reconstituted_probability": None,
                "additivity_discrepancy": None,
                "additivity_tolerance": tolerance,
                "output_space": "probability",
                "top_features": [],
                "all_feature_impacts": {},
                "original_features": original_features,
                "methodology": "TreeSHAP",
                "causation_warning": "SHAP explains surrogate model approximations, not physical causation.",
                "disclaimer": "Surrogate model explanation approximating rule-based index.",
            }
    else:
        return {
            "status": "ERROR",
            "error": f"Unexpected SHAP output structure type: {type(raw_shap)}",
            "model_version": model_version,
            "model_type": model_type,
            "predicted_class": pred_class,
            "explained_class": explained_class,
            "prediction_probability": round(pred_prob, 4),
            "base_value": None,
            "sum_shap_values": None,
            "reconstituted_probability": None,
            "additivity_discrepancy": None,
            "additivity_tolerance": tolerance,
            "output_space": "probability",
            "top_features": [],
            "all_feature_impacts": {},
            "original_features": original_features,
            "methodology": "TreeSHAP",
            "causation_warning": "SHAP explains surrogate model approximations, not physical causation.",
            "disclaimer": "Surrogate model explanation approximating rule-based index.",
        }

    # Extract class base value
    exp_base = explainer.expected_value
    if isinstance(exp_base, (list, np.ndarray)):
        base_val = float(exp_base[class_idx])
    else:
        base_val = float(exp_base)

    # 8. Additivity Verification
    sum_shap = float(np.sum(class_shap))
    reconstituted = base_val + sum_shap
    discrepancy = abs(reconstituted - pred_prob)

    if discrepancy > tolerance:
        logger.warning(
            f"SHAP additivity verification failed for class '{explained_class}': "
            f"base={base_val:.4f} + sum={sum_shap:.4f} = {reconstituted:.4f} vs prob={pred_prob:.4f} "
            f"(diff={discrepancy:.6f} > tolerance={tolerance:.4f})"
        )
        return {
            "status": "ERROR",
            "error": (
                f"SHAP additivity verification failed: |({base_val:.4f} + {sum_shap:.4f}) - "
                f"{pred_prob:.4f}| = {discrepancy:.6f} exceeds tolerance {tolerance:.4f}."
            ),
            "model_version": model_version,
            "model_type": model_type,
            "predicted_class": pred_class,
            "explained_class": explained_class,
            "prediction_probability": round(pred_prob, 4),
            "base_value": round(base_val, 4),
            "sum_shap_values": round(sum_shap, 4),
            "reconstituted_probability": round(reconstituted, 4),
            "additivity_discrepancy": round(discrepancy, 6),
            "additivity_tolerance": tolerance,
            "output_space": "probability",
            "top_features": [],
            "all_feature_impacts": {},
            "original_features": original_features,
            "methodology": "TreeSHAP (interventional perturbation with training partition background)",
            "causation_warning": (
                "SHAP values quantify statistical feature attributions toward the surrogate model's "
                "predicted class probability. They do NOT represent physical causation or ground-truth "
                "soil degradation mechanisms."
            ),
            "disclaimer": "Explanation rejected due to additivity check failure.",
        }

    # 9. Top Feature Ranking & Signed Impact Assembly
    ranked_indices = np.argsort(np.abs(class_shap))[::-1][:top_n]
    top_features = []
    for rank_num, idx in enumerate(ranked_indices, 1):
        f_name = FEATURE_COLUMNS[idx]
        phi_val = float(class_shap[idx])
        top_features.append({
            "rank": int(rank_num),
            "feature": str(f_name),
            "feature_value": original_features.get(f_name),
            "shap_value": round(phi_val, 4),
            "absolute_impact": round(abs(phi_val), 4),
            "direction": "INCREASES_CLASS_PROBABILITY" if phi_val > 0 else "DECREASES_CLASS_PROBABILITY",
        })

    all_impacts = {
        str(FEATURE_COLUMNS[idx]): round(float(class_shap[idx]), 4)
        for idx in range(len(FEATURE_COLUMNS))
    }

    return {
        "status": "AVAILABLE",
        "model_version": model_version,
        "model_type": model_type,
        "predicted_class": str(pred_class),
        "explained_class": str(explained_class),
        "prediction_probability": round(pred_prob, 4),
        "base_value": round(base_val, 4),
        "sum_shap_values": round(sum_shap, 4),
        "reconstituted_probability": round(reconstituted, 4),
        "additivity_discrepancy": round(discrepancy, 6),
        "additivity_tolerance": float(tolerance),
        "output_space": "probability",
        "top_features": top_features,
        "all_feature_impacts": all_impacts,
        "original_features": original_features,
        "methodology": "TreeSHAP (interventional perturbation with training partition background)",
        "causation_warning": (
            "SHAP values quantify statistical feature attributions toward the surrogate model's "
            "predicted class probability. They do NOT represent physical causation or ground-truth "
            "soil degradation mechanisms."
        ),
        "disclaimer": (
            "Surrogate model explanation approximating rule-based Seasonal Hydro-Thermal "
            "Stress & Baseline Vulnerability Index."
        ),
    }
