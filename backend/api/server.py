#!/usr/bin/env python3
"""
server.py
---------
FastAPI backend for the Acty mobile prototype.
Reads OBD-II CSV files, runs lightweight anomaly detection,
persists results to PostgreSQL, and serves structured insights
to the Android app over local WiFi.
"""

import asyncio
import glob
import io
import json
import os
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import asyncpg
import numpy as np
import pandas as pd
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from ml.pipeline.report import generate_diagnostic_report

# ── config ────────────────────────────────────────────────────────────────────
CSV_DIR      = Path(os.environ.get("ACTY_CSV_DIR", str(Path.home())))
PORT         = 8765
HOST         = os.environ.get("ACTY_HOST", "0.0.0.0")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ── thresholds for rule-based anomaly flags ───────────────────────────────────
THRESHOLDS = {
    "COOLANT_TEMP":      {"warn": 100, "crit": 108,  "unit": "°C",  "label": "Coolant Temp"},
    "ENGINE_OIL_TEMP":   {"warn": 120, "crit": 135,  "unit": "°C",  "label": "Oil Temp"},
    "LONG_FUEL_TRIM_1":  {"warn": 8.0, "crit": 12.0, "unit": "%",   "label": "Long Fuel Trim B1", "abs": True},
    "SHORT_FUEL_TRIM_1": {"warn": 10,  "crit": 20,   "unit": "%",   "label": "Short Fuel Trim B1", "abs": True},
    "LONG_FUEL_TRIM_2":  {"warn": 8.0, "crit": 12.0, "unit": "%",   "label": "Long Fuel Trim B2", "abs": True},
    "INTAKE_TEMP":       {"warn": 50,  "crit": 65,   "unit": "°C",  "label": "Intake Air Temp"},
    "CONTROL_VOLTAGE":   {"warn": 13.8,"crit": 11.5, "unit": "V",   "label": "Battery Voltage", "low": True},
    "ENGINE_LOAD":       {"warn": 85,  "crit": 95,   "unit": "%",   "label": "Engine Load"},
    "RPM":               {"warn": 5000,"crit": 6000, "unit": "rpm", "label": "RPM"},
}

# ── database connection factory ─────────────────────────────────────────────────
_db_config = None

def get_db_config():
    """Get database configuration for creating connections."""
    global _db_config
    if _db_config is None:
        _db_config = {
            "host": DATABASE_URL.split("@")[1].split(":")[0] if "@" in DATABASE_URL else "localhost",
            "port": int(DATABASE_URL.split(":")[-1].split("/")[0]) if ":" in DATABASE_URL.split("@")[-1] else 5432,
            "user": DATABASE_URL.split("://")[1].split(":")[0] if "://" in DATABASE_URL else "",
            "password": DATABASE_URL.split(":")[2].split("@")[0] if len(DATABASE_URL.split(":")) > 2 else "",
            "database": DATABASE_URL.split("/")[-1] if "/" in DATABASE_URL else "",
        }
    return _db_config

async def get_db_connection():
    """Create a new database connection for each request."""
    config = get_db_config()
    return await asyncpg.connect(**config)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate BYOK key encryption key at startup — fail fast rather than 503 mid-request
    try:
        from llm.key_encryption import _load_master_key
        _load_master_key()
        print("[byok] CACTUS_KEY_ENCRYPTION_KEY validated")
    except (EnvironmentError, ValueError) as e:
        print(f"[byok] WARNING: {e} — BYOK key registration/decryption will fail")

    if DATABASE_URL:
        try:
            # Test connection during startup
            conn = await get_db_connection()
            await conn.close()
            print(f"[db] Connected to PostgreSQL")
        except Exception as e:
            print(f"[db] Could not connect to PostgreSQL: {e}")
    yield


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="Acty Mobile API", version="0.1.0", lifespan=lifespan)

# ── CORS Configuration ────────────────────────────────────────────────────────
# Production domains: acty-labs.com and subdomains
# Development: localhost and 192.168.68.138 (local network for mobile testing)
CORS_ORIGINS = [
    # Production domain and subdomains
    "https://acty-labs.com",
    "https://www.acty-labs.com",
    "https://api.acty-labs.com",
    "https://dashboard.acty-labs.com",
    
    # Staging domains (if used)
    "https://staging.acty-labs.com",
    "https://api.staging.acty-labs.com",
    
    # Development and testing
    "http://localhost:3000",      # Frontend dev server
    "http://localhost:8765",      # API dev server
    "http://localhost:5000",      # Alt frontend port
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8765",
    
    # Local network (for mobile app testing)
    "http://192.168.68.138:3000",
    "http://192.168.68.138:8765",
    "http://192.168.68.1:8765",   # Gateway IP fallback
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "X-User-Id", "X-Request-ID"],
)

# ── BYOK LLM routers ──────────────────────────────────────────────────────────
from api.routers.llm_config import router as llm_config_router
from api.routers.insights import router as insights_router

app.include_router(llm_config_router)
app.include_router(insights_router)

# ── helpers ───────────────────────────────────────────────────────────────────
def find_latest_csv() -> Optional[Path]:
    files = sorted(CSV_DIR.glob("acty_obd_*.csv"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None

def find_all_csvs() -> list[Path]:
    return sorted(CSV_DIR.glob("acty_obd_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)

def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.dropna(subset=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df

def detect_anomalies(df: pd.DataFrame) -> list[dict]:
    alerts = []

    for col, cfg in THRESHOLDS.items():
        if col not in df.columns:
            continue
        series = df[col].dropna()
        if series.empty:
            continue

        recent = series.tail(30)
        val    = recent.mean()
        peak   = recent.abs().max() if cfg.get("abs") else recent.max()

        if cfg.get("abs"):
            check_val = abs(val)
        elif cfg.get("low"):
            check_val = -val
            cfg = {**cfg, "warn": -cfg["warn"], "crit": -cfg["crit"]}
        else:
            check_val = val

        severity = None
        if cfg.get("low"):
            if val <= abs(cfg["crit"]):   severity = "critical"
            elif val <= abs(cfg["warn"]): severity = "warning"
        else:
            if cfg.get("abs"):
                if abs(val) >= cfg["crit"]:   severity = "critical"
                elif abs(val) >= cfg["warn"]: severity = "warning"
            else:
                if val >= cfg["crit"]:   severity = "critical"
                elif val >= cfg["warn"]: severity = "warning"

        if severity:
            alerts.append({
                "pid":      col,
                "label":    cfg["label"],
                "severity": severity,
                "value":    round(float(val), 2),
                "unit":     cfg["unit"],
                "message":  _anomaly_message(col, val, cfg, severity),
            })

    # Isolation Forest on numeric columns if we have enough data
    if len(df) >= 50:
        try:
            from sklearn.ensemble import IsolationForest
            numeric_cols = [c for c in df.select_dtypes(include=[np.number]).columns
                            if c not in ("elapsed_s",) and df[c].notna().sum() > 30]
            if numeric_cols:
                X      = df[numeric_cols].fillna(df[numeric_cols].median())
                clf    = IsolationForest(contamination=0.05, random_state=42)
                scores = clf.fit_predict(X)
                n_anomalies = (scores == -1).sum()
                if n_anomalies > 0:
                    anomaly_rate = round(n_anomalies / len(df) * 100, 1)
                    if anomaly_rate > 8:
                        alerts.append({
                            "pid":      "ML_ISOLATION_FOREST",
                            "label":    "Pattern Anomalies",
                            "severity": "warning",
                            "value":    anomaly_rate,
                            "unit":     "%",
                            "message":  f"ML detected unusual telemetry patterns in {anomaly_rate}% of samples this session.",
                        })
        except ImportError:
            pass

    return alerts

def _anomaly_message(col: str, val: float, cfg: dict, severity: str) -> str:
    messages = {
        "COOLANT_TEMP":      f"Coolant temperature averaging {val:.1f}°C — {'critically high, stop soon' if severity == 'critical' else 'running warm, monitor closely'}.",
        "ENGINE_OIL_TEMP":   f"Oil temperature at {val:.1f}°C — {'critically high' if severity == 'critical' else 'elevated, check oil level'}.",
        "LONG_FUEL_TRIM_1":  f"Long-term fuel trim bank 1 at {val:+.1f}% — {'significant fuel delivery issue, check O2 sensor or injectors' if severity == 'critical' else 'outside normal range, monitor over next few drives'}.",
        "SHORT_FUEL_TRIM_1": f"Short-term fuel trim bank 1 at {val:+.1f}% — ECU actively compensating for {'rich' if val < 0 else 'lean'} condition.",
        "LONG_FUEL_TRIM_2":  f"Long-term fuel trim bank 2 at {val:+.1f}% — check bank 2 O2 sensor.",
        "INTAKE_TEMP":       f"Intake air temperature {val:.1f}°C — {'very hot intake air reduces power' if severity == 'critical' else 'warm intake air'}.",
        "CONTROL_VOLTAGE":   f"Battery/charging voltage {val:.2f}V — {'critically low, charging system fault' if severity == 'critical' else 'slightly low, check alternator'}.",
        "ENGINE_LOAD":       f"Engine load averaging {val:.1f}% — {'sustained near-maximum load' if severity == 'critical' else 'high sustained load'}.",
        "RPM":               f"RPM averaging {val:.0f} — {'near redline territory' if severity == 'critical' else 'high RPM sustained'}.",
    }
    return messages.get(col, f"{cfg['label']} at {val:.2f}{cfg['unit']} ({severity})")

def summarize_session(df: pd.DataFrame, path: Path) -> dict:
    duration_s = float((df["timestamp"].max() - df["timestamp"].min()).total_seconds())

    def safe_mean(col):
        return round(float(df[col].dropna().mean()), 2) if col in df.columns and df[col].notna().any() else None
    def safe_max(col):
        return round(float(df[col].dropna().max()), 2) if col in df.columns and df[col].notna().any() else None

    moving = df[df["SPEED"] > 2] if "SPEED" in df.columns else pd.DataFrame()

    return {
        "filename":        path.name,
        "session_date":    df["timestamp"].min().strftime("%Y-%m-%d"),
        "session_time":    df["timestamp"].min().strftime("%H:%M"),
        "duration_min":    round(duration_s / 60, 1),
        "sample_count":    len(df),
        "avg_rpm":         safe_mean("RPM"),
        "max_rpm":         safe_max("RPM"),
        "avg_speed_kmh":   safe_mean("SPEED"),
        "max_speed_kmh":   safe_max("SPEED"),
        "avg_coolant_c":   safe_mean("COOLANT_TEMP"),
        "max_coolant_c":   safe_max("COOLANT_TEMP"),
        "avg_engine_load": safe_mean("ENGINE_LOAD"),
        "ltft_b1":         safe_mean("LONG_FUEL_TRIM_1"),
        "stft_b1":         safe_mean("SHORT_FUEL_TRIM_1"),
        "avg_timing":      safe_mean("TIMING_ADVANCE"),
        "avg_maf":         safe_mean("MAF"),
        "pct_time_moving": round(len(moving) / len(df) * 100, 1) if len(df) > 0 else None,
        "fuel_level_pct":  safe_mean("FUEL_LEVEL"),
        "battery_v":       safe_mean("CONTROL_VOLTAGE"),
    }

def _generate_insights(df: pd.DataFrame, stats: dict) -> list[dict]:
    """Rule-based insight cards for the web dashboard."""
    insights = []

    ltft      = stats.get("ltft_avg")
    pct_moving = stats.get("pct_moving", 75.0)
    dips      = stats.get("dips_below_13_5", 0)
    min_v     = stats.get("min_voltage")
    avg_v     = stats.get("avg_voltage", 14.0)

    # 1. Long fuel trim
    if ltft is not None:
        if abs(ltft) >= 7.5:
            direction = "lean" if ltft < 0 else "rich"
            cause = "an air leak, MAF drift, or fuel pressure issue" if ltft < 0 else "an injector leak or O2 sensor issue"
            insights.append({
                "type": "warning",
                "title": f"Long fuel trim trending {direction} ({ltft:+.1f}%)",
                "body": (
                    f"LTFT has been running consistently around {ltft:.1f}% on this drive. "
                    f"This suggests the ECU has been compensating for a persistently {direction} condition — "
                    f"possible causes include {cause}. Worth trending across sessions to see if it's getting worse."
                ),
            })

    # 2. Timing retard
    if "TIMING_ADVANCE" in df.columns:
        timing = df["TIMING_ADVANCE"].dropna()
        min_timing = float(timing.min()) if not timing.empty else 99
        n_retard = int((timing < 5).sum())
        if min_timing < 0 or n_retard > 3:
            lean_note = "Combined with the lean LTFT pattern, it's worth noting. " if (ltft is not None and ltft < -5) else ""
            insights.append({
                "type": "warning",
                "title": f"Timing retard event{'s' if n_retard > 1 else ''} detected (min {min_timing:.1f}°)",
                "body": (
                    f"{n_retard} timing retard event(s) were captured. The FA24 pulls timing aggressively when it "
                    f"detects potential knock. A single event is not alarming, but {lean_note}"
                    f"premium fuel and monitoring over future drives is recommended."
                ),
            })

    # 3. Warm-up
    if "COOLANT_TEMP" in df.columns:
        coolant = df["COOLANT_TEMP"].dropna()
        if not coolant.empty and (coolant >= 80).any():
            warmup_idx  = (coolant >= 80).idxmax()
            warmup_s    = float(df.loc[warmup_idx, "elapsed_s"]) if warmup_idx in df.index else None
            oil_warmup_s = None
            if "ENGINE_OIL_TEMP" in df.columns:
                oil = df["ENGINE_OIL_TEMP"].dropna()
                if not oil.empty and (oil >= 80).any():
                    oi = (oil >= 80).idxmax()
                    oil_warmup_s = float(df.loc[oi, "elapsed_s"]) if oi in df.index else None
            ambient = None
            if "AMBIENT_TEMP" in df.columns and df["AMBIENT_TEMP"].notna().any():
                ambient = float(df["AMBIENT_TEMP"].dropna().iloc[0])
            ambient_str = f"on a {ambient:.0f}°C morning" if ambient is not None else ""
            c_min = round(warmup_s / 60, 1) if warmup_s else "?"
            o_min = round(oil_warmup_s / 60, 1) if oil_warmup_s else "?"
            oil_str = f", oil at {o_min} min" if oil_warmup_s else ""
            insights.append({
                "type": "success",
                "title": "Warm-up completed normally",
                "body": (
                    f"Coolant hit 80°C at {c_min} min{oil_str} {ambient_str} — both within expected range "
                    f"for a cold start. No extended cold-idle detected. The FA24 warms up efficiently on a commute-style drive."
                ),
            })

    # 4. Hard acceleration
    if "SPEED" in df.columns:
        speed   = df["SPEED"].fillna(0)
        dt_s    = df["elapsed_s"].diff().replace(0, np.nan)
        accel   = speed.diff() / dt_s / 3.6  # m/s²
        n_hard  = int((accel > 2.5).sum())
        max_spd = float(speed.max())
        thr_pk  = round(float(df["THROTTLE_POS"].dropna().max()), 1) if "THROTTLE_POS" in df.columns and df["THROTTLE_POS"].notna().any() else None
        thr_str = f" Throttle peaked at {thr_pk}% briefly." if thr_pk else ""
        if n_hard == 0:
            insights.append({
                "type": "success",
                "title": "No hard acceleration events",
                "body": (
                    f"Max speed reached {max_spd:.0f} kph, but no events exceeded 2.5 m/s² acceleration threshold.{thr_str} "
                    f"Drive style was calm and commute-appropriate — consistent with good long-term engine health habits."
                ),
            })
        else:
            insights.append({
                "type": "info",
                "title": f"{n_hard} hard acceleration event(s) detected",
                "body": (
                    f"Max speed reached {max_spd:.0f} kph with {n_hard} event(s) above 2.5 m/s².{thr_str} "
                    f"Occasional spirited driving is within spec for the FA24."
                ),
            })

    # 5. Voltage / battery
    if min_v is not None:
        if dips > 0:
            insights.append({
                "type": "info",
                "title": f"Voltage dips to {min_v:.2f}V — monitor battery",
                "body": (
                    f"{dips} brief dip(s) below 13.5V were recorded. These may correspond to high-load moments "
                    f"(AC compressor, fans). Average of {avg_v:.2f}V confirms the alternator is charging normally. "
                    f"If dips become frequent or deeper, a battery health test is worth scheduling."
                ),
            })
        else:
            insights.append({
                "type": "success",
                "title": f"Charging system healthy ({min_v:.2f}V min)",
                "body": f"Voltage stayed above 13.5V throughout the drive. Alternator is maintaining charge correctly.",
            })

    # 6. Standstill %
    idle_pct = round(100.0 - pct_moving, 1)
    if idle_pct > 0:
        idle_df   = df[df["SPEED"] <= 2] if "SPEED" in df.columns else pd.DataFrame()
        idle_rpm  = round(float(idle_df["RPM"].dropna().mean()), 0) if "RPM" in idle_df.columns and not idle_df.empty else 720
        insights.append({
            "type": "info",
            "title": f"{idle_pct:.0f}% of drive time at standstill",
            "body": (
                f"Consistent with stop-and-go traffic. Idle RPM averaged a healthy {idle_rpm:.0f} RPM. "
                f"No abnormal idle quality detected. No action needed."
            ),
        })

    # 7. Catalyst temp
    if "CATALYST_TEMP_B1S1" in df.columns:
        cat = df["CATALYST_TEMP_B1S1"].dropna()
        if not cat.empty:
            cat_avg = float(cat.mean())
            cat_max = float(cat.max())
            if cat_avg > 300 and cat_max < 900:
                insights.append({
                    "type": "success",
                    "title": "Catalyst running at healthy temp",
                    "body": (
                        f"Catalyst B1S1 averaged {cat_avg:.0f}°C and peaked at {cat_max:.0f}°C — "
                        f"well within the FA24's normal operating band. The catalyst is lit off and actively "
                        f"converting emissions throughout the drive."
                    ),
                })
            elif cat_max >= 900:
                insights.append({
                    "type": "warning",
                    "title": f"Catalyst temp elevated (peak {cat_max:.0f}°C)",
                    "body": (
                        f"Catalyst temperature peaked at {cat_max:.0f}°C. While FA24 cats can handle high temps, "
                        f"sustained operation above 900°C accelerates washcoat degradation. Monitor fuel trims."
                    ),
                })

    return insights


def _compute_trip_report(df: pd.DataFrame, filename: str) -> dict:
    """Compute full trip analytics for the web dashboard."""
    t_start = df["timestamp"].min()
    t_end   = df["timestamp"].max()
    duration_s   = (t_end - t_start).total_seconds()
    duration_min = duration_s / 60.0

    # --- date / time strings ---
    DAY   = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    MON   = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    trip_date = f"{DAY[t_start.weekday()]} {MON[t_start.month-1]} {t_start.day}, {t_start.year}"

    def _fmt(dt):
        h = dt.hour % 12 or 12
        return f"{h}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"
    trip_time_range = f"{_fmt(t_start)} \u2013 {_fmt(t_end)}"

    # trip label
    h = t_start.hour
    if   5  <= h < 12: trip_label = "Morning Commute"
    elif 12 <= h < 14: trip_label = "Midday Drive"
    elif 14 <= h < 18: trip_label = "Afternoon Drive"
    elif 18 <= h < 21: trip_label = "Evening Commute"
    else:              trip_label = "Night Drive"

    # --- distance ---
    dist_km = 0.0
    if "DIST_SINCE_CLEAR" in df.columns:
        d = df["DIST_SINCE_CLEAR"].dropna()
        if len(d) > 1:
            dist_km = max(0.0, float(d.iloc[-1] - d.iloc[0]))
    if dist_km == 0.0 and "ODOMETER" in df.columns:
        od = df["ODOMETER"].dropna()
        if len(od) > 1:
            dist_km = max(0.0, float(od.iloc[-1] - od.iloc[0]))
    dist_miles = round(dist_km * 0.621371, 1)

    # --- speed ---
    moving = df[df["SPEED"] > 2] if "SPEED" in df.columns else pd.DataFrame()
    avg_spd_kph = round(float(moving["SPEED"].mean()), 1) if not moving.empty else 0.0
    avg_spd_mph = round(avg_spd_kph * 0.621371, 1)
    max_spd_kph = round(float(df["SPEED"].max()), 1) if "SPEED" in df.columns else 0.0
    pct_moving  = round(len(moving) / len(df) * 100.0, 1) if len(df) > 0 else 0.0

    # --- fuel ---
    fuel_L = None
    fuel_L100 = None
    fuel_mpg  = None
    if "MAF" in df.columns and df["MAF"].notna().any():
        maf  = df["MAF"].fillna(0.0)
        dt_s = df["elapsed_s"].diff().fillna(3.5).clip(0, 10)
        fuel_g = float((maf / 14.7 * dt_s).sum())
        fuel_L = round(fuel_g / 740.0, 2)
        if dist_km > 0.5:
            fuel_L100 = round(fuel_L / dist_km * 100.0, 1)
            fuel_mpg  = round(235.21 / fuel_L100, 1) if fuel_L100 > 0 else None

    # --- thermal ---
    tail = df.tail(20)
    def _tail_mean(col):
        return round(float(tail[col].dropna().mean()), 1) if col in tail.columns and tail[col].notna().any() else None

    coolant_end = _tail_mean("COOLANT_TEMP")
    oil_end     = _tail_mean("ENGINE_OIL_TEMP")

    def _thermal_status(t, warn, crit):
        if t is None: return "Unknown"
        if t >= crit: return "Critical"
        if t >= warn: return "Warning"
        return "Normal"

    # --- fueling ---
    def _col_mean(col):
        return round(float(df[col].dropna().mean()), 2) if col in df.columns and df[col].notna().any() else None

    stft = _col_mean("SHORT_FUEL_TRIM_1")
    ltft = _col_mean("LONG_FUEL_TRIM_1")

    closed_loop_pct = None
    if "FUEL_SYSTEM_STATUS" in df.columns:
        n_cl = df["FUEL_SYSTEM_STATUS"].str.contains("CL", na=False).sum()
        closed_loop_pct = round(n_cl / len(df) * 100.0, 1)

    def _stft_status(v):
        if v is None: return "Unknown"
        return "Critical" if abs(v) >= 20 else "Watch" if abs(v) >= 10 else "Normal"

    def _ltft_status(v):
        if v is None: return "Unknown"
        return "Critical" if abs(v) >= 12 else "Watch" if abs(v) >= 7.5 else "Normal"

    # --- electrical ---
    avg_v = round(float(df["CONTROL_VOLTAGE"].dropna().mean()), 2) if "CONTROL_VOLTAGE" in df.columns and df["CONTROL_VOLTAGE"].notna().any() else None
    min_v = round(float(df["CONTROL_VOLTAGE"].dropna().min()), 2) if "CONTROL_VOLTAGE" in df.columns and df["CONTROL_VOLTAGE"].notna().any() else None
    dips  = int((df["CONTROL_VOLTAGE"].dropna() < 13.5).sum()) if "CONTROL_VOLTAGE" in df.columns else 0

    def _v_status(v):
        if v is None: return "Unknown"
        if v <= 11.5: return "Critical"
        if v <= 12.5: return "Low dip"
        if v <= 13.8: return "Watch"
        return "Good"

    has_cel = False
    if "DIST_WITH_MIL" in df.columns:
        dmil = df["DIST_WITH_MIL"].dropna()
        if not dmil.empty and float(dmil.iloc[-1]) > 0:
            has_cel = True

    odometer_km = None
    if "ODOMETER" in df.columns:
        od = df["ODOMETER"].dropna()
        if not od.empty:
            odometer_km = int(round(float(od.iloc[-1])))

    fuel_level = round(float(df["FUEL_LEVEL"].dropna().iloc[-1]), 1) if "FUEL_LEVEL" in df.columns and df["FUEL_LEVEL"].notna().any() else None

    # --- warm-up chart (resample ~every 30 s, first 25 min) ---
    wu_df = df[df["elapsed_s"] <= 1500].copy()
    step  = max(1, len(wu_df) // 60)
    samp  = wu_df.iloc[::step]
    warmup_labels  = [round(float(v) / 60.0, 2) for v in samp["elapsed_s"].tolist()]
    warmup_coolant = [round(float(v), 1) if pd.notna(v) else None for v in (samp["COOLANT_TEMP"].tolist() if "COOLANT_TEMP" in samp.columns else [])]
    warmup_oil     = [round(float(v), 1) if pd.notna(v) else None for v in (samp["ENGINE_OIL_TEMP"].tolist() if "ENGINE_OIL_TEMP" in samp.columns else [])]

    # --- insights ---
    stats_ctx = {
        "ltft_avg": ltft, "stft_avg": stft,
        "pct_moving": pct_moving,
        "avg_voltage": avg_v, "min_voltage": min_v, "dips_below_13_5": dips,
        "closed_loop_pct": closed_loop_pct,
        "fuel_used_L": fuel_L,
    }
    insights = _generate_insights(df, stats_ctx)

    alerts      = detect_anomalies(df)
    health_score = _health_score(alerts)

    return {
        "vehicle":        "GR86",
        "filename":       filename,
        "trip_label":     trip_label,
        "trip_date":      trip_date,
        "trip_time_range": trip_time_range,
        "stats": {
            "distance_km":        round(dist_km, 1),
            "distance_miles":     dist_miles,
            "duration_min":       round(duration_min, 1),
            "avg_speed_kph":      avg_spd_kph,
            "avg_speed_mph":      avg_spd_mph,
            "max_speed_kph":      max_spd_kph,
            "fuel_used_L":        fuel_L,
            "fuel_economy_L100km": fuel_L100,
            "fuel_economy_mpg":   fuel_mpg,
        },
        "warmup_chart": {
            "labels_min": warmup_labels,
            "coolant":    warmup_coolant,
            "oil":        warmup_oil,
        },
        "drive_profile": {
            "moving_pct": pct_moving,
            "idle_pct":   round(100.0 - pct_moving, 1),
        },
        "thermal": {
            "coolant_temp":   coolant_end,
            "coolant_status": _thermal_status(coolant_end, 100, 108),
            "oil_temp":       oil_end,
            "oil_status":     _thermal_status(oil_end, 120, 135),
        },
        "fueling": {
            "stft_avg":          stft,
            "stft_status":       _stft_status(stft),
            "ltft_avg":          ltft,
            "ltft_status":       _ltft_status(ltft),
            "closed_loop_pct":   closed_loop_pct,
            "open_loop_pct":     round(100.0 - closed_loop_pct, 1) if closed_loop_pct is not None else None,
            "closed_loop_status": (
                "Good" if closed_loop_pct is not None and closed_loop_pct >= 75
                else "Watch" if closed_loop_pct is not None and closed_loop_pct >= 50
                else "Low"
            ),
        },
        "electrical": {
            "avg_voltage":        avg_v,
            "avg_voltage_status": _v_status(avg_v),
            "min_voltage":        min_v,
            "min_voltage_status": _v_status(min_v),
            "dips_below_13_5v":   dips,
            "cel_value":          "None" if not has_cel else "Active",
            "cel_status":         "Clear" if not has_cel else "Active",
        },
        "odometer_km":    odometer_km,
        "fuel_level_pct": fuel_level,
        "has_dtc":        has_cel,
        "health_score":   health_score,
        "insights":       insights,
    }


def _health_score(alerts: list[dict]) -> int:
    """Simple 0-100 score. 100 = no alerts, deduct for warnings/criticals."""
    score = 100
    for a in alerts:
        if a["severity"] == "critical": score -= 25
        elif a["severity"] == "warning": score -= 10
    return max(0, score)

# ── database persistence ──────────────────────────────────────────────────────
async def _persist_session(
    summary: dict,
    alerts: list[dict],
    health_score: int,
) -> None:
    """Upsert session + alerts into PostgreSQL. Silently skips if DB unavailable."""
    if not _pool:
        return
    try:
        async with _pool.acquire() as conn:
            # Ensure default vehicle row exists
            await conn.execute(
                """
                INSERT INTO vehicles (vehicle_id, make, model, year, engine)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (vehicle_id) DO NOTHING
                """,
                "default", "Toyota", "GR86", 2023, "FA24",
            )

            # Check if session already persisted
            existing_id = await conn.fetchval(
                "SELECT id FROM sessions WHERE filename = $1",
                summary["filename"],
            )

            if existing_id is None:
                session_id = await conn.fetchval(
                    """
                    INSERT INTO sessions (
                        vehicle_id, filename, session_date, session_time,
                        duration_min, sample_count,
                        avg_rpm, max_rpm, avg_speed_kmh, max_speed_kmh,
                        avg_coolant_c, max_coolant_c, avg_engine_load,
                        pct_time_moving, ltft_b1, stft_b1,
                        avg_timing, avg_maf, fuel_level_pct, battery_v,
                        health_score
                    ) VALUES (
                        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
                        $11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21
                    ) RETURNING id
                    """,
                    "default",
                    summary["filename"],
                    summary["session_date"],
                    summary["session_time"],
                    summary["duration_min"],
                    summary["sample_count"],
                    summary["avg_rpm"],
                    summary["max_rpm"],
                    summary["avg_speed_kmh"],
                    summary["max_speed_kmh"],
                    summary["avg_coolant_c"],
                    summary["max_coolant_c"],
                    summary["avg_engine_load"],
                    summary["pct_time_moving"],
                    summary["ltft_b1"],
                    summary["stft_b1"],
                    summary["avg_timing"],
                    summary["avg_maf"],
                    summary["fuel_level_pct"],
                    summary["battery_v"],
                    health_score,
                )
            else:
                # Update health score in case alerts changed
                await conn.execute(
                    "UPDATE sessions SET health_score = $1 WHERE id = $2",
                    health_score, existing_id,
                )
                session_id = existing_id

            if session_id and alerts:
                await conn.execute(
                    "DELETE FROM alerts WHERE session_id = $1", session_id
                )
                await conn.executemany(
                    """
                    INSERT INTO alerts
                        (session_id, vehicle_id, pid, label, severity, value, unit, message)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    [
                        (
                            session_id, "default",
                            a["pid"], a["label"], a["severity"],
                            a["value"], a["unit"], a["message"],
                        )
                        for a in alerts
                    ],
                )
    except Exception as e:
        print(f"[db] persist_session failed: {e}")


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"service": "Acty Mobile API", "status": "ok", "version": "0.1.0"}

@app.get("/health")
async def health():
    csv = find_latest_csv()
    db_connected = False
    if DATABASE_URL:
        try:
            conn = await get_db_connection()
            await conn.close()
            db_connected = True
        except Exception:
            db_connected = False

    return {
        "status":        "ok",
        "csv_dir":       str(CSV_DIR),
        "latest_csv":    csv.name if csv else None,
        "session_count": len(find_all_csvs()),
        "db_connected":  db_connected,
    }

@app.get("/insights")
async def insights(session: Optional[str] = None):
    """
    Main endpoint. Returns:
      - session summary stats
      - anomaly alerts with severity + human-readable messages
      - sparkline data for key PIDs (last 60 samples)
    """
    if session:
        path = CSV_DIR / session
        if not path.exists():
            raise HTTPException(404, f"Session not found: {session}")
    else:
        path = find_latest_csv()
        if not path:
            raise HTTPException(404, f"No acty_obd_*.csv files found in {CSV_DIR}")

    df      = load_csv(path)
    summary = summarize_session(df, path)
    alerts  = detect_anomalies(df)
    score   = _health_score(alerts)

    # Sparkline data — last 60 samples of key PIDs
    sparkline_pids = ["RPM", "SPEED", "COOLANT_TEMP", "ENGINE_LOAD",
                      "SHORT_FUEL_TRIM_1", "LONG_FUEL_TRIM_1", "TIMING_ADVANCE", "MAF"]
    sparklines = {}
    tail = df.tail(60)
    for pid in sparkline_pids:
        if pid in tail.columns:
            vals = tail[pid].ffill().fillna(0).round(2).tolist()
            sparklines[pid] = vals

    # Persist to DB (fire-and-forget; never blocks the response)
    asyncio.create_task(_persist_session(summary, alerts, score))

    return {
        "summary":      summary,
        "alerts":       alerts,
        "sparklines":   sparklines,
        "alert_count":  len(alerts),
        "health_score": score,
    }

# ── report endpoint ───────────────────────────────────────────────────────────
@app.post("/api/v1/report")
async def diagnostic_report(payload: dict):
    """
    Generate a RAG-grounded diagnostic report.
    Expects: { dtc_codes, anomalies, vehicle_data, vehicle_id }
    """
    result = await generate_diagnostic_report(
        dtc_codes=payload.get("dtc_codes", []),
        anomalies=payload.get("anomalies", []),
        vehicle_data=payload.get("vehicle_data", {}),
        vehicle_id=payload.get("vehicle_id"),
    )
    return result

@app.get("/sessions")
async def sessions():
    """List all available CSV sessions."""
    csvs   = find_all_csvs()
    result = []
    for p in csvs[:20]:
        try:
            df = load_csv(p)
            s  = summarize_session(df, p)
            result.append(s)
        except Exception:
            result.append({"filename": p.name, "error": "parse failed"})
    return {"sessions": result, "total": len(csvs)}

@app.get("/sessions/{filename}")
async def session_detail(filename: str):
    """Full insights for a specific session by filename."""
    return await insights(session=filename)


@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """
    Accept a CSV upload, run full trip analysis, return dashboard JSON.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only .csv files are accepted.")
    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents), parse_dates=["timestamp"])
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    except Exception as e:
        raise HTTPException(422, f"Could not parse CSV: {e}")
    if len(df) < 5:
        raise HTTPException(422, "CSV has too few rows to analyse.")

    report = _compute_trip_report(df, file.filename)

    # Persist to DB if available (fire-and-forget)
    summary = summarize_session(df, Path(file.filename))
    alerts  = detect_anomalies(df)
    asyncio.create_task(_persist_session(summary, alerts, report["health_score"]))

    return report


# ── web dashboard ─────────────────────────────────────────────────────────────
_WEB_DIR = Path(__file__).parent.parent.parent / "web"

@app.get("/app", response_class=FileResponse)
async def web_app():
    """Serve the browser dashboard."""
    index = _WEB_DIR / "index.html"
    if not index.exists():
        raise HTTPException(404, "Web dashboard not found. Make sure web/index.html exists.")
    return FileResponse(str(index), media_type="text/html")


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{'='*55}")
    print(f"  Acty Mobile API")
    print(f"  CSV dir : {CSV_DIR}")
    print(f"  Serving : http://{HOST}:{PORT}")
    print(f"\n  On your phone (same WiFi):")
    print(f"  Run: python3 -c \"import socket; print(socket.gethostbyname(socket.gethostname()))\"")
    print(f"  Then open: http://<your-ip>:{PORT}/insights")
    print(f"{'='*55}\n")
    uvicorn.run("server:app", host=HOST, port=PORT, reload=True)
