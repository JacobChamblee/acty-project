import numpy as np
from typing import Dict, List
from sqlalchemy.orm import Session
from models import Trip, Vehicle

def analyze_trends(db: Session, vehicle_id: str, current_features: Dict) -> Dict:
    trips = db.query(Trip).filter(
        Trip.vehicle_id == vehicle_id
    ).order_by(Trip.uploaded_at).all()

    if len(trips) < 3:
        return {
            'status': 'insufficient_data',
            'trip_count': len(trips),
            'message': 'Need at least 3 trips for trend analysis'
        }

    ltft_values = []
    maf_per_rpm_values = []

    for trip in trips:
        features = trip.features
        if features and isinstance(features, dict):
            if 'ltft_drift' in features:
                ltft_values.append(features['ltft_drift'])
            if 'maf_per_rpm' in features:
                maf_per_rpm_values.append(features['maf_per_rpm'])

    trends = {}

    if len(ltft_values) >= 3:
        x = np.arange(len(ltft_values))
        slope, _ = np.polyfit(x, ltft_values, 1)
        trends['ltft_drift_slope'] = float(slope)
        trends['ltft_direction'] = 'increasing' if slope > 0.005 else 'decreasing' if slope < -0.005 else 'stable'
    else:
        trends['ltft_drift_slope'] = 0.0
        trends['ltft_direction'] = 'unknown'

    if len(maf_per_rpm_values) >= 3:
        x = np.arange(len(maf_per_rpm_values))
        slope, _ = np.polyfit(x, maf_per_rpm_values, 1)
        trends['maf_per_rpm_slope'] = float(slope)
        trends['maf_direction'] = 'increasing' if slope > 0.0001 else 'decreasing' if slope < -0.0001 else 'stable'
    else:
        trends['maf_per_rpm_slope'] = 0.0
        trends['maf_direction'] = 'unknown'

    vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == vehicle_id).first()
    if vehicle:
        vehicle.trend_history = trends
        db.commit()

    return {
        'status': 'success',
        'trip_count': len(trips),
        'trends': trends
    }
