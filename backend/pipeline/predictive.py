import numpy as np
from typing import Dict, List
from sqlalchemy.orm import Session
from models import Trip

# XGBoost is optional — falls back to Random Forest if not installed
try:
    from xgboost import XGBRegressor
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler


# ── Feature vector ───────────────────────────────────────────────────────────

FEATURE_KEYS = [
    'pct_time_wot',
    'avg_rpm',
    'redline_events',
    'ltft_drift',
    'knock_events_per_1k_cycles',
    'maf_per_rpm',
    'coolant_peak_temp',
    'time_above_100c',
]


def _features_to_vector(features: Dict) -> np.ndarray:
    """Convert a features dict (from features.py) to a fixed-length numpy vector."""
    return np.array([features.get(k, 0.0) for k in FEATURE_KEYS], dtype=float)


def _build_training_data(trips: List) -> tuple:
    """
    Derive a simple supervised signal from trip history.

    X  — feature vector for trip N
    y  — "stress score" for trip N+1 (a proxy target we can compute without
         labelled failure data, using LTFT drift + knock + thermal exposure)

    As real failure labels accumulate these targets can be replaced with
    actual maintenance records.
    """
    X, y = [], []

    for i in range(len(trips) - 1):
        current  = trips[i].features
        next_trip = trips[i + 1].features

        if not current or not next_trip:
            continue

        x_vec = _features_to_vector(current)

        # Proxy stress target — weighted sum of degradation indicators
        stress = (
            abs(next_trip.get('ltft_drift', 0)) * 3.0
            + next_trip.get('knock_events_per_1k_cycles', 0) * 0.5
            + next_trip.get('time_above_100c', 0) / 120.0
            + next_trip.get('redline_events', 0) * 0.1
        )

        X.append(x_vec)
        y.append(stress)

    return np.array(X), np.array(y)


# ── Prediction helpers ────────────────────────────────────────────────────────

def _miles_until_service(stress_score: float, base_miles: int = 5000) -> int:
    """
    Convert a stress score into an estimated miles-to-service figure.
    Higher stress → fewer miles recommended before next check.
    """
    factor = max(0.2, 1.0 - stress_score * 0.4)
    return max(500, int(base_miles * factor))


def _severity_from_stress(stress: float) -> str:
    if stress > 1.5:
        return 'high'
    if stress > 0.75:
        return 'medium'
    return 'low'


# ── Public API ────────────────────────────────────────────────────────────────

def predict_maintenance(
    db: Session,
    vehicle_id: str,
    current_features: Dict,
) -> List[Dict]:
    """
    Train a model on this vehicle's trip history and predict upcoming
    maintenance needs based on the current trip's features.

    Returns a list of event dicts in the same format as rules.py / anomaly.py.
    """
    events = []

    trips = (
        db.query(Trip)
        .filter(Trip.vehicle_id == vehicle_id)
        .order_by(Trip.uploaded_at)
        .all()
    )

    if len(trips) < 5:
        return [{
            'type': 'predictive_maintenance_unavailable',
            'severity': 'info',
            'confidence': 100.0,
            'evidence': (
                f'Need at least 5 trips for predictive maintenance. '
                f'Currently have {len(trips)}.'
            ),
            'meta': {'trip_count': len(trips)}
        }]

    X, y = _build_training_data(trips)

    if len(X) < 4:
        return events

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # ── Train ────────────────────────────────────────────────────────────────
    if XGBOOST_AVAILABLE:
        model = XGBRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            random_state=42,
            verbosity=0,
        )
    else:
        model = RandomForestRegressor(
            n_estimators=100,
            max_depth=4,
            random_state=42,
        )

    model.fit(X_scaled, y)

    # ── Predict on current trip ──────────────────────────────────────────────
    current_vec  = _features_to_vector(current_features).reshape(1, -1)
    current_scaled = scaler.transform(current_vec)
    predicted_stress = float(model.predict(current_scaled)[0])
    predicted_stress = max(0.0, predicted_stress)  # clamp negatives

    # ── Feature importances ──────────────────────────────────────────────────
    importances = dict(zip(FEATURE_KEYS, model.feature_importances_))
    top_factors = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:3]
    top_factor_names = [k.replace('_', ' ') for k, _ in top_factors]

    # ── Generate events ──────────────────────────────────────────────────────
    if predicted_stress > 0.4:
        miles_est = _miles_until_service(predicted_stress)
        severity  = _severity_from_stress(predicted_stress)

        events.append({
            'type': 'predictive_maintenance_recommended',
            'severity': severity,
            'confidence': min(90, 55 + predicted_stress * 20),
            'evidence': (
                f'Model predicts elevated vehicle stress (score: {predicted_stress:.2f}). '
                f'Recommended service within ~{miles_est:,} miles. '
                f'Top contributing factors: {", ".join(top_factor_names)}.'
            ),
            'meta': {
                'method': 'xgboost' if XGBOOST_AVAILABLE else 'random_forest',
                'predicted_stress': round(predicted_stress, 3),
                'miles_until_service': miles_est,
                'top_factors': top_factor_names,
                'trip_count': len(trips),
            }
        })

    # ── Injector health ──────────────────────────────────────────────────────
    ltft_history = [
        t.features.get('ltft_drift', 0)
        for t in trips
        if t.features and 'ltft_drift' in t.features
    ]
    if len(ltft_history) >= 5:
        ltft_trend = np.polyfit(np.arange(len(ltft_history)), ltft_history, 1)[0]
        if ltft_trend > 0.003:
            miles_est = _miles_until_service(ltft_trend * 10, base_miles=3000)
            events.append({
                'type': 'injector_service_predicted',
                'severity': 'medium',
                'confidence': min(88, 60 + ltft_trend * 500),
                'evidence': (
                    f'LTFT has been drifting +{ltft_trend*100:.2f}% per trip over the last '
                    f'{len(ltft_history)} trips. Injector cleaning recommended within '
                    f'~{miles_est:,} miles.'
                ),
                'meta': {
                    'ltft_slope_per_trip': round(ltft_trend, 5),
                    'miles_until_service': miles_est,
                }
            })

    # ── MAF degradation trend ────────────────────────────────────────────────
    maf_history = [
        t.features.get('maf_per_rpm', 0)
        for t in trips
        if t.features and 'maf_per_rpm' in t.features
    ]
    if len(maf_history) >= 5:
        maf_trend = np.polyfit(np.arange(len(maf_history)), maf_history, 1)[0]
        if maf_trend < -0.0001:
            events.append({
                'type': 'maf_degradation_predicted',
                'severity': 'low',
                'confidence': 72.0,
                'evidence': (
                    f'MAF/RPM efficiency declining at {maf_trend:.5f} per trip. '
                    f'MAF sensor cleaning or replacement may be needed within 2,000–4,000 miles.'
                ),
                'meta': {
                    'maf_slope_per_trip': round(maf_trend, 6),
                }
            })

    return events