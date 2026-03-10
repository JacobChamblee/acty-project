import pandas as pd
import numpy as np
from typing import Dict

def compute_features(df: pd.DataFrame) -> Dict:
    features = {}

    throttle_col = 'THROTTLE_POS' if 'THROTTLE_POS' in df.columns else 'THROTTLE'
    if throttle_col in df.columns:
        wot_samples = (df[throttle_col] > 0.9).sum()
        features['pct_time_wot'] = (wot_samples / len(df)) * 100
    else:
        features['pct_time_wot'] = 0.0

    if 'RPM' in df.columns:
        features['avg_rpm'] = float(df['RPM'].mean())
        features['redline_events'] = int((df['RPM'] > 0.8125).sum())
    else:
        features['avg_rpm'] = 0.0
        features['redline_events'] = 0

    if 'LTFT' in df.columns:
        features['ltft_drift'] = float(df['LTFT'].mean())
    else:
        features['ltft_drift'] = 0.0

    if 'KNOCK_RETARD' in df.columns:
        knock_events = (df['KNOCK_RETARD'] > 0).sum()
        total_cycles = len(df) * features.get('avg_rpm', 0) / 60 / 10
        if total_cycles > 0:
            features['knock_events_per_1k_cycles'] = float((knock_events / total_cycles) * 1000)
        else:
            features['knock_events_per_1k_cycles'] = 0.0
    else:
        features['knock_events_per_1k_cycles'] = 0.0

    if 'MAF' in df.columns and 'RPM' in df.columns:
        rpm_nonzero = df[df['RPM'] > 0.01]
        if len(rpm_nonzero) > 0:
            features['maf_per_rpm'] = float((rpm_nonzero['MAF'] / rpm_nonzero['RPM']).mean())
        else:
            features['maf_per_rpm'] = 0.0
    else:
        features['maf_per_rpm'] = 0.0

    if 'COOLANT_TEMP' in df.columns:
        features['coolant_peak_temp'] = float(df['COOLANT_TEMP'].max())

        temp_above_threshold = df['COOLANT_TEMP'] > 0.465
        if 'TIME_ELAPSED' in df.columns and temp_above_threshold.any():
            time_diffs = df[temp_above_threshold]['TIME_ELAPSED'].diff()
            features['time_above_100c'] = float(time_diffs.sum()) if not time_diffs.empty else 0.0
        else:
            features['time_above_100c'] = 0.0
    else:
        features['coolant_peak_temp'] = 0.0
        features['time_above_100c'] = 0.0

    return features
