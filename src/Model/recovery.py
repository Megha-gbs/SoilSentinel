"""
Soil Sentinel - Historical Recovery Tracking & Longitudinal Stress Comparison Engine.

Provides evidence-based trajectory tracking and recovery analysis across multi-month
time series of the Seasonal Hydro-Thermal Stress & Baseline Vulnerability Index.

CRITICAL PRINCIPLES:
1. LONGITUDINAL EVIDENCE:
   Evaluates true sequential context across historical time steps rather than isolated
   single-month snapshots.
2. STANDARDIZED RECOVERY STATES:
   - RECOVERING: Significant decrease in hydro-thermal stress (>= 5.0 pt decline over 3 months).
   - ESCALATING_STRESS: Significant increase in stress (>= 5.0 pt increase over 3 months).
   - CHRONIC_HIGH_STRESS: Sustained high risk (>= 65.0) for 3 or more consecutive months.
   - STABLE_RESILIENT: Consistently low stress (< 35.0) throughout observation window.
   - SEASONAL_CYCLING: Fluctuating within expected seasonal ranges without secular degradation.
   - INSUFFICIENT_HISTORY: Less than 3 observed consecutive months to establish trend.
3. BENCHMARK COMPARISONS:
   Computes Month-over-Month (MoM), Year-over-Year (YoY), historical percentile, and distance
   from historical peak stress.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from src.Model.risk_scoring import (
    classify_risk_category,
    THRESHOLD_LOW_UPPER,
    THRESHOLD_MEDIUM_UPPER,
)


@dataclass
class RecoveryAssessment:
    """Structured assessment of historical recovery status and longitudinal trend."""
    evaluation_date: str
    current_score: Optional[float]
    current_category: str
    mom_delta: Optional[float]          # Score(t) - Score(t-1)
    yoy_delta: Optional[float]          # Score(t) - Score(t-12)
    historical_mean: Optional[float]
    historical_min: Optional[float]
    historical_max: Optional[float]
    historical_percentile: Optional[float]
    consecutive_months_in_category: int
    recovery_status: str               # "RECOVERING", "ESCALATING_STRESS", "CHRONIC_HIGH_STRESS", "STABLE_RESILIENT", "SEASONAL_CYCLING", "INSUFFICIENT_HISTORY"
    observation_count: int = 0
    trajectory_slope_3m: Optional[float] = None
    peak_stress_recovery_points: Optional[float] = None  # Historical max - Current score
    key_trajectory_driver: str = ""
    evidence_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_historical_recovery(
    df_scored: pd.DataFrame,
    target_date: Optional[str] = None,
    score_column: str = "score",
    date_column: str = "date"
) -> RecoveryAssessment:
    """
    Evaluate longitudinal recovery trajectory and historical benchmarks for a target date.

    Parameters:
        df_scored: DataFrame containing scored time series records (e.g. from predict_from_csv or score_feature_dataframe).
        target_date: Optional 'YYYY-MM' date string. If None, evaluates the latest record in df_scored.
        score_column: Name of score column ('score' or 'baseline_risk_score').
        date_column: Name of date column ('date' or 'input_date').

    Returns:
        Structured RecoveryAssessment.
    """
    if df_scored.empty:
        raise ValueError("Cannot evaluate recovery on an empty DataFrame.")

    # Harmonize score column name
    s_col = score_column
    if s_col not in df_scored.columns:
        if "baseline_risk_score" in df_scored.columns:
            s_col = "baseline_risk_score"
        elif "score" in df_scored.columns:
            s_col = "score"
        else:
            raise KeyError(f"Score column '{score_column}' not found in DataFrame columns: {list(df_scored.columns)}")

    d_col = date_column
    if d_col not in df_scored.columns:
        if "date" in df_scored.columns:
            d_col = "date"
        elif "input_date" in df_scored.columns:
            d_col = "input_date"
        else:
            raise KeyError(f"Date column '{date_column}' not found in DataFrame columns: {list(df_scored.columns)}")

    df = df_scored.copy()
    # Sort chronologically by date
    df[d_col] = df[d_col].astype(str)
    df = df.sort_values(by=d_col).reset_index(drop=True)

    # Locate target record index
    if target_date is not None:
        matches = df.index[df[d_col] == str(target_date)].tolist()
        if not matches:
            raise ValueError(f"Target date '{target_date}' not found in dataset dates ({df[d_col].min()} to {df[d_col].max()}).")
        idx = matches[0]
    else:
        idx = len(df) - 1

    curr_row = df.iloc[idx]
    eval_date = str(curr_row[d_col])
    
    # Safe score extraction
    raw_s = curr_row[s_col]
    if raw_s is None or (isinstance(raw_s, float) and np.isnan(raw_s)) or raw_s == "":
        curr_score = None
        curr_cat = "UNKNOWN"
    else:
        curr_score = round(float(raw_s), 2)
        curr_cat = classify_risk_category(curr_score)

    # 1. Historical Baseline Statistics (over all preceding + current valid scores)
    valid_history = df.loc[:idx, s_col].dropna()
    valid_history_floats = [float(v) for v in valid_history if v != "" and not (isinstance(v, float) and np.isnan(v))]

    if not valid_history_floats or curr_score is None:
        return RecoveryAssessment(
            evaluation_date=eval_date,
            current_score=curr_score,
            current_category=curr_cat,
            mom_delta=None,
            yoy_delta=None,
            historical_mean=None,
            historical_min=None,
            historical_max=None,
            historical_percentile=None,
            consecutive_months_in_category=1,
            recovery_status="INSUFFICIENT_HISTORY",
            observation_count=len(valid_history_floats),
            trajectory_slope_3m=None,
            peak_stress_recovery_points=None,
            key_trajectory_driver="Insufficient historical score records to evaluate trajectory.",
            evidence_summary=f"Record {eval_date} has null/unobserved score or no preceding history."
        )

    hist_mean = round(float(np.mean(valid_history_floats)), 2)
    hist_min = round(float(np.min(valid_history_floats)), 2)
    hist_max = round(float(np.max(valid_history_floats)), 2)
    hist_percentile = round(float((np.array(valid_history_floats) <= curr_score).mean() * 100.0), 1)
    peak_recovery = round(hist_max - curr_score, 2)

    # 2. Month-over-Month Delta
    mom_delta: Optional[float] = None
    if idx > 0:
        prev_s = df.iloc[idx - 1][s_col]
        if prev_s is not None and prev_s != "" and not (isinstance(prev_s, float) and np.isnan(prev_s)):
            mom_delta = round(curr_score - float(prev_s), 2)

    # 3. Year-over-Year Delta (t - 12)
    yoy_delta: Optional[float] = None
    if idx >= 12:
        yoy_s = df.iloc[idx - 12][s_col]
        if yoy_s is not None and yoy_s != "" and not (isinstance(yoy_s, float) and np.isnan(yoy_s)):
            yoy_delta = round(curr_score - float(yoy_s), 2)

    # 4. Consecutive Months in Same Category
    consecutive_count = 0
    for back_i in range(idx, -1, -1):
        s_val = df.iloc[back_i][s_col]
        if s_val is None or s_val == "" or (isinstance(s_val, float) and np.isnan(s_val)):
            break
        if classify_risk_category(float(s_val)) == curr_cat:
            consecutive_count += 1
        else:
            break

    # 5. 3-Month Trajectory Slope
    trajectory_slope_3m: Optional[float] = None
    if idx >= 2:
        # Fit linear slope over last 3 points (t-2, t-1, t)
        scores_3m = []
        for offset in [2, 1, 0]:
            v = df.iloc[idx - offset][s_col]
            if v is not None and v != "" and not (isinstance(v, float) and np.isnan(v)):
                scores_3m.append(float(v))
        if len(scores_3m) == 3:
            # Change per month over 2 intervals: (score[2] - score[0]) / 2.0
            trajectory_slope_3m = round((scores_3m[2] - scores_3m[0]) / 2.0, 2)

    # 6. Classify Recovery Status
    if idx < 2 or trajectory_slope_3m is None:
        status = "INSUFFICIENT_HISTORY"
        driver = "Initial boundary sequence with fewer than 3 consecutive observations."
    elif curr_cat == "High" and consecutive_count >= 3:
        status = "CHRONIC_HIGH_STRESS"
        driver = f"Persistently elevated hydro-thermal stress in High category for {consecutive_count} consecutive months."
    elif trajectory_slope_3m <= -2.5:
        status = "RECOVERING"
        driver = f"Easing environmental stress with sharp 3-month score reduction (slope: {trajectory_slope_3m:+.2f} pts/month)."
    elif trajectory_slope_3m >= 2.5:
        status = "ESCALATING_STRESS"
        driver = f"Intensifying environmental stress with positive 3-month score escalation (slope: {trajectory_slope_3m:+.2f} pts/month)."
    elif curr_cat == "Low" and consecutive_count >= 3:
        status = "STABLE_RESILIENT"
        driver = f"Consistently low stress buffered across {consecutive_count} consecutive months."
    else:
        status = "SEASONAL_CYCLING"
        driver = "Score fluctuations remain within typical seasonal cyclical bounds without secular drift."

    # 7. Synthesize Evidence Summary
    mom_str = f"{mom_delta:+.2f}" if mom_delta is not None else "N/A"
    yoy_str = f"{yoy_delta:+.2f}" if yoy_delta is not None else "N/A"
    summary = (
        f"Evaluation for {eval_date}: Score = {curr_score:.2f} ({curr_cat}). "
        f"Trajectory Status: {status}. MoM Delta: {mom_str} pts, YoY Delta: {yoy_str} pts. "
        f"Historical Percentile: {hist_percentile:.1f}% (Range: [{hist_min:.2f}, {hist_max:.2f}], Mean: {hist_mean:.2f}). "
        f"{driver}"
    )

    return RecoveryAssessment(
        evaluation_date=eval_date,
        current_score=curr_score,
        current_category=curr_cat,
        mom_delta=mom_delta,
        yoy_delta=yoy_delta,
        historical_mean=hist_mean,
        historical_min=hist_min,
        historical_max=hist_max,
        historical_percentile=hist_percentile,
        consecutive_months_in_category=consecutive_count,
        recovery_status=status,
        observation_count=len(valid_history_floats),
        trajectory_slope_3m=trajectory_slope_3m,
        peak_stress_recovery_points=peak_recovery,
        key_trajectory_driver=driver,
        evidence_summary=summary
    )
