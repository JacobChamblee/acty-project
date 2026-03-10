import pandas as pd
import numpy as np
from typing import Dict, Tuple

KNOWN_RANGES = {
    'RPM': (0, 8000),
    'SPEED': (0, 255),
    'THROTTLE_POS': (0, 100),
    'THROTTLE': (0, 100),
    'ENGINE_LOAD': (0, 100),
    'COOLANT_TEMP': (-40, 215),
    'MAF': (0, 655),
    'O2_VOLTAGE': (0, 1.275),
    'LTFT': (-100, 100),
    'STFT': (-100, 100),
    'KNOCK_RETARD': (0, 64),
}

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [col.upper().replace(' ', '_') for col in df.columns]
    return df

def normalize_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    if 'TIMESTAMP' in df.columns:
        df['TIMESTAMP'] = pd.to_datetime(df['TIMESTAMP'], errors='coerce')
        df['TIME_ELAPSED'] = (df['TIMESTAMP'] - df['TIMESTAMP'].iloc[0]).dt.total_seconds()
    return df

def validate_cadence(df: pd.DataFrame) -> Dict:
    if 'TIME_ELAPSED' in df.columns:
        time_diff = df['TIME_ELAPSED'].diff().dropna()
        median_diff = time_diff.median()
        expected_diff = 0.1
        deviation_pct = abs(median_diff - expected_diff) / expected_diff * 100

        return {
            'valid': deviation_pct <= 25,
            'median_interval': median_diff,
            'expected_interval': expected_diff,
            'deviation_pct': deviation_pct
        }
    return {'valid': True, 'warning': 'No timestamp column found'}

def normalize_values(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    normalized_df = df.copy()
    normalization_info = {}

    for col in df.columns:
        if col in ['TIMESTAMP', 'TIME_ELAPSED']:
            continue

        if pd.api.types.is_numeric_dtype(df[col]):
            col_key = col.upper()

            if col_key in KNOWN_RANGES:
                min_val, max_val = KNOWN_RANGES[col_key]
                normalization_info[col] = {'method': 'known_range', 'min': min_val, 'max': max_val}
            else:
                min_val = df[col].min()
                max_val = df[col].max()
                normalization_info[col] = {'method': 'observed_range', 'min': float(min_val), 'max': float(max_val)}

            if max_val > min_val:
                normalized_df[col] = (df[col] - min_val) / (max_val - min_val)
            else:
                normalized_df[col] = 0.0

    return normalized_df, normalization_info

def ingest_and_normalize(csv_path: str) -> Tuple[pd.DataFrame, Dict]:
    df = pd.read_csv(csv_path)

    df = normalize_columns(df)
    df = normalize_timestamps(df)

    cadence_check = validate_cadence(df)

    normalized_df, norm_info = normalize_values(df)

    metadata = {
        'row_count': len(df),
        'columns': list(df.columns),
        'cadence_validation': cadence_check,
        'normalization_info': norm_info
    }

    return normalized_df, metadata
