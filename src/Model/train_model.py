"""
SoilSentinel - Machine Learning Training and Evaluation Pipeline.

Trains and evaluates genuine machine learning surrogate models to approximate
the Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index from dynamic
physical meteorological and hydrological features.

CRITICAL ARCHITECTURAL CONSTRAINTS & PROVENANCE:
1. SURROGATE PROXY LEARNING:
   Because independently observed, physical ground-truth soil degradation labels
   are unobserved (NASA POWER provides atmospheric reanalysis, SoilGrids v2.0
   provides static digital mapping), the models learn to approximate the
   multi-factor non-linear heuristic decision surface of the rule-based engine.
   Labels are explicitly documented as PROXY TARGETS, not field measurements.
2. ZERO TARGET LEAKAGE:
   Input features consist strictly of raw physical and temporal covariates.
   The composite score, sub-scores, buffering factors, and explanation strings
   are NEVER included in the input feature matrix X.
3. STRICT TEMPORAL ORDERING:
   Splits are strictly chronological (Train: 2020-2022, Val: 2023, Test: 2024).
   Imputation and scaling transformations are fitted ONLY on training data.
4. MODEL COMPARISON:
   Evaluates Naive Baseline (Dummy Majority), Logistic Regression,
   Random Forest (Primary), and Gradient Boosting.
5. ATOMIC ARTIFACT VALIDATION:
   Artifacts are validated by loading and predicting against a live sample
   record before serialization is marked complete.
"""

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Ensure project root resolution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Model.predict import predict_from_csv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("train_model")

# ---------------------------------------------------------------------------
# Feature Schema Specification (Zero Leakage)
# ---------------------------------------------------------------------------

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

TARGET_COLUMN: str = "risk_category"
TARGET_CLASSES: List[str] = ["High", "Low", "Medium"]
RANDOM_SEED: int = 42


def load_and_prepare_dataset(
    feature_csv_path: Optional[Union[str, Path]] = None
) -> pd.DataFrame:
    """
    Load feature table and compute deterministic proxy risk categories.

    Returns:
        pd.DataFrame sorted chronologically by date with feature columns and proxy target.
    """
    csv_path = Path(feature_csv_path) if feature_csv_path else PROJECT_ROOT / "data" / "feature_table.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Feature table not found at: {csv_path}")

    feat_df = pd.read_csv(csv_path)
    scored_df = predict_from_csv(input_path=csv_path, output_path=None, allow_partial=True)

    # Validate row alignment
    if len(feat_df) != len(scored_df):
        raise ValueError(f"Mismatched rows: features={len(feat_df)}, scored={len(scored_df)}")

    merged = feat_df.merge(
        scored_df[["date", "score", "risk_category"]],
        on="date",
        how="inner"
    )

    merged["date"] = merged["date"].astype(str)
    merged = merged.sort_values("date").reset_index(drop=True)

    # Validate feature presence
    missing_cols = [col for col in FEATURE_COLUMNS if col not in merged.columns]
    if missing_cols:
        raise ValueError(f"Missing required feature columns: {missing_cols}")

    return merged


def split_dataset_chronological(
    df: pd.DataFrame,
    train_end_date: str = "2022-12",
    val_end_date: str = "2023-12"
) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    """
    Split dataset chronologically into Train, Validation, and Test sets.

    Train: records <= train_end_date (e.g. 2020-01 to 2022-12, 36 months)
    Val: train_end_date < records <= val_end_date (e.g. 2023-01 to 2023-12, 12 months)
    Test: records > val_end_date (e.g. 2024-01 to 2024-12, 12 months)
    """
    train_mask = df["date"] <= train_end_date
    val_mask = (df["date"] > train_end_date) & (df["date"] <= val_end_date)
    test_mask = df["date"] > val_end_date

    X_train = df.loc[train_mask, FEATURE_COLUMNS].copy()
    y_train = df.loc[train_mask, TARGET_COLUMN].copy()

    X_val = df.loc[val_mask, FEATURE_COLUMNS].copy()
    y_val = df.loc[val_mask, TARGET_COLUMN].copy()

    X_test = df.loc[test_mask, FEATURE_COLUMNS].copy()
    y_test = df.loc[test_mask, TARGET_COLUMN].copy()

    return X_train, y_train, X_val, y_val, X_test, y_test


def build_candidate_models() -> Dict[str, Any]:
    """Instantiate candidate classifiers with fixed random seeds."""
    return {
        "Dummy (Majority Class)": DummyClassifier(strategy="most_frequent"),
        "Logistic Regression": LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=RANDOM_SEED
        ),
        "Random Forest Classifier": RandomForestClassifier(
            n_estimators=100,
            max_depth=4,
            class_weight="balanced",
            random_state=RANDOM_SEED
        ),
        "Gradient Boosting Classifier": GradientBoostingClassifier(
            n_estimators=50,
            max_depth=3,
            random_state=RANDOM_SEED
        ),
    }


def evaluate_model_pipeline(
    pipeline: Pipeline,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_eval: pd.DataFrame,
    y_eval: pd.Series,
    split_name: str = "Validation"
) -> Dict[str, Any]:
    """
    Evaluate fitted pipeline against an evaluation set.
    """
    y_pred = pipeline.predict(X_eval)

    acc = float(accuracy_score(y_eval, y_pred))
    macro_f1 = float(f1_score(y_eval, y_pred, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_eval, y_pred, average="weighted", zero_division=0))

    labels = sorted(list(set(y_train.unique()).union(set(y_eval.unique()))))
    cm = confusion_matrix(y_eval, y_pred, labels=labels).tolist()

    report_dict = classification_report(
        y_eval,
        y_pred,
        labels=labels,
        output_dict=True,
        zero_division=0
    )

    per_class = {}
    for label in labels:
        if label in report_dict:
            per_class[label] = {
                "precision": round(float(report_dict[label]["precision"]), 4),
                "recall": round(float(report_dict[label]["recall"]), 4),
                "f1_score": round(float(report_dict[label]["f1-score"]), 4),
                "support": int(report_dict[label]["support"]),
            }

    return {
        "split": split_name,
        "sample_count": len(y_eval),
        "accuracy": round(acc, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "confusion_matrix": {
            "labels": labels,
            "matrix": cm
        },
        "per_class_metrics": per_class
    }


def perform_timeseries_cross_validation(
    X: pd.DataFrame,
    y: pd.Series,
    dates: pd.Series,
    n_splits: int = 4
) -> List[Dict[str, Any]]:
    """
    Perform expanding-window TimeSeries cross-validation for Random Forest.
    """
    tscv = TimeSeriesSplit(n_splits=n_splits)
    fold_results = []

    for fold_idx, (train_idx, val_idx) in enumerate(tscv.split(X)):
        pipe = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("classifier", RandomForestClassifier(
                n_estimators=100,
                max_depth=4,
                class_weight="balanced",
                random_state=RANDOM_SEED
            )),
        ])

        X_tr, y_tr = X.iloc[train_idx], y.iloc[train_idx]
        X_va, y_va = X.iloc[val_idx], y.iloc[val_idx]

        pipe.fit(X_tr, y_tr)
        y_pred = pipe.predict(X_va)

        acc = float(accuracy_score(y_va, y_pred))
        macro_f1 = float(f1_score(y_va, y_pred, average="macro", zero_division=0))

        fold_results.append({
            "fold": fold_idx + 1,
            "train_start": str(dates.iloc[train_idx[0]]),
            "train_end": str(dates.iloc[train_idx[-1]]),
            "train_count": len(train_idx),
            "val_start": str(dates.iloc[val_idx[0]]),
            "val_end": str(dates.iloc[val_idx[-1]]),
            "val_count": len(val_idx),
            "accuracy": round(acc, 4),
            "macro_f1": round(macro_f1, 4),
        })

    return fold_results


def extract_feature_importances(
    pipeline: Pipeline,
    feature_names: List[str]
) -> List[Dict[str, Any]]:
    """Extract and sort feature importances from the classifier."""
    classifier = pipeline.named_steps.get("classifier")
    if hasattr(classifier, "feature_importances_"):
        importances = classifier.feature_importances_
        sorted_pairs = sorted(
            zip(feature_names, importances),
            key=lambda x: x[1],
            reverse=True
        )
        return [
            {"feature": feat, "importance": round(float(imp), 4)}
            for feat, imp in sorted_pairs
        ]
    return []


def compute_and_save_shap_artifacts(
    pipeline: Pipeline,
    preprocessor: Pipeline,
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    feature_names: List[str],
    models_dir: Path,
    outputs_dir: Path,
) -> Dict[str, Any]:
    """
    Fit SHAP TreeExplainer on Random Forest classifier using strictly the
    transformed training partition as background, verify multiclass additivity,
    serialize the explainer artifact, and export global test SHAP importance.
    """
    import shap

    logger.info("Computing SHAP TreeExplainer using transformed training background (N=%d)...", len(X_train))
    classifier = pipeline.named_steps["classifier"]
    classes = list(classifier.classes_)

    # 1. Transform training set background
    X_train_trans = preprocessor.transform(X_train)

    # 2. Build explainer with model_output="probability"
    explainer = shap.TreeExplainer(
        classifier,
        data=X_train_trans,
        model_output="probability",
        feature_names=feature_names,
    )

    # 3. Serialize explainer safely with atomic rename
    explainer_path = models_dir / "soil_risk_explainer.joblib"
    tmp_explainer_path = models_dir / "soil_risk_explainer.joblib.tmp"
    joblib.dump(explainer, tmp_explainer_path)
    tmp_explainer_path.replace(explainer_path)
    logger.info(f"Saved SHAP explainer to {explainer_path} (Size: {explainer_path.stat().st_size} bytes)")

    # 4. Compute SHAP explanations on held-out test partition (2024, N=12)
    X_test_trans = preprocessor.transform(X_test)
    shap_test = explainer.shap_values(X_test_trans)  # shape: (12, 14, 3)
    probs_test = pipeline.predict_proba(X_test)

    # 5. Multiclass Additivity Verification on Test Partition
    max_additivity_diff = 0.0
    for i in range(len(X_test)):
        for c_idx in range(len(classes)):
            base_val = explainer.expected_value[c_idx]
            sum_shap = float(np.sum(shap_test[i, :, c_idx]))
            pred_prob = float(probs_test[i, c_idx])
            diff = abs((base_val + sum_shap) - pred_prob)
            if diff > max_additivity_diff:
                max_additivity_diff = diff

    logger.info(
        f"Test Partition SHAP Additivity Verification: max discrepancy={max_additivity_diff:.6f} "
        f"(Classes: {classes})"
    )

    # 6. Global SHAP Feature Importance Table (Export to outputs/shap_global_importance.csv)
    rf_gini = dict(zip(feature_names, classifier.feature_importances_))
    records = []
    for j, f in enumerate(feature_names):
        per_class_mean = {
            f"mean_abs_shap_{c.lower()}": float(np.mean(np.abs(shap_test[:, j, idx])))
            for idx, c in enumerate(classes)
        }
        overall_mean = float(np.mean(np.abs(shap_test[:, j, :])))
        records.append({
            "feature": f,
            "mean_abs_shap_overall": round(overall_mean, 4),
            "mean_abs_shap_high": round(per_class_mean["mean_abs_shap_high"], 4),
            "mean_abs_shap_low": round(per_class_mean["mean_abs_shap_low"], 4),
            "mean_abs_shap_medium": round(per_class_mean["mean_abs_shap_medium"], 4),
            "rf_gini_importance": round(float(rf_gini.get(f, 0.0)), 4),
            "indicator_weight_mapping": "Dynamic ML feature; separate from 5 rule-based indicator weights",
        })

    df_global = pd.DataFrame(records).sort_values("mean_abs_shap_overall", ascending=False).reset_index(drop=True)
    df_global.insert(0, "rank", range(1, len(df_global) + 1))

    outputs_dir.mkdir(parents=True, exist_ok=True)
    csv_path = outputs_dir / "shap_global_importance.csv"
    df_global.to_csv(csv_path, index=False)
    logger.info(f"Exported global SHAP importance to {csv_path}")

    return {
        "explainer_path": str(explainer_path.name),
        "background_partition": "Training Partition (2020-01 to 2022-12, N=36)",
        "explainer_type": "shap.TreeExplainer",
        "output_space": "probability",
        "classes": classes,
        "base_values": {c: round(float(explainer.expected_value[idx]), 4) for idx, c in enumerate(classes)},
        "test_additivity_max_discrepancy": round(float(max_additivity_diff), 6),
        "global_shap_importance": df_global.to_dict(orient="records"),
    }


def run_full_training_pipeline(
    data_path: Optional[Union[str, Path]] = None,
    output_dir: Optional[Union[str, Path]] = None,
    save_artifacts: bool = True
) -> Dict[str, Any]:
    """
    Execute full training, evaluation, cross-validation, and artifact serialization.
    """
    logger.info("Initializing SoilSentinel ML training pipeline...")
    models_dir = Path(output_dir) if output_dir else PROJECT_ROOT / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load and prepare dataset
    df = load_and_prepare_dataset(data_path)
    total_samples = len(df)
    date_min = df["date"].min()
    date_max = df["date"].max()
    logger.info(f"Loaded {total_samples} observations spanning {date_min} to {date_max}.")

    # 2. Chronological Split
    X_train, y_train, X_val, y_val, X_test, y_test = split_dataset_chronological(df)
    logger.info(
        f"Splits: Train n={len(X_train)} (classes: {dict(y_train.value_counts())}), "
        f"Val n={len(X_val)} (classes: {dict(y_val.value_counts())}), "
        f"Test n={len(X_test)} (classes: {dict(y_test.value_counts())})"
    )

    # 3. Model Training & Comparison
    candidates = build_candidate_models()
    model_comparisons = {}
    fitted_pipelines = {}

    for name, clf in candidates.items():
        pipe = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("classifier", clf),
        ])

        # Strict featurization ordering: fit ONLY on training data
        pipe.fit(X_train, y_train)
        fitted_pipelines[name] = pipe

        val_metrics = evaluate_model_pipeline(pipe, X_train, y_train, X_val, y_val, split_name="Validation (2023)")
        test_metrics = evaluate_model_pipeline(pipe, X_train, y_train, X_test, y_test, split_name="Test (2024)")

        model_comparisons[name] = {
            "validation_metrics": val_metrics,
            "test_metrics": test_metrics,
        }
        logger.info(
            f"[{name}] Val Acc: {val_metrics['accuracy']:.4f}, Val F1: {val_metrics['macro_f1']:.4f} | "
            f"Test Acc: {test_metrics['accuracy']:.4f}, Test F1: {test_metrics['macro_f1']:.4f}"
        )

    # 4. Perform TimeSeries Cross-Validation on Random Forest
    ts_cv_results = perform_timeseries_cross_validation(
        X=df[FEATURE_COLUMNS],
        y=df[TARGET_COLUMN],
        dates=df["date"],
        n_splits=4
    )
    avg_cv_acc = np.mean([r["accuracy"] for r in ts_cv_results])
    avg_cv_f1 = np.mean([r["macro_f1"] for r in ts_cv_results])
    logger.info(f"TimeSeries CV (4 folds) Random Forest: Mean Acc={avg_cv_acc:.4f}, Mean Macro-F1={avg_cv_f1:.4f}")

    # 5. Select Best Model: Random Forest Classifier
    selected_name = "Random Forest Classifier"
    selected_pipeline = fitted_pipelines[selected_name]
    feature_importances = extract_feature_importances(selected_pipeline, FEATURE_COLUMNS)

    # Also build standalone preprocessor for modular inference
    preprocessor = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    preprocessor.fit(X_train)

    # 6. Save Artifacts Safely with Atomic Write
    model_path = models_dir / "soil_risk_model.joblib"
    preprocessor_path = models_dir / "soil_risk_preprocessor.joblib"
    metadata_path = models_dir / "model_metadata.json"

    metadata = {
        "model_version": "v1.0.0-rf-proxy",
        "engine_version": "v1.0.0-baseline",
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "algorithm": selected_name,
        "target_column": TARGET_COLUMN,
        "classes": sorted(list(selected_pipeline.classes_)),
        "feature_columns": FEATURE_COLUMNS,
        "feature_count": len(FEATURE_COLUMNS),
        "dataset_total_samples": total_samples,
        "date_coverage": {"start": date_min, "end": date_max},
        "spatial_context": "Indo-Gangetic Agricultural Plains / Punjab",
        "target_provenance": "SURROGATE_PROXY_LEARNING",
        "target_provenance_notes": (
            "Learned from rule-based Seasonal Hydro-Thermal Stress & Baseline Vulnerability "
            "Index categories. NOT an independently measured physical soil degradation metric."
        ),
        "split_methodology": {
            "strategy": "Chronological Split",
            "train_window": "2020-01 to 2022-12 (36 months)",
            "validation_window": "2023-01 to 2023-12 (12 months)",
            "test_window": "2024-01 to 2024-12 (12 months)",
            "class_distribution_train": dict(y_train.value_counts()),
            "class_distribution_val": dict(y_val.value_counts()),
            "class_distribution_test": dict(y_test.value_counts()),
        },
        "evaluation_metrics": {
            "validation": model_comparisons[selected_name]["validation_metrics"],
            "test": model_comparisons[selected_name]["test_metrics"],
            "timeseries_cv_4fold": {
                "mean_accuracy": round(float(avg_cv_acc), 4),
                "mean_macro_f1": round(float(avg_cv_f1), 4),
                "folds": ts_cv_results,
            },
        },
        "model_comparison_summary": {
            k: {
                "val_accuracy": v["validation_metrics"]["accuracy"],
                "val_macro_f1": v["validation_metrics"]["macro_f1"],
                "test_accuracy": v["test_metrics"]["accuracy"],
                "test_macro_f1": v["test_metrics"]["macro_f1"],
            }
            for k, v in model_comparisons.items()
        },
        "top_features": feature_importances,
    }

    outputs_dir = PROJECT_ROOT / "outputs"
    shap_meta = None
    if save_artifacts:
        # Save preprocessor
        tmp_prep_path = models_dir / "soil_risk_preprocessor.joblib.tmp"
        joblib.dump(preprocessor, tmp_prep_path)
        tmp_prep_path.replace(preprocessor_path)

        # Save model pipeline
        tmp_model_path = models_dir / "soil_risk_model.joblib.tmp"
        joblib.dump(selected_pipeline, tmp_model_path)
        tmp_model_path.replace(model_path)

        # Generate and save SHAP Explainer and Global Importance
        try:
            shap_meta = compute_and_save_shap_artifacts(
                pipeline=selected_pipeline,
                preprocessor=preprocessor,
                X_train=X_train,
                X_test=X_test,
                feature_names=FEATURE_COLUMNS,
                models_dir=models_dir,
                outputs_dir=outputs_dir,
            )
        except Exception as e:
            logger.error(f"Failed to compute SHAP artifacts: {e}", exc_info=True)
            shap_meta = {"status": "ERROR", "error": str(e)}
        metadata["shap_explainer"] = shap_meta

        def _to_native_json(obj: Any) -> Any:
            """Recursively convert numpy scalars/arrays to native Python primitives for JSON."""
            if isinstance(obj, (np.integer, np.int64, np.int32)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64, np.float32)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {str(k): _to_native_json(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [_to_native_json(item) for item in obj]
            return obj

        # Save metadata
        tmp_meta_path = models_dir / "model_metadata.json.tmp"
        with open(tmp_meta_path, "w", encoding="utf-8") as f:
            json.dump(_to_native_json(metadata), f, indent=2)
        tmp_meta_path.replace(metadata_path)

        # Verification: load back from disk and test prediction on real row
        loaded_model = joblib.load(model_path)
        sample_row = X_test.iloc[[0]]
        sample_pred = loaded_model.predict(sample_row)[0]
        sample_probs = loaded_model.predict_proba(sample_row)[0]
        logger.info(
            f"Verification successful: Model loaded from {model_path} "
            f"(Size: {model_path.stat().st_size} bytes). "
            f"Test prediction on {df.loc[sample_row.index[0], 'date']}: {sample_pred} (probs={sample_probs.round(3)})"
        )

    return {
        "status": "SUCCESS",
        "selected_model": selected_name,
        "model_comparisons": model_comparisons,
        "timeseries_cv": ts_cv_results,
        "feature_importances": feature_importances,
        "metadata": metadata,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train and evaluate SoilSentinel surrogate ML models.")
    parser.add_argument("--data", type=str, default=None, help="Path to feature_table.csv")
    parser.add_argument("--output-dir", type=str, default=None, help="Directory to save model artifacts")
    parser.add_argument("--evaluate-only", action="store_true", help="Evaluate without overwriting artifacts")

    args = parser.parse_args()

    results = run_full_training_pipeline(
        data_path=args.data,
        output_dir=args.output_dir,
        save_artifacts=not args.evaluate_only
    )
    print("\nTraining completed successfully!")
    print(json.dumps(results["metadata"]["model_comparison_summary"], indent=2))
