import pandas as pd
from typing import Dict, List

def apply_diagnostic_rules(df: pd.DataFrame, features: Dict) -> List[Dict]:
    events = []

    if 'KNOCK_RETARD' in df.columns and 'ENGINE_LOAD' in df.columns:
        knock_samples = df[(df['KNOCK_RETARD'] > 0.047) & (df['ENGINE_LOAD'] < 0.6)]
        if len(knock_samples) > 0:
            events.append({
                'type': 'reduced_knock_margin',
                'severity': 'medium',
                'confidence': min(95, 70 + len(knock_samples) / len(df) * 100),
                'evidence': f'Detected {len(knock_samples)} knock retard events (>3°) at moderate load (<60%)'
            })

    ltft_drift = features.get('ltft_drift', 0)
    if abs(ltft_drift) > 0.07:
        events.append({
            'type': 'injector_fouling_suspected',
            'severity': 'medium',
            'confidence': min(95, 60 + abs(ltft_drift) * 200),
            'evidence': f'Long-term fuel trim drift of {ltft_drift*100:.1f}% exceeds normal range (±7%)'
        })

    if 'COOLANT_RISE_RATE' in df.columns and 'ENGINE_LOAD' in df.columns:
        rapid_heating = df[(df['COOLANT_RISE_RATE'] > 0.02) & (df['ENGINE_LOAD'] > 0.7)]
        if len(rapid_heating) > 5:
            events.append({
                'type': 'cooling_system_stress',
                'severity': 'high',
                'confidence': min(95, 75 + len(rapid_heating) / 10),
                'evidence': f'Coolant rise rate >2°C/s under high load detected {len(rapid_heating)} times'
            })

    maf_per_rpm = features.get('maf_per_rpm', 0)
    avg_rpm = features.get('avg_rpm', 0)
    if maf_per_rpm < 0.003 and avg_rpm > 0.25:
        events.append({
            'type': 'maf_degradation',
            'severity': 'low',
            'confidence': 65,
            'evidence': f'MAF/RPM ratio ({maf_per_rpm:.5f}) below expected threshold at avg RPM {avg_rpm*8000:.0f}'
        })

    pct_time_wot = features.get('pct_time_wot', 0)
    if pct_time_wot > 15:
        events.append({
            'type': 'aggressive_driving_pattern',
            'severity': 'info',
            'confidence': 90,
            'evidence': f'{pct_time_wot:.1f}% of trip spent at wide-open throttle (>90%)'
        })

    time_above_100c = features.get('time_above_100c', 0)
    if time_above_100c > 60:
        events.append({
            'type': 'thermal_overexposure',
            'severity': 'medium',
            'confidence': 85,
            'evidence': f'Coolant temperature exceeded 100°C for {time_above_100c:.0f} seconds'
        })

    return events
