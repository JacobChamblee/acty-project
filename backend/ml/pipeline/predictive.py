"""
predictive.py — Stage 3: Predictive Maintenance
XGBoost + Random Forest ensemble, per-vehicle models.
Consumes normalized OBD DataFrame + anomaly results,
predicts maintenance needs and component health scores.
"""

import json
import os
import pickle
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── config ────────────────────────────────────────────────────────────────────
MODEL_DIR = Path(os.environ.get("ACTY_MODEL_DIR", Path.home() / "acty" / "models"))
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# ── Maintenance prediction targets ────────────────────────────────────────────
MAINTENANCE_TARGETS = {
    "oil_degradation": {
        "label":       "Oil Degradation",
        "pids":        ["ENGINE_OIL_TEMP", "RPM", "ENGINE_LOAD", "COOLANT_TEMP"],
        "warn_thresh": 0.65,
        "crit_thresh": 0.85,
    },
    "fuel_system_stress": {
        "label":       "Fuel System Stress",
        "pids":        ["SHORT_FUEL_TRIM_1", "LONG_FUEL_TRIM_1", "MAF", "RPM"],
        "warn_thresh": 0.60,
        "crit_thresh": 0.80,
    },
    "cooling_system_stress": {
        "label":       "Cooling System Stress",
        "pids":        ["COOLANT_TEMP", "ENGINE_LOAD", "RPM", "INTAKE_TEMP"],
        "warn_thresh": 0.65,
        "crit_thresh": 0.82,
    },
    "ignition_health": {
        "label":       "Ignition Health",
        "pids":        ["TIMING_ADVANCE", "RPM", "ENGINE_LOAD", "SHORT_FUEL_TRIM_1"],
        "warn_thresh": 0.60,
        "crit_thresh": 0.78,
    },
    "battery_alternator": {
        "label":       "Battery / Alternator",
        "pids":        ["CONTROL_VOLTAGE", "RPM", "ENGINE_LOAD"],
        "warn_thresh": 0.55,
        "crit_thresh": 0.75,
    },
}

# ── result dataclass ──────────────────────────────────────────────────────────
@dataclass
class MaintenancePrediction:
    target:        str
    label:         str
    health_score:  float        # 0.0 (critical) → 1.0 (healthy)
    stress_score:  float        # 0.0 (no stress) → 1.0 (max stress)
    severity:      str          # "normal" | "warning" | "critical"
    confidence:    float
    contributing_pids: list[str] = field(default_factory=list)
    recommendation:    str = ""


# ── feature engineering ───────────────────────────────────────────────────────
def engineer_features(df: pd.DataFrame, pids: list[str]) -> Optional[pd.DataFrame]:
    """
    Build statistical features from a session's PID time series.
    Returns a single-row DataFrame of features.
    """
    available = [p for p in pids if p in df.columns and df[p].notna().sum() > 10]
    if not available:
        return None

    features = {}
    for pid in available:
        series = df[pid].dropna()
        features[f"{pid}_mean"]    = series.mean()
        features[f"{pid}_std"]     = series.std()
        features[f"{pid}_max"]     = series.max()
        features[f"{pid}_min"]     = series.min()
        features[f"{pid}_p95"]     = series.quantile(0.95)
        features[f"{pid}_p05"]     = series.quantile(0.05)
        features[f"{pid}_range"]   = series.max() - series.min()
        # Trend — slope of last 30 samples
        tail = series.tail(30)
        if len(tail) > 1:
            features[f"{pid}_trend"] = float(np.polyfit(range(len(tail)), tail.values, 1)[0])
        else:
            features[f"{pid}_trend"] = 0.0

    return pd.DataFrame([features])


def _rule_based_stress(df: pd.DataFrame, target: str) -> float:
    """
    Fast rule-based stress score when ML models aren't available.
    Returns 0.0 (healthy) → 1.0 (critical stress).
    """
    cfg  = MAINTENANCE_TARGETS[target]
    pids = cfg["pids"]
    scores = []

    if target == "oil_degradation":
        if "ENGINE_OIL_TEMP" in df.columns:
            mean_temp = df["ENGINE_OIL_TEMP"].dropna().mean()
            scores.append(min((mean_temp - 80) / 55, 1.0) if mean_temp > 80 else 0.0)
        if "ENGINE_LOAD" in df.columns:
            high_load_pct = (df["ENGINE_LOAD"].dropna() > 80).mean()
            scores.append(float(high_load_pct))

    elif target == "fuel_system_stress":
        for trim in ["SHORT_FUEL_TRIM_1", "LONG_FUEL_TRIM_1"]:
            if trim in df.columns:
                mean_trim = df[trim].dropna().abs().mean()
                scores.append(min(mean_trim / 15.0, 1.0))

    elif target == "cooling_system_stress":
        if "COOLANT_TEMP" in df.columns:
            mean_temp = df["COOLANT_TEMP"].dropna().mean()
            scores.append(min((mean_temp - 85) / 25, 1.0) if mean_temp > 85 else 0.0)

    elif target == "ignition_health":
        if "TIMING_ADVANCE" in df.columns:
            timing_std = df["TIMING_ADVANCE"].dropna().std()
            scores.append(min(timing_std / 10.0, 1.0))

    elif target == "battery_alternator":
        if "CONTROL_VOLTAGE" in df.columns:
            mean_v = df["CONTROL_VOLTAGE"].dropna().mean()
            if mean_v < 13.8:
                scores.append(min((13.8 - mean_v) / 2.3, 1.0))
            else:
                scores.append(0.0)

    return round(float(np.mean(scores)) if scores else 0.0, 4)


# ── per-vehicle model (XGBoost + Random Forest ensemble) ─────────────────────
def _get_model_path(vehicle_id: str, target: str) -> Path:
    return MODEL_DIR / f"{vehicle_id}_{target}.pkl"


def _train_or_load_model(
    vehicle_id: str,
    target: str,
    X: pd.DataFrame,
    y: np.ndarray,
):
    """
    Load existing per-vehicle model or train a new one.
    Uses XGBoost + Random Forest soft-vote ensemble.
    """
    try:
        from sklearn.ensemble import RandomForestRegressor, VotingRegressor
        from xgboost import XGBRegressor
    except ImportError:
        return None

    model_path = _get_model_path(vehicle_id, target)

    if model_path.exists() and len(X) < 20:
        # Not enough new data to retrain — load existing
        with open(model_path, "rb") as f:
            return pickle.load(f)

    if len(X) < 5:
        return None

    rf  = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
    xgb = XGBRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
        verbosity=0,
    )

    ensemble = VotingRegressor(estimators=[("rf", rf), ("xgb", xgb)])

    try:
        ensemble.fit(X, y)
        with open(model_path, "wb") as f:
            pickle.dump(ensemble, f)
        return ensemble
    except Exception as e:
        print(f"[predictive] Model training failed for {target}: {e}")
        return None


# ── main prediction function ──────────────────────────────────────────────────
def predict_maintenance(
    df: pd.DataFrame,
    vehicle_id: str = "default",
    anomaly_score: float = 0.0,
) -> list[MaintenancePrediction]:
    """
    Run predictive maintenance analysis for all targets.
    Falls back to rule-based scoring if ML unavailable.

    Args:
        df:            Normalized OBD DataFrame for the session
        vehicle_id:    Unique vehicle identifier for per-vehicle models
        anomaly_score: Combined anomaly score from anomaly.py (boosts stress scores)

    Returns:
        List of MaintenancePrediction for each target
    """
    predictions = []

    for target, cfg in MAINTENANCE_TARGETS.items():
        features = engineer_features(df, cfg["pids"])

        stress_score = None

        # Try ML model first
        if features is not None:
            try:
                model_path = _get_model_path(vehicle_id, target)
                if model_path.exists():
                    with open(model_path, "rb") as f:
                        model = pickle.load(f)
                    stress_score = float(np.clip(model.predict(features)[0], 0.0, 1.0))
            except Exception as e:
                print(f"[predictive] Model inference failed for {target}: {e}")

        # Fall back to rule-based
        if stress_score is None:
            stress_score = _rule_based_stress(df, target)

        # Boost stress score by anomaly signal (up to +15%)
        stress_score = float(np.clip(stress_score + anomaly_score * 0.15, 0.0, 1.0))

        health_score = round(1.0 - stress_score, 4)
        stress_score = round(stress_score, 4)

        # Severity classification
        if stress_score >= cfg["crit_thresh"]:
            severity = "critical"
        elif stress_score >= cfg["warn_thresh"]:
            severity = "warning"
        else:
            severity = "normal"

        # Identify top contributing PIDs
        contributing = []
        if features is not None:
            pid_means = {
                pid: abs(features[f"{pid}_mean"].values[0])
                for pid in cfg["pids"]
                if f"{pid}_mean" in features.columns
            }
            contributing = sorted(pid_means, key=pid_means.get, reverse=True)[:3]

        recommendation = _build_recommendation(target, severity, stress_score)

        predictions.append(MaintenancePrediction(
            target            = target,
            label             = cfg["label"],
            health_score      = health_score,
            stress_score      = stress_score,
            severity          = severity,
            confidence        = 0.7 if stress_score is not None else 0.4,
            contributing_pids = contributing,
            recommendation    = recommendation,
        ))

    return predictions


def _build_recommendation(target: str, severity: str, score: float) -> str:
    if severity == "normal":
        return "No action required. Continue monitoring."

    recommendations = {
        "oil_degradation": {
            "warning":  "Oil showing elevated thermal stress. Check oil level and condition. Consider oil change if approaching interval.",
            "critical": "Oil under severe thermal stress. Immediate oil change recommended. Check for coolant contamination.",
        },
        "fuel_system_stress": {
            "warning":  "Fuel trims outside normal range. Inspect air filter, check for vacuum leaks.",
            "critical": "Significant fuel delivery issue detected. Check O2 sensors, fuel injectors, and MAF sensor.",
        },
        "cooling_system_stress": {
            "warning":  "Cooling system running warm. Check coolant level and inspect for leaks.",
            "critical": "Cooling system under critical stress. Inspect thermostat, water pump, and radiator immediately.",
        },
        "ignition_health": {
            "warning":  "Timing variability detected. Inspect spark plugs and ignition coils.",
            "critical": "Ignition system degradation detected. Replace spark plugs and check coil packs.",
        },
        "battery_alternator": {
            "warning":  "Charging voltage below optimal. Test battery and alternator output.",
            "critical": "Charging system fault. Battery or alternator requires immediate inspection.",
        },
    }

    return recommendations.get(target, {}).get(severity, "Inspection recommended.")


# ── pipeline entry point ──────────────────────────────────────────────────────
def run_predictive_pipeline(
    df: pd.DataFrame,
    vehicle_id: str = "default",
    anomaly_score: float = 0.0,
) -> dict:
    """
    Main entry point called by Acty pipeline after anomaly detection.

    Returns:
        {
            "predictions":    list[dict],
            "overall_health": float,
            "needs_attention": list[str],
            "vehicle_id":     str,
            "timestamp":      str,
        }
    """
    predictions = predict_maintenance(df, vehicle_id, anomaly_score)

    overall_health = round(
        float(np.mean([p.health_score for p in predictions])), 4
    )

    needs_attention = [
        p.label for p in predictions
        if p.severity in ("warning", "critical")
    ]

    return {
        "predictions": [
            {
                "target":             p.target,
                "label":              p.label,
                "health_score":       p.health_score,
                "stress_score":       p.stress_score,
                "severity":           p.severity,
                "confidence":         p.confidence,
                "contributing_pids":  p.contributing_pids,
                "recommendation":     p.recommendation,
            }
            for p in predictions
        ],
        "overall_health":  overall_health,
        "needs_attention": needs_attention,
        "vehicle_id":      vehicle_id,
        "timestamp":       datetime.utcnow().isoformat(),
    }
