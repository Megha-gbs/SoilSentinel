"""
SoilSentinel Global ML Training Pipeline
Phase: Global Multi-Continental Expansion (v3.0.0-global)
Evaluates generalization across geographically held-out continents and provides uncertainty estimation.
Preserves all existing baseline and regional models.
"""

import os
import json
import joblib
import pandas as pd
import numpy as np
from sklearn.model_selection import LeaveOneGroupOut, KFold
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.dummy import DummyRegressor, DummyClassifier
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.ensemble import (
    RandomForestRegressor, 
    GradientBoostingRegressor, 
    RandomForestClassifier,
    IsolationForest
)
from sklearn.metrics import (
    r2_score, 
    mean_absolute_error, 
    mean_squared_error,
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    classification_report
)

BASE_DIR = os.path.abspath(r"C:\Users\mohitkumar\Documents\Datathon")
DATA_PROCESSED = os.path.join(BASE_DIR, "data", "processed")
MODELS_DIR = os.path.join(BASE_DIR, "models", "v3_global")
os.makedirs(MODELS_DIR, exist_ok=True)

# ==============================================================================
# WORKSTREAM 1: GLOBAL LABORATORY-MEASURED SOIL ORGANIC CARBON REGRESSOR
# ==============================================================================
def train_and_evaluate_global_soc_model():
    print("=" * 80)
    print("WORKSTREAM 1: GLOBAL LABORATORY-MEASURED SOIL ORGANIC CARBON REGRESSOR")
    print("Ground Truth: ISRIC WoSIS Multi-Continental Analytical Profiles")
    print("=" * 80)
    
    csv_path = os.path.join(DATA_PROCESSED, "global_multicontinental_wosis_profiles.csv")
    df = pd.read_csv(csv_path)
    
    feature_cols = ['ph_h2o', 'clay_fraction', 'sand_fraction', 'silt_fraction']
    target_col = 'organic_carbon_g_kg'
    group_col = 'continent'
    
    X = df[feature_cols].copy()
    y = df[target_col].copy()
    groups = df[group_col].values
    
    print(f"Dataset Shape: {X.shape}, Target: {target_col}")
    print(f"Continents: {np.unique(groups)}")
    print(f"Target stats: Mean={y.mean():.2f}, Median={y.median():.2f}, Std={y.std():.2f}, Min={y.min():.2f}, Max={y.max():.2f}")
    
    # 1. Continent-Held-Out Evaluation (Leave-One-Continent-Out)
    logo = LeaveOneGroupOut()
    
    models = {
        "Dummy (Mean)": DummyRegressor(strategy='mean'),
        "Ridge Linear": Ridge(alpha=1.0),
        "Random Forest": RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42),
        "Gradient Boosting": GradientBoostingRegressor(n_estimators=100, max_depth=3, learning_rate=0.08, subsample=0.85, random_state=42)
    }
    
    continent_results = {}
    for name, model in models.items():
        continent_results[name] = {"r2_per_continent": {}, "mae_per_continent": {}, "rmse_per_continent": {}}
        y_true_all = []
        y_pred_all = []
        
        for train_idx, test_idx in logo.split(X, y, groups=groups):
            cont_name = groups[test_idx[0]]
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            
            # Preprocessor fit strictly on training continents
            preprocessor = Pipeline([
                ('imputer', SimpleImputer(strategy='median')),
                ('scaler', StandardScaler())
            ])
            X_train_s = preprocessor.fit_transform(X_train)
            X_test_s = preprocessor.transform(X_test)
            
            model.fit(X_train_s, y_train)
            preds = model.predict(X_test_s)
            
            r2 = r2_score(y_test, preds)
            mae = mean_absolute_error(y_test, preds)
            rmse = np.sqrt(mean_squared_error(y_test, preds))
            
            continent_results[name]["r2_per_continent"][cont_name] = round(float(r2), 4)
            continent_results[name]["mae_per_continent"][cont_name] = round(float(mae), 4)
            continent_results[name]["rmse_per_continent"][cont_name] = round(float(rmse), 4)
            
            y_true_all.extend(y_test)
            y_pred_all.extend(preds)
            
        overall_r2 = r2_score(y_true_all, y_pred_all)
        overall_mae = mean_absolute_error(y_true_all, y_pred_all)
        overall_rmse = np.sqrt(mean_squared_error(y_true_all, y_pred_all))
        
        continent_results[name]["overall_r2"] = round(float(overall_r2), 4)
        continent_results[name]["overall_mae"] = round(float(overall_mae), 4)
        continent_results[name]["overall_rmse"] = round(float(overall_rmse), 4)
        
        print(f"\nModel: {name}")
        print(f"Overall Cross-Continental R2: {overall_r2:.4f}, MAE: {overall_mae:.4f} g/kg, RMSE: {overall_rmse:.4f} g/kg")
        for c in continent_results[name]["r2_per_continent"]:
            c_r2 = continent_results[name]["r2_per_continent"][c]
            c_mae = continent_results[name]["mae_per_continent"][c]
            print(f"  - {c:18s}: R2 = {c_r2:7.4f}, MAE = {c_mae:.4f} g/kg")

    # Fit final global model on entire multi-continental dataset
    final_preprocessor = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])
    X_s = final_preprocessor.fit_transform(X)
    best_soc_model = GradientBoostingRegressor(n_estimators=100, max_depth=3, learning_rate=0.08, subsample=0.85, random_state=42)
    best_soc_model.fit(X_s, y)
    
    # Save artifacts
    soc_model_path = os.path.join(MODELS_DIR, "global_soc_regressor.joblib")
    soc_preprocessor_path = os.path.join(MODELS_DIR, "global_soc_preprocessor.joblib")
    soc_meta_path = os.path.join(MODELS_DIR, "global_soc_metadata.json")
    
    joblib.dump(best_soc_model, soc_model_path)
    joblib.dump(final_preprocessor, soc_preprocessor_path)
    
    metadata = {
        "model_version": "3.0.0-global-gbr-soc",
        "description": "Global Laboratory-Measured Soil Organic Carbon Regressor",
        "features": feature_cols,
        "target": target_col,
        "target_units": "g C / kg (grams Carbon per kilogram dry soil)",
        "continents_included": list(np.unique(groups)),
        "sample_size": len(df),
        "evaluation_strategy": "Leave-One-Continent-Out Cross-Validation (6 Folds)",
        "results": continent_results
    }
    with open(soc_meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
        
    print(f"\nSaved Global SOC Regressor artifacts to {MODELS_DIR}")
    return continent_results


# ==============================================================================
# WORKSTREAM 2: GLOBAL ENVIRONMENTAL DEGRADATION RISK SURROGATE
# ==============================================================================
def train_and_evaluate_global_risk_surrogate():
    print("\n" + "=" * 80)
    print("WORKSTREAM 2: GLOBAL ENVIRONMENTAL DEGRADATION RISK SURROGATE MODEL")
    print("Proxy Task: Multi-Factor Agro-Climatic Degradation Risk Approximation")
    print("=" * 80)
    
    csv_path = os.path.join(DATA_PROCESSED, "global_agroclimatic_multiregion_features.csv")
    df = pd.read_csv(csv_path)
    
    feature_cols = ['ndvi', 'ndwi', 'msi', 'temperature', 'precipitation', 'humidity', 'organic_matter', 'ph', 'clay_content']
    target_col = 'risk_class'
    group_col = 'region_id'
    
    X = df[feature_cols].copy()
    y = df[target_col].copy()
    groups = df[group_col].values
    
    print(f"Dataset Shape: {X.shape}, Target Distribution:")
    print(df['risk_label'].value_counts())
    
    # 1. Continent / Region-Held-Out Evaluation
    logo = LeaveOneGroupOut()
    
    models = {
        "Majority Baseline": DummyClassifier(strategy='most_frequent'),
        "Balanced Random Forest": RandomForestClassifier(n_estimators=100, max_depth=8, class_weight='balanced', random_state=42),
        "Logistic Regression": LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42)
    }
    
    region_results = {}
    for name, model in models.items():
        region_results[name] = {"acc_per_region": {}, "bal_acc_per_region": {}}
        y_true_all = []
        y_pred_all = []
        
        for train_idx, test_idx in logo.split(X, y, groups=groups):
            reg_name = groups[test_idx[0]]
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            
            preprocessor = Pipeline([
                ('imputer', SimpleImputer(strategy='median')),
                ('scaler', StandardScaler())
            ])
            X_train_s = preprocessor.fit_transform(X_train)
            X_test_s = preprocessor.transform(X_test)
            
            model.fit(X_train_s, y_train)
            preds = model.predict(X_test_s)
            
            acc = accuracy_score(y_test, preds)
            unique_test_classes = np.unique(y_test)
            if len(unique_test_classes) > 1:
                bal_acc = balanced_accuracy_score(y_test, preds)
            else:
                bal_acc = acc
                
            region_results[name]["acc_per_region"][reg_name] = round(float(acc), 4)
            region_results[name]["bal_acc_per_region"][reg_name] = round(float(bal_acc), 4)
            
            y_true_all.extend(y_test)
            y_pred_all.extend(preds)
            
        overall_acc = accuracy_score(y_true_all, y_pred_all)
        overall_bal_acc = balanced_accuracy_score(y_true_all, y_pred_all)
        overall_f1 = f1_score(y_true_all, y_pred_all, average='macro')
        
        region_results[name]["overall_accuracy"] = round(float(overall_acc), 4)
        region_results[name]["overall_balanced_accuracy"] = round(float(overall_bal_acc), 4)
        region_results[name]["overall_macro_f1"] = round(float(overall_f1), 4)
        
        print(f"\nModel: {name}")
        print(f"Overall Accuracy: {overall_acc:.4f}, Balanced Accuracy: {overall_bal_acc:.4f}, Macro F1: {overall_f1:.4f}")
        for r in region_results[name]["acc_per_region"]:
            r_acc = region_results[name]["acc_per_region"][r]
            print(f"  - {r:26s}: Accuracy = {r_acc:.4f}")

    # Fit final global risk model
    final_preprocessor = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])
    X_s = final_preprocessor.fit_transform(X)
    best_risk_model = RandomForestClassifier(n_estimators=100, max_depth=8, class_weight='balanced', random_state=42)
    best_risk_model.fit(X_s, y)
    
    # Save artifacts
    risk_model_path = os.path.join(MODELS_DIR, "global_risk_surrogate.joblib")
    risk_preprocessor_path = os.path.join(MODELS_DIR, "global_risk_preprocessor.joblib")
    risk_meta_path = os.path.join(MODELS_DIR, "global_risk_metadata.json")
    
    joblib.dump(best_risk_model, risk_model_path)
    joblib.dump(final_preprocessor, risk_preprocessor_path)
    
    metadata = {
        "model_version": "3.0.0-global-rf-surrogate",
        "description": "Global Environmental Degradation Risk Surrogate Model",
        "features": feature_cols,
        "target": target_col,
        "target_nature": "Heuristic Surrogate approximating domain-expert multi-factor risk index across global biomes",
        "regions_included": list(np.unique(groups)),
        "sample_size": len(df),
        "evaluation_strategy": "Leave-One-Region-Out Cross-Validation (6 Continental Regions)",
        "results": region_results
    }
    with open(risk_meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
        
    print(f"\nSaved Global Risk Surrogate artifacts to {MODELS_DIR}")
    return region_results


# ==============================================================================
# WORKSTREAM 3: EPISTEMIC UNCERTAINTY & DOMAIN APPLICABILITY DETECTOR
# ==============================================================================
def train_and_save_domain_applicability_detector():
    print("\n" + "=" * 80)
    print("WORKSTREAM 3: EPISTEMIC UNCERTAINTY & DOMAIN APPLICABILITY ENGINE")
    print("Guards against confident hallucination on out-of-domain locations")
    print("=" * 80)
    
    csv_path = os.path.join(DATA_PROCESSED, "global_agroclimatic_multiregion_features.csv")
    df = pd.read_csv(csv_path)
    feature_cols = ['ndvi', 'ndwi', 'msi', 'temperature', 'precipitation', 'humidity', 'organic_matter', 'ph', 'clay_content']
    X = df[feature_cols].copy()
    
    preprocessor = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])
    X_s = preprocessor.fit_transform(X)
    
    # Train Isolation Forest on empirical feature distribution
    iso_forest = IsolationForest(contamination=0.03, random_state=42)
    iso_forest.fit(X_s)
    
    # Store empirical bounds for rule-based boundary checks
    bounds = {}
    for col in feature_cols:
        bounds[col] = {
            "min": float(X[col].min()),
            "max": float(X[col].max()),
            "p01": float(np.percentile(X[col], 1)),
            "p99": float(np.percentile(X[col], 99)),
            "mean": float(X[col].mean()),
            "std": float(X[col].std())
        }
        
    detector_artifact = {
        "feature_cols": feature_cols,
        "preprocessor": preprocessor,
        "isolation_forest": iso_forest,
        "empirical_bounds": bounds
    }
    
    detector_path = os.path.join(MODELS_DIR, "global_domain_applicability_detector.joblib")
    joblib.dump(detector_artifact, detector_path)
    
    # Test evaluation on in-domain vs. extreme out-of-domain samples
    in_domain_sample = X.iloc[[0]].copy()
    out_domain_arctic = pd.DataFrame([{
        'ndvi': 0.02, 'ndwi': -0.8, 'msi': 3.5, 
        'temperature': -28.0, 'precipitation': 2.0, 'humidity': 25.0, 
        'organic_matter': 0.05, 'ph': 4.2, 'clay_content': 5.0
    }])
    out_domain_sahara = pd.DataFrame([{
        'ndvi': 0.01, 'ndwi': -0.9, 'msi': 4.0, 
        'temperature': 52.0, 'precipitation': 0.0, 'humidity': 8.0, 
        'organic_matter': 0.01, 'ph': 9.8, 'clay_content': 2.0
    }])
    
    def check_applicability(sample_df):
        s_scaled = preprocessor.transform(sample_df[feature_cols])
        score = iso_forest.decision_function(s_scaled)[0]
        is_in = bool(iso_forest.predict(s_scaled)[0] == 1)
        uncertainty = float(np.clip(1.0 - (score + 0.3) / 0.55, 0.0, 1.0))
        return {
            "is_in_domain": is_in,
            "anomaly_score": round(float(score), 4),
            "uncertainty": round(uncertainty, 4),
            "status": "In-Domain (Reliable Evidence)" if is_in else "Out-of-Domain (High Uncertainty - Lacks Evidence)"
        }
        
    res_in = check_applicability(in_domain_sample)
    res_arctic = check_applicability(out_domain_arctic)
    res_sahara = check_applicability(out_domain_sahara)
    
    print("\nApplicability Verification:")
    print(" 1. In-Domain Agricultural Sample (Iowa Summer):", res_in)
    print(" 2. Out-of-Domain Sample (Arctic Tundra Winter):", res_arctic)
    print(" 3. Out-of-Domain Sample (Hyper-Arid Sahara):", res_sahara)
    
    meta_path = os.path.join(MODELS_DIR, "global_applicability_metadata.json")
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump({
            "artifact": "global_domain_applicability_detector.joblib",
            "empirical_bounds": bounds,
            "verification_examples": {
                "in_domain": res_in,
                "arctic": res_arctic,
                "sahara": res_sahara
            }
        }, f, indent=2)
        
    print(f"\nSaved Domain Applicability Detector to {detector_path}")

if __name__ == "__main__":
    train_and_evaluate_global_soc_model()
    train_and_evaluate_global_risk_surrogate()
    train_and_save_domain_applicability_detector()
    print("\nALL GLOBAL ML PIPELINE TASKS COMPLETED SUCCESSFULLY.")
