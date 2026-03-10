import pandas as pd
import numpy as np
from typing import Dict, List
from scipy import stats

def apply_median_filter(df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    filtered_df = df.copy()

    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]) and col not in ['TIMESTAMP', 'TIME_ELAPSED']:
            filtered_df[col] = df[col].rolling(window=window, center=True, min_periods=1).median()

    return filtered_df

def detect_outliers(df: pd.DataFrame, threshold: float = 3.5) -> Dict[str, List[int]]:
    outliers = {}

    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]) and col not in ['TIMESTAMP', 'TIME_ELAPSED']:
            z_scores = np.abs(stats.zscore(df[col].dropna()))
            outlier_indices = np.where(z_scores > threshold)[0].tolist()

            if outlier_indices:
                outliers[col] = outlier_indices

    return outliers

def derive_signals(df: pd.DataFrame) -> pd.DataFrame:
    derived_df = df.copy()

    if 'TIME_ELAPSED' in df.columns:
        time_diff = df['TIME_ELAPSED'].diff()

        if 'RPM' in df.columns:
            rpm_diff = df['RPM'].diff()
            derived_df['RPM_RATE'] = rpm_diff / time_diff

        if 'COOLANT_TEMP' in df.columns:
            coolant_diff = df['COOLANT_TEMP'].diff()
            derived_df['COOLANT_RISE_RATE'] = coolant_diff / time_diff

        if 'THROTTLE_POS' in df.columns or 'THROTTLE' in df.columns:
            throttle_col = 'THROTTLE_POS' if 'THROTTLE_POS' in df.columns else 'THROTTLE'
            throttle_diff = df[throttle_col].diff()
            derived_df['THROTTLE_TRANSIENT_RATE'] = throttle_diff / time_diff

        if 'KNOCK_RETARD' in df.columns:
            knock_events = (df['KNOCK_RETARD'] > 0).astype(int)
            derived_df['KNOCK_FREQUENCY'] = knock_events.rolling(window=100, min_periods=1).sum()

    return derived_df

def process_signals(df: pd.DataFrame) -> tuple[pd.DataFrame, Dict]:
    filtered_df = apply_median_filter(df)

    outliers = detect_outliers(filtered_df)

    processed_df = derive_signals(filtered_df)

    metadata = {
        'outliers': outliers,
        'outlier_count': sum(len(indices) for indices in outliers.values()),
        'derived_signals': ['RPM_RATE', 'COOLANT_RISE_RATE', 'THROTTLE_TRANSIENT_RATE', 'KNOCK_FREQUENCY']
    }

    return processed_df, metadata
