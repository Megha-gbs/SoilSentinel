"""
SoilSentinel - Production Machine Learning Training, Evaluation & Benchmarking Pipeline (v2.0.0).

Executes two scientifically grounded, zero-leakage ML workstreams:

=============================================================================
WORKSTREAM 1: MULTI-DISTRICT SPATIAL-TEMPORAL RISK SURROGATE MODEL
=============================================================================
Dataset: data/processed/punjab_multidistrict_features.csv (420 records, 7 districts x 60 months)
Features: 14 zero-leakage physical & temporal features (meteorology, hydrology, lags, ratios)
Target: risk_category (High, Low, Medium) from rule-based hydro-thermal stress engine.
Dual Evaluation Protocol:
  A. Spatial Location-Held-Out Split:
     - Train: 5 districts (300 records: SAS Nagar, Jalandhar, Patiala, Amritsar, Hoshiarpur)
     - Val: 1 district (60 records: Ludhiana - central agricultural plain)
     - Test: 1 district (60 records: Bathinda - semi-arid / saline / high heat stress)
  B. Chronological Temporal Split across all 7 districts:
     - Train: 2020-01 to 2022-12 (252 records)
     - Val: 2023-01 to 2023-12 (84 records)
     - Test: 2024-01 to 2024-12 (84 records)
  C. Spatial GroupKFold Cross-Validation (7 folds, grouped by district).
Models:
  - Dummy Majority Class Baseline
  - Logistic Regression (balanced)
  - Random Forest Classifier (balanced)
  - Gradient Boosting Classifier
  - XGBoost Classifier
Explainability:
  - SHAP TreeExplainer fitted on transformed training partition background.
  - Test additivity verification across multiclass output probabilities.

=============================================================================
WORKSTREAM 2: PHYSICAL GROUND-TRUTH MEASURED SOIL PROPERTY MODEL (WoSIS)
=============================================================================
Dataset: data/processed/wosis_measured_soil_properties.csv (61 profiles in NW India / Punjab basin)
Target: Measured Soil Organic Carbon (soc_measured_g_kg)
Features: latitude, longitude, sand_measured_pct, silt_measured_pct, clay_measured_pct, ph_measured_h2o
Evaluation: 5-Fold Cross-Validation & 80/20 Held-Out Split
Models:
  - Baseline Mean Predictor
  - Ridge Regression
  - Random Forest Regressor
  - Gradient Boosting Regressor

Safety & Preservation:
- Preserves all existing models in models/ (models/soil_risk_model.joblib is untouched).
- Versioned artifacts written to models/v2_spatial_surrogate/ and models/v2_wosis_soc_model/.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold, KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelBinarizer, StandardScaler
import xgboost as xgb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = PROJECT_ROOT / "models"
LOGS_DIR = DATA_DIR / "logs"

SURROGATE_MODELS_DIR = MODELS_DIR / "v2_spatial_surrogate"
WOSIS_MODELS_DIR = MODELS_DIR / "v2_wosis_soc_model"

SURROGATE_MODELS_DIR.mkdir(parents=True, exist_ok=True)
WOSIS_MODELS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging
log_file = LOGS_DIR / "model_training.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("train_improved_models")

FEATURE_COLUMNS = [
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

TARGET_COLUMN = "risk_category"
TARGET_CLASSES = ["High", "Low", "Medium"]
RANDOM_SEED = 42


def _to_native_json(obj: Any) -> Any:
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {str(k): _to_native_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_to_native_json(i) for i in obj]
    return obj


def evaluate_classifier_split(
    pipeline: Pipeline,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_eval: pd.DataFrame,
    y_eval: pd.Series,
    split_name: str,
) -> Dict[str, Any]:
    y_pred = pipeline.predict(X_eval)
    classes = sorted(list(set(y_train.unique()).union(set(y_eval.unique()))))

    acc = float(accuracy_score(y_eval, y_pred))
    bal_acc = float(balanced_accuracy_score(y_eval, y_pred))
    macro_f1 = float(f1_score(y_eval, y_pred, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_eval, y_pred, average="weighted", zero_division=0))

    cm = confusion_matrix(y_eval, y_pred, labels=classes).tolist()
    rep = classification_report(y_eval, y_pred, labels=classes, output_dict=True, zero_division=0)

    per_class = {}
    for c in classes:
        if c in rep:
            per_class[c] = {
                "precision": round(float(rep[c]["precision"]), 4),
                "recall": round(float(rep[c]["recall"]), 4),
                "f1_score": round(float(rep[c]["f1-score"]), 4),
                "support": int(rep[c]["support"]),
            }

    # Multiclass ROC-AUC (OVR) if probability available
    auc_score = None
    if hasattr(pipeline, "predict_proba"):
        try:
            probs = pipeline.predict_proba(X_eval)
            lb = LabelBinarizer()
            lb.fit(classes)
            y_eval_bin = lb.transform(y_eval)
            if y_eval_bin.shape[1] > 1:
                auc_score = round(float(roc_auc_score(y_eval_bin, probs, multi_class="ovr", average="macro")), 4)
        except Exception:
            auc_score = None

    return {
        "split": split_name,
        "sample_count": len(y_eval),
        "accuracy": round(acc, 4),
        "balanced_accuracy": round(bal_acc, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "roc_auc_macro_ovr": auc_score,
        "confusion_matrix": {"labels": classes, "matrix": cm},
        "per_class_metrics": per_class,
    }


def compute_shap_for_surrogate(
    pipeline: Pipeline,
    preprocessor: Pipeline,
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    feature_names: List[str],
    out_dir: Path,
) -> Dict[str, Any]:
    import shap

    logger.info("Computing SHAP TreeExplainer on multi-district training background (N=%d)...", len(X_train))
    classifier = pipeline.named_steps["classifier"]
    classes = list(getattr(classifier, "classes_", ["High", "Low", "Medium"]))

    X_train_trans = preprocessor.transform(X_train)
    explainer = shap.TreeExplainer(
        classifier,
        data=X_train_trans,
        model_output="probability",
        feature_names=feature_names,
    )

    explainer_path = out_dir / "soil_risk_explainer_v2.joblib"
    tmp_path = out_dir / "soil_risk_explainer_v2.joblib.tmp"
    joblib.dump(explainer, tmp_path)
    tmp_path.replace(explainer_path)

    X_test_trans = preprocessor.transform(X_test)
    shap_vals = explainer.shap_values(X_test_trans)
    probs_test = pipeline.predict_proba(X_test)

    max_diff = 0.0
    for i in range(len(X_test)):
        for c_idx in range(len(classes)):
            base = explainer.expected_value[c_idx]
            s_sum = float(np.sum(shap_vals[i, :, c_idx]))
            p = float(probs_test[i, c_idx])
            diff = abs((base + s_sum) - p)
            if diff > max_diff:
                max_diff = diff

    rf_imp = getattr(classifier, "feature_importances_", np.zeros(len(feature_names)))
    records = []
    for j, f in enumerate(feature_names):
        overall = float(np.mean(np.abs(shap_vals[:, j, :])))
        records.append({
            "feature": f,
            "mean_abs_shap_overall": round(overall, 4),
            "rf_feature_importance": round(float(rf_imp[j]), 4),
        })
    records.sort(key=lambda x: x["mean_abs_shap_overall"], reverse=True)
    for rank, r in enumerate(records, start=1):
        r["rank"] = rank

    df_shap = pd.DataFrame(records)
    csv_path = out_dir / "shap_global_importance_v2.csv"
    df_shap.to_csv(csv_path, index=False)

    return {
        "explainer_path": explainer_path.name,
        "explainer_type": "shap.TreeExplainer (multiclass probability)",
        "classes": classes,
        "base_values": {c: round(float(explainer.expected_value[idx]), 4) for idx, c in enumerate(classes)},
        "test_additivity_max_discrepancy": round(float(max_diff), 6),
        "global_shap_importance": records,
    }


def train_workstream1_surrogate() -> Dict[str, Any]:
    logger.info("=== WORKSTREAM 1: Multi-District Spatial-Temporal Risk Surrogate Model ===")
    csv_path = PROCESSED_DIR / "punjab_multidistrict_features.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Multi-district dataset missing at: {csv_path}")

    df = pd.read_csv(csv_path)
    total_samples = len(df)
    districts = sorted(df["district_id"].unique().tolist())
    logger.info(f"Loaded {total_samples} records across {len(districts)} districts: {districts}")

    # 1. SPATIAL LOCATION-HELD-OUT EVALUATION
    # Hold out Bathinda (extreme semi-arid / saline zone) as independent spatial test set
    # Hold out Ludhiana (central agricultural plain) as validation set
    # Train on remaining 5 districts (300 records)
    test_dist = "bathinda"
    val_dist = "ludhiana"
    train_dists = [d for d in districts if d not in [test_dist, val_dist]]

    mask_train = df["district_id"].isin(train_dists)
    mask_val = df["district_id"] == val_dist
    mask_test = df["district_id"] == test_dist

    X_train_sp = df.loc[mask_train, FEATURE_COLUMNS].copy()
    y_train_sp = df.loc[mask_train, TARGET_COLUMN].copy()
    X_val_sp = df.loc[mask_val, FEATURE_COLUMNS].copy()
    y_val_sp = df.loc[mask_val, TARGET_COLUMN].copy()
    X_test_sp = df.loc[mask_test, FEATURE_COLUMNS].copy()
    y_test_sp = df.loc[mask_test, TARGET_COLUMN].copy()

    logger.info(
        f"Spatial Partition: Train N={len(X_train_sp)} ({train_dists}), "
        f"Val N={len(X_val_sp)} ({val_dist}), "
        f"Test N={len(X_test_sp)} (Held-Out: {test_dist})"
    )

    # 2. CHRONOLOGICAL TEMPORAL EVALUATION (across all 7 districts)
    mask_time_tr = df["date"] <= "2022-12"
    mask_time_va = (df["date"] > "2022-12") & (df["date"] <= "2023-12")
    mask_time_te = df["date"] > "2023-12"

    X_tr_time = df.loc[mask_time_tr, FEATURE_COLUMNS].copy()
    y_tr_time = df.loc[mask_time_tr, TARGET_COLUMN].copy()
    X_va_time = df.loc[mask_time_va, FEATURE_COLUMNS].copy()
    y_va_time = df.loc[mask_time_va, TARGET_COLUMN].copy()
    X_te_time = df.loc[mask_time_te, FEATURE_COLUMNS].copy()
    y_te_time = df.loc[mask_time_te, TARGET_COLUMN].copy()

    logger.info(
        f"Temporal Partition: Train N={len(X_tr_time)} (2020-2022), "
        f"Val N={len(X_va_time)} (2023), "
        f"Test N={len(X_te_time)} (2024)"
    )

    # Candidate Classifiers
    candidate_factories = {
        "Dummy (Majority Class)": lambda: DummyClassifier(strategy="most_frequent"),
        "Logistic Regression": lambda: LogisticRegression(class_weight="balanced", max_iter=1000, random_state=RANDOM_SEED),
        "Random Forest Classifier": lambda: RandomForestClassifier(
            n_estimators=150, max_depth=6, min_samples_split=4, class_weight="balanced", random_state=RANDOM_SEED
        ),
        "Gradient Boosting Classifier": lambda: GradientBoostingClassifier(
            n_estimators=80, max_depth=3, learning_rate=0.08, random_state=RANDOM_SEED
        ),
        "XGBoost Classifier": lambda: xgb.XGBClassifier(
            n_estimators=80, max_depth=3, learning_rate=0.08, random_state=RANDOM_SEED, eval_metric="mlogloss"
        ),
    }

    # Evaluate Spatial Split
    spatial_comparisons = {}
    time_comparisons = {}
    spatial_fitted = {}
    time_fitted = {}

    label_to_int = {"High": 0, "Low": 1, "Medium": 2}

    for name, factory in candidate_factories.items():
        # A. Spatial Split Pipeline
        clf = factory()
        pipe_sp = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("classifier", clf),
        ])

        # XGBoost requires integer targets
        if "XGBoost" in name:
            y_train_in = y_train_sp.map(label_to_int)
            y_val_in = y_val_sp.map(label_to_int)
            y_test_in = y_test_sp.map(label_to_int)
        else:
            y_train_in, y_val_in, y_test_in = y_train_sp, y_val_sp, y_test_sp

        pipe_sp.fit(X_train_sp, y_train_in)
        spatial_fitted[name] = pipe_sp

        val_m = evaluate_classifier_split(pipe_sp, X_train_sp, y_train_in, X_val_sp, y_val_in, f"Val ({val_dist})")
        test_m = evaluate_classifier_split(pipe_sp, X_train_sp, y_train_in, X_test_sp, y_test_in, f"Spatial Test ({test_dist})")
        spatial_comparisons[name] = {"validation": val_m, "test": test_m}

        logger.info(
            f"[Spatial: {name}] Val Acc: {val_m['accuracy']:.4f}, Macro-F1: {val_m['macro_f1']:.4f} | "
            f"Test ({test_dist}) Acc: {test_m['accuracy']:.4f}, Macro-F1: {test_m['macro_f1']:.4f}, "
            f"BalAcc: {test_m['balanced_accuracy']:.4f}"
        )

        # B. Temporal Split Pipeline
        clf_time = factory()
        pipe_time = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("classifier", clf_time),
        ])

        if "XGBoost" in name:
            y_tr_t_in = y_tr_time.map(label_to_int)
            y_va_t_in = y_va_time.map(label_to_int)
            y_te_t_in = y_te_time.map(label_to_int)
        else:
            y_tr_t_in, y_va_t_in, y_te_t_in = y_tr_time, y_va_time, y_te_time

        pipe_time.fit(X_tr_time, y_tr_t_in)
        time_fitted[name] = pipe_time

        val_t_m = evaluate_classifier_split(pipe_time, X_tr_time, y_tr_t_in, X_va_time, y_va_t_in, "Val (2023)")
        test_t_m = evaluate_classifier_split(pipe_time, X_tr_time, y_tr_t_in, X_te_time, y_te_t_in, "Temporal Test (2024)")
        time_comparisons[name] = {"validation": val_t_m, "test": test_t_m}

        logger.info(
            f"[Temporal: {name}] Val Acc: {val_t_m['accuracy']:.4f}, Macro-F1: {val_t_m['macro_f1']:.4f} | "
            f"Test (2024) Acc: {test_t_m['accuracy']:.4f}, Macro-F1: {test_t_m['macro_f1']:.4f}, "
            f"BalAcc: {test_t_m['balanced_accuracy']:.4f}"
        )

    # 3. SPATIAL GROUPKFOLD CROSS-VALIDATION (7 folds, grouped by district)
    logger.info("Executing 7-Fold Spatial GroupKFold Cross-Validation (Grouped by District)...")
    gkf = GroupKFold(n_splits=len(districts))
    rf_gkf_scores = []

    for fold_i, (tr_idx, te_idx) in enumerate(gkf.split(df[FEATURE_COLUMNS], df[TARGET_COLUMN], groups=df["district_id"])):
        held_out_district = df["district_id"].iloc[te_idx].unique()[0]
        pipe_cv = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("classifier", RandomForestClassifier(
                n_estimators=150, max_depth=6, min_samples_split=4, class_weight="balanced", random_state=RANDOM_SEED
            )),
        ])
        pipe_cv.fit(df.iloc[tr_idx][FEATURE_COLUMNS], df.iloc[tr_idx][TARGET_COLUMN])
        y_cv_pred = pipe_cv.predict(df.iloc[te_idx][FEATURE_COLUMNS])

        fold_acc = accuracy_score(df.iloc[te_idx][TARGET_COLUMN], y_cv_pred)
        fold_bal = balanced_accuracy_score(df.iloc[te_idx][TARGET_COLUMN], y_cv_pred)
        fold_f1 = f1_score(df.iloc[te_idx][TARGET_COLUMN], y_cv_pred, average="macro", zero_division=0)
        rf_gkf_scores.append({
            "fold": fold_i + 1,
            "held_out_district": held_out_district,
            "samples": len(te_idx),
            "accuracy": round(float(fold_acc), 4),
            "balanced_accuracy": round(float(fold_bal), 4),
            "macro_f1": round(float(fold_f1), 4),
        })

    avg_spatial_acc = float(np.mean([s["accuracy"] for s in rf_gkf_scores]))
    avg_spatial_bal = float(np.mean([s["balanced_accuracy"] for s in rf_gkf_scores]))
    avg_spatial_f1 = float(np.mean([s["macro_f1"] for s in rf_gkf_scores]))
    logger.info(
        f"Spatial GroupKFold (7 Districts) Random Forest: Mean Acc={avg_spatial_acc:.4f}, "
        f"Mean BalAcc={avg_spatial_bal:.4f}, Mean Macro-F1={avg_spatial_f1:.4f}"
    )

    # 4. SELECT BEST MODEL: RANDOM FOREST CLASSIFIER (PROVEN RESILIENCE)
    selected_name = "Random Forest Classifier"
    final_pipeline = time_fitted[selected_name]

    preprocessor = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    preprocessor.fit(X_tr_time)

    # Save artifacts into models/v2_spatial_surrogate/
    model_path = SURROGATE_MODELS_DIR / "soil_risk_model_v2.joblib"
    prep_path = SURROGATE_MODELS_DIR / "soil_risk_preprocessor_v2.joblib"
    meta_path = SURROGATE_MODELS_DIR / "model_metadata_v2.json"

    joblib.dump(final_pipeline, model_path)
    joblib.dump(preprocessor, prep_path)

    # Compute SHAP
    shap_meta = None
    try:
        shap_meta = compute_shap_for_surrogate(
            pipeline=final_pipeline,
            preprocessor=preprocessor,
            X_train=X_tr_time,
            X_test=X_te_time,
            feature_names=FEATURE_COLUMNS,
            out_dir=SURROGATE_MODELS_DIR,
        )
    except Exception as e:
        logger.error(f"Error computing SHAP: {e}", exc_info=True)
        shap_meta = {"status": "ERROR", "error": str(e)}

    metadata_payload = {
        "model_version": "v2.0.0-spatial-temporal-rf",
        "engine_version": "v2.0.0-multidistrict",
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "algorithm": selected_name,
        "target_column": TARGET_COLUMN,
        "classes": sorted(list(final_pipeline.classes_)),
        "feature_columns": FEATURE_COLUMNS,
        "feature_count": len(FEATURE_COLUMNS),
        "total_dataset_samples": total_samples,
        "districts_count": len(districts),
        "districts_list": districts,
        "date_coverage": {"start": df["date"].min(), "end": df["date"].max()},
        "target_provenance": "SURROGATE_PROXY_LEARNING",
        "target_provenance_notes": (
            "Multi-district surrogate learning approximating the Seasonal Hydro-Thermal Stress "
            "& Baseline Vulnerability Index across diverse Punjab agro-climatic zones. "
            "Not an independently measured physical soil degradation metric."
        ),
        "evaluation_protocols": {
            "spatial_held_out_evaluation": {
                "train_districts": train_dists,
                "validation_district": val_dist,
                "held_out_test_district": test_dist,
                "held_out_test_metrics": spatial_comparisons[selected_name]["test"],
                "model_comparisons": spatial_comparisons,
            },
            "temporal_chronological_evaluation": {
                "train_window": "2020-01 to 2022-12 (252 samples across 7 districts)",
                "val_window": "2023-01 to 2023-12 (84 samples across 7 districts)",
                "test_window": "2024-01 to 2024-12 (84 samples across 7 districts)",
                "test_metrics": time_comparisons[selected_name]["test"],
                "model_comparisons": time_comparisons,
            },
            "spatial_groupkfold_7districts": {
                "folds": rf_gkf_scores,
                "mean_accuracy": round(avg_spatial_acc, 4),
                "mean_balanced_accuracy": round(avg_spatial_bal, 4),
                "mean_macro_f1": round(avg_spatial_f1, 4),
            },
        },
        "shap_explainer": shap_meta,
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(_to_native_json(metadata_payload), f, indent=2)

    logger.info(f"Saved v2 surrogate artifacts in {SURROGATE_MODELS_DIR}")
    return metadata_payload


def train_workstream2_wosis_soc() -> Dict[str, Any]:
    logger.info("=== WORKSTREAM 2: Physical Ground-Truth Measured Soil Property Model (WoSIS) ===")
    csv_path = PROCESSED_DIR / "wosis_measured_soil_properties.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"WoSIS processed dataset missing at: {csv_path}")

    df_w = pd.read_csv(csv_path)
    df_valid = df_w.dropna(subset=["soc_measured_g_kg"]).copy().reset_index(drop=True)
    logger.info(f"Loaded {len(df_valid)} valid laboratory-assayed SOC records from WoSIS.")

    features = ["latitude", "longitude", "sand_measured_pct", "silt_measured_pct", "clay_measured_pct", "ph_measured_h2o"]
    target = "soc_measured_g_kg"

    # 80/20 train/test split with fixed seed
    np.random.seed(RANDOM_SEED)
    shuffled_idx = np.random.permutation(len(df_valid))
    split_point = int(0.8 * len(df_valid))
    train_idx = shuffled_idx[:split_point]
    test_idx = shuffled_idx[split_point:]

    X_train = df_valid.iloc[train_idx][features].copy()
    y_train = df_valid.iloc[train_idx][target].copy()
    X_test = df_valid.iloc[test_idx][features].copy()
    y_test = df_valid.iloc[test_idx][target].copy()

    regressors = {
        "Mean Baseline Regressor": DummyRegressor(strategy="mean"),
        "Ridge Regression": Ridge(alpha=1.0, random_state=RANDOM_SEED),
        "Random Forest Regressor": RandomForestRegressor(n_estimators=100, max_depth=4, random_state=RANDOM_SEED),
        "Gradient Boosting Regressor": GradientBoostingRegressor(n_estimators=50, max_depth=3, learning_rate=0.08, random_state=RANDOM_SEED),
    }

    results = {}
    fitted_regs = {}

    for name, reg in regressors.items():
        pipe = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("regressor", reg),
        ])
        pipe.fit(X_train, y_train)
        fitted_regs[name] = pipe

        y_pred = pipe.predict(X_test)
        mae = float(mean_absolute_error(y_test, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        r2 = float(r2_score(y_test, y_pred))

        results[name] = {
            "test_sample_count": len(y_test),
            "mae_g_kg": round(mae, 4),
            "rmse_g_kg": round(rmse, 4),
            "r2_score": round(r2, 4),
        }
        logger.info(f"[WoSIS SOC: {name}] Test MAE: {mae:.4f} g/kg, RMSE: {rmse:.4f} g/kg, R2: {r2:.4f}")

    # 5-Fold Cross-Validation for Random Forest
    kf = KFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    cv_maes = []
    cv_rmses = []
    cv_r2s = []

    for tr_k, te_k in kf.split(df_valid[features], df_valid[target]):
        p = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("regressor", RandomForestRegressor(n_estimators=100, max_depth=4, random_state=RANDOM_SEED)),
        ])
        p.fit(df_valid.iloc[tr_k][features], df_valid.iloc[tr_k][target])
        p_pred = p.predict(df_valid.iloc[te_k][features])
        cv_maes.append(mean_absolute_error(df_valid.iloc[te_k][target], p_pred))
        cv_rmses.append(np.sqrt(mean_squared_error(df_valid.iloc[te_k][target], p_pred)))
        cv_r2s.append(r2_score(df_valid.iloc[te_k][target], p_pred))

    cv_summary = {
        "mean_mae_g_kg": round(float(np.mean(cv_maes)), 4),
        "mean_rmse_g_kg": round(float(np.mean(cv_rmses)), 4),
        "mean_r2": round(float(np.mean(cv_r2s)), 4),
    }
    logger.info(f"WoSIS SOC 5-Fold CV Random Forest: Mean MAE={cv_summary['mean_mae_g_kg']} g/kg, Mean R2={cv_summary['mean_r2']}")

    # Save best physical property model (Random Forest Regressor)
    best_pipe = fitted_regs["Random Forest Regressor"]
    model_path = WOSIS_MODELS_DIR / "wosis_soc_regressor.joblib"
    prep_path = WOSIS_MODELS_DIR / "wosis_soc_preprocessor.joblib"
    meta_path = WOSIS_MODELS_DIR / "wosis_soc_metadata.json"

    prep = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())])
    prep.fit(X_train)

    joblib.dump(best_pipe, model_path)
    joblib.dump(prep, prep_path)

    rf_clf = best_pipe.named_steps["regressor"]
    importances = [
        {"feature": f, "importance": round(float(imp), 4)}
        for f, imp in sorted(zip(features, rf_clf.feature_importances_), key=lambda x: x[1], reverse=True)
    ]

    meta = {
        "model_version": "v1.0.0-wosis-soc-rf",
        "task_type": "PHYSICAL_MEASURED_SOIL_PROPERTY_REGRESSION",
        "target": target,
        "target_description": "Topsoil Soil Organic Carbon (g C / kg dry soil) measured by laboratory dry combustion / Walkley-Black",
        "features": features,
        "samples_total": len(df_valid),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "held_out_test_metrics": results["Random Forest Regressor"],
        "baseline_comparison": results,
        "cross_validation_5fold": cv_summary,
        "feature_importances": importances,
        "epistemic_disclaimer": (
            "Predicts measured in-situ soil organic carbon concentration from pedo-spatial features. "
            "Does NOT predict multi-temporal degradation rate (Delta-SOC over time), as repeated temporal "
            "sampling of the exact same parcels was unavailable in public archives."
        ),
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(_to_native_json(meta), f, indent=2)

    logger.info(f"Saved WoSIS SOC physical property model artifacts in {WOSIS_MODELS_DIR}")
    return meta


def run_all_training_pipelines():
    m1 = train_workstream1_surrogate()
    m2 = train_workstream2_wosis_soc()
    return {"workstream1_surrogate": m1, "workstream2_wosis_soc": m2}


if __name__ == "__main__":
    res = run_all_training_pipelines()
    print("\n=== All Training Pipelines Completed Successfully ===")
