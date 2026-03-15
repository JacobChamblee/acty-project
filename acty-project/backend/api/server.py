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
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import asyncpg
import numpy as np
import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

# ── database pool ─────────────────────────────────────────────────────────────
_pool: Optional[asyncpg.Pool] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool
    if DATABASE_URL:
        try:
            _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
            print(f"[db] Connected to PostgreSQL")
        except Exception as e:
            print(f"[db] Could not connect to PostgreSQL: {e}")
    yield
    if _pool:
        await _pool.close()


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="Acty Mobile API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # prototype — lock this down before production
    allow_methods=["*"],
    allow_headers=["*"],
)

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
def health():
    csv = find_latest_csv()
    return {
        "status":        "ok",
        "csv_dir":       str(CSV_DIR),
        "latest_csv":    csv.name if csv else None,
        "session_count": len(find_all_csvs()),
        "db_connected":  _pool is not None,
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
