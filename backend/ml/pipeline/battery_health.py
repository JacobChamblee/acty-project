#!/usr/bin/env python3
"""
battery_health.py
-----------------
Acty ML Pipeline — Battery & Alternator Health Monitor

Tracks 12V lead-acid battery and alternator health from CONTROL_VOLTAGE
telemetry. No additional hardware required — all signals come from the
OBD-II CONTROL_VOLTAGE PID already captured.

A degrading battery reveals itself through four measurable patterns:
  1. Cold-start voltage drop      — deeper sag during cranking
  2. Surface charge plateau       — voltage peaks lower after charging
  3. Alternator load response     — voltage sags more at high electrical load
  4. Recovery rate                — time to reach full charge after start

A failing alternator reveals itself through:
  1. Charging voltage below 13.8V at cruise
  2. Voltage instability at idle (ripple proxy)
  3. Voltage drop under accessory load (A/C, headlights)

Battery SoH estimate uses a simplified Peukert / capacity fade model
calibrated against the measurable voltage patterns above. It won't give
you a precise amp-hour reading but will reliably classify: Good / Monitor
/ Replace Soon / Replace Now.

Pipeline position:
    ingest.py → features.py → signal.py → rules.py → trends.py
                                                           ↓
                                              battery_health.py ← here
                                                           ↓
                                                    llm_report.py

Usage:
    python3 battery_health.py --csv acty_obd_20260313_071256.csv
    python3 battery_health.py --status
    python3 battery_health.py --set-battery-date 2024-01   # install month
    python3 battery_health.py --set-battery-age-months 36
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────
HISTORY_PATH = Path("data/battery_history.json")

# ── Voltage thresholds (12V lead-acid) ───────────────────────────────────────
# These apply to a car that has been sitting (resting voltage)
# and while running (charging voltage)
V = {
    # Charging voltage (engine running at cruise)
    "charge_healthy_min":   13.8,    # below this = alternator concern
    "charge_healthy_max":   14.7,    # above this = overcharge concern
    "charge_warn":          13.5,    # warning
    "charge_crit":          13.0,    # critical — not charging properly

    # Idle voltage with A/C load
    "idle_load_ok":         13.2,    # fine under accessory load
    "idle_load_warn":       12.8,    # marginal
    "idle_load_crit":       12.5,    # failing to maintain charge at idle

    # Cold start voltage sag (first 10 seconds)
    "start_sag_ok":         11.0,    # normal crank sag
    "start_sag_warn":       10.5,    # deeper than normal
    "start_sag_crit":       10.0,    # battery struggling to crank

    # Surface charge (voltage in first 30s before alternator takes over)
    "surface_charge_full":  12.7,    # fully charged resting
    "surface_charge_ok":    12.4,    # acceptable
    "surface_charge_low":   12.1,    # 50% charge
    "surface_charge_crit":  11.9,    # critical — needs charging

    # Recovery rate: time (seconds) for voltage to reach 13.8V after start
    "recovery_fast":        30.0,    # healthy battery charges quickly
    "recovery_slow":        90.0,    # degraded — takes longer to accept charge
    "recovery_very_slow":   180.0,   # failing
}

# SoH thresholds
SOH_BANDS = {
    "excellent": (0.85, 1.00, "✅", "Excellent"),
    "good":      (0.70, 0.85, "✅", "Good"),
    "monitor":   (0.55, 0.70, "👀", "Monitor"),
    "due_soon":  (0.35, 0.55, "⚠️", "Replace Soon"),
    "replace":   (0.00, 0.35, "🔴", "Replace Now"),
}

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class SessionBatteryMetrics:
    session_id:               str
    timestamp:                str
    odometer_km:              float
    ambient_temp_c:           float
    has_cold_start:           bool

    # Charging system
    cruise_voltage_mean:      Optional[float] = None   # voltage at speed >50 km/h
    cruise_voltage_std:       Optional[float] = None   # instability proxy
    cruise_voltage_min:       Optional[float] = None
    idle_voltage_mean:        Optional[float] = None   # voltage at idle, warmed up
    idle_voltage_min:         Optional[float] = None
    idle_with_load_voltage:   Optional[float] = None   # idle voltage (high load = A/C)

    # Battery condition (cold start sessions only)
    surface_charge_voltage:   Optional[float] = None   # first 5s before alternator
    crank_sag_min:            Optional[float] = None   # minimum during crank
    crank_sag_duration_s:     Optional[float] = None   # seconds below 12V
    recovery_time_s:          Optional[float] = None   # seconds to reach 13.8V

    # Alternator
    alternator_output_mean:   Optional[float] = None   # cruise voltage ≈ alt output
    voltage_drop_at_load:     Optional[float] = None   # idle - loaded_idle delta

    # Computed
    session_soh_estimate:     Optional[float] = None   # 0–1
    alternator_ok:            Optional[bool]  = None

@dataclass
class BatteryState:
    sessions:              list  = field(default_factory=list)
    battery_install_date:  Optional[str]   = None
    battery_age_months:    Optional[int]   = None
    battery_brand:         Optional[str]   = None
    soh_estimate:          float           = 1.0      # current best estimate
    soh_trend:             str             = "stable" # "improving","stable","declining"
    last_alert:            Optional[str]   = None
    alternator_concern:    bool            = False

# ── Extraction ────────────────────────────────────────────────────────────────

def extract_battery_metrics(df: pd.DataFrame, session_id: str) -> SessionBatteryMetrics:
    if "CONTROL_VOLTAGE" not in df.columns:
        raise ValueError("CONTROL_VOLTAGE not in DataFrame — check PID capture")

    v       = df["CONTROL_VOLTAGE"].ffill()
    speed   = df["SPEED"] if "SPEED" in df.columns else pd.Series([50]*len(df))
    elapsed = df["elapsed_s"] if "elapsed_s" in df.columns else pd.Series(range(len(df)))
    load    = df["ENGINE_LOAD"] if "ENGINE_LOAD" in df.columns else pd.Series([30]*len(df))
    ambient = float(df["AMBIENT_TEMP"].mean()) if "AMBIENT_TEMP" in df.columns else 20.0

    coolant_start = float(df["COOLANT_TEMP"].iloc[0]) if "COOLANT_TEMP" in df.columns else 90.0
    has_cold = coolant_start < 40.0

    odo = float(df["ODOMETER"].dropna().iloc[-1]) if "ODOMETER" in df.columns and df["ODOMETER"].notna().any() else 0.0

    # ── Cruise voltage (speed > 50 km/h, settled engine) ─────────────────────
    cruise_mask = (speed > 50) & (elapsed > 120)
    cruise_v = v[cruise_mask]
    cruise_mean = float(cruise_v.mean())     if len(cruise_v) > 5 else None
    cruise_std  = float(cruise_v.std())      if len(cruise_v) > 5 else None
    cruise_min  = float(cruise_v.min())      if len(cruise_v) > 5 else None

    # ── Idle voltage (speed ≤ 2, engine warm, elapsed > 3 min) ───────────────
    idle_mask    = (speed <= 2) & (elapsed > 180)
    idle_v       = v[idle_mask]
    idle_mean    = float(idle_v.mean()) if len(idle_v) > 5 else None
    idle_min     = float(idle_v.min())  if len(idle_v) > 5 else None

    # High-load idle (A/C running proxy: engine load > 20% at idle)
    if "ENGINE_LOAD" in df.columns:
        loaded_mask = idle_mask & (load > 20)
        loaded_v = v[loaded_mask]
        idle_load_v = float(loaded_v.mean()) if len(loaded_v) > 5 else idle_mean
    else:
        idle_load_v = idle_mean

    # ── Cold start metrics (first 60s) ────────────────────────────────────────
    surface_v = crank_min = crank_dur = recovery_s = None

    if has_cold:
        first_5s  = v[elapsed <= 5]
        first_60s = v[elapsed <= 60]
        elapsed_60 = elapsed[elapsed <= 60]

        if len(first_5s) > 0:
            surface_v = float(first_5s.mean())

        # Crank sag: minimum voltage in first 10s
        first_10s = v[elapsed <= 10]
        if len(first_10s) > 0:
            crank_min = float(first_10s.min())
            crank_dur = float((first_10s < 12.0).sum() * 8)  # 8s per sample approx

        # Recovery: first sample at or above 13.8V
        above_charge = elapsed_60[first_60s.values >= 13.8]
        if len(above_charge) > 0:
            recovery_s = float(above_charge.iloc[0])
        elif len(first_60s) > 0:
            # Didn't reach 13.8V in 60s — check full session
            above_charge_full = elapsed[v.values >= 13.8]
            recovery_s = float(above_charge_full.iloc[0]) if len(above_charge_full) > 0 else 999.0

    # ── Voltage drop under load ───────────────────────────────────────────────
    v_drop = None
    if idle_mean and idle_load_v:
        v_drop = round(idle_mean - idle_load_v, 3)

    # ── Alternator ok check ───────────────────────────────────────────────────
    alt_ok = None
    if cruise_mean:
        alt_ok = V["charge_warn"] <= cruise_mean <= V["charge_healthy_max"]

    # ── Session SoH estimate ──────────────────────────────────────────────────
    soh = _estimate_soh(
        surface_v     = surface_v,
        crank_min     = crank_min,
        cruise_mean   = cruise_mean,
        idle_load_v   = idle_load_v,
        recovery_s    = recovery_s,
        ambient_c     = ambient,
    )

    return SessionBatteryMetrics(
        session_id              = session_id,
        timestamp               = str(df["timestamp"].iloc[0]) if "timestamp" in df.columns else datetime.now().isoformat(),
        odometer_km             = odo,
        ambient_temp_c          = ambient,
        has_cold_start          = has_cold,
        cruise_voltage_mean     = round(cruise_mean, 3) if cruise_mean else None,
        cruise_voltage_std      = round(cruise_std, 4)  if cruise_std  else None,
        cruise_voltage_min      = round(cruise_min, 3)  if cruise_min  else None,
        idle_voltage_mean       = round(idle_mean, 3)   if idle_mean   else None,
        idle_voltage_min        = round(idle_min, 3)    if idle_min    else None,
        idle_with_load_voltage  = round(idle_load_v, 3) if idle_load_v else None,
        surface_charge_voltage  = round(surface_v, 3)   if surface_v   else None,
        crank_sag_min           = round(crank_min, 3)   if crank_min   else None,
        crank_sag_duration_s    = round(crank_dur, 1)   if crank_dur   else None,
        recovery_time_s         = round(recovery_s, 1)  if recovery_s  else None,
        alternator_output_mean  = round(cruise_mean, 3) if cruise_mean else None,
        voltage_drop_at_load    = round(v_drop, 3)      if v_drop      else None,
        session_soh_estimate    = soh,
        alternator_ok           = alt_ok,
    )

# ── SoH estimation ────────────────────────────────────────────────────────────

def _estimate_soh(
    surface_v:   Optional[float],
    crank_min:   Optional[float],
    cruise_mean: Optional[float],
    idle_load_v: Optional[float],
    recovery_s:  Optional[float],
    ambient_c:   float,
) -> Optional[float]:
    """
    Weighted multi-signal SoH estimate. Returns 0–1 or None if insufficient data.

    Temperature correction: cold weather suppresses voltage — adjust thresholds
    downward ~0.01V per °C below 20°C to avoid false low readings in winter.
    """
    scores = []
    weights = []

    # Temperature correction factor
    temp_offset = max(0, (20 - ambient_c) * 0.01)

    # ── Surface charge (weight 3 — most direct measure) ───────────────────────
    if surface_v is not None:
        sv = surface_v + temp_offset
        if   sv >= V["surface_charge_full"]:  sc_score = 1.00
        elif sv >= V["surface_charge_ok"]:    sc_score = 0.80
        elif sv >= V["surface_charge_low"]:   sc_score = 0.55
        elif sv >= V["surface_charge_crit"]:  sc_score = 0.30
        else:                                  sc_score = 0.10
        scores.append(sc_score); weights.append(3)

    # ── Crank sag minimum (weight 3) ──────────────────────────────────────────
    if crank_min is not None:
        cm = crank_min + temp_offset
        if   cm >= V["start_sag_ok"]:    cs_score = 1.00
        elif cm >= V["start_sag_warn"]:  cs_score = 0.65
        elif cm >= V["start_sag_crit"]:  cs_score = 0.35
        else:                             cs_score = 0.10
        scores.append(cs_score); weights.append(3)

    # ── Recovery time (weight 2) ──────────────────────────────────────────────
    if recovery_s is not None and recovery_s < 999:
        if   recovery_s <= V["recovery_fast"]:      r_score = 1.00
        elif recovery_s <= V["recovery_slow"]:      r_score = 0.70
        elif recovery_s <= V["recovery_very_slow"]: r_score = 0.40
        else:                                        r_score = 0.15
        scores.append(r_score); weights.append(2)

    # ── Cruise voltage (weight 2 — alternator output as proxy) ───────────────
    if cruise_mean is not None:
        if   cruise_mean >= V["charge_healthy_min"]: cv_score = 1.00
        elif cruise_mean >= V["charge_warn"]:         cv_score = 0.60
        elif cruise_mean >= V["charge_crit"]:         cv_score = 0.30
        else:                                          cv_score = 0.10
        scores.append(cv_score); weights.append(2)

    # ── Idle loaded voltage (weight 1) ────────────────────────────────────────
    if idle_load_v is not None:
        if   idle_load_v >= V["idle_load_ok"]:   il_score = 1.00
        elif idle_load_v >= V["idle_load_warn"]: il_score = 0.60
        elif idle_load_v >= V["idle_load_crit"]: il_score = 0.30
        else:                                      il_score = 0.10
        scores.append(il_score); weights.append(1)

    if not scores:
        return None

    soh = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
    return round(soh, 3)

def _soh_band(soh: float) -> tuple:
    for band, (lo, hi, icon, label) in SOH_BANDS.items():
        if lo <= soh <= hi:
            return band, icon, label
    return "unknown", "❓", "Unknown"

# ── Trend analysis ────────────────────────────────────────────────────────────

def compute_soh_trend(sessions: list[SessionBatteryMetrics], window: int = 5) -> str:
    """Determine if SoH is improving, stable, or declining over recent sessions."""
    estimates = [s.session_soh_estimate for s in sessions if s.session_soh_estimate is not None]
    if len(estimates) < 3:
        return "stable"
    recent = estimates[-window:]
    if len(recent) < 2:
        return "stable"
    # Linear regression slope
    x = np.arange(len(recent))
    slope = np.polyfit(x, recent, 1)[0]
    if slope < -0.01:
        return "declining"
    if slope > 0.005:
        return "improving"
    return "stable"

def detect_alternator_concern(sessions: list[SessionBatteryMetrics]) -> tuple[bool, str]:
    """Look for consistent alternator underperformance across recent sessions."""
    recent = sessions[-5:]
    cruise_readings = [s.cruise_voltage_mean for s in recent if s.cruise_voltage_mean]
    if not cruise_readings:
        return False, ""

    avg_cruise = np.mean(cruise_readings)
    low_count  = sum(1 for v in cruise_readings if v < V["charge_warn"])

    if low_count >= 3:
        return True, f"Cruise voltage averaging {avg_cruise:.2f}V — below healthy threshold in {low_count} recent sessions"
    if avg_cruise < V["charge_crit"]:
        return True, f"Cruise voltage critically low at {avg_cruise:.2f}V"

    # Check for voltage instability (high std dev at cruise = diode ripple proxy)
    stds = [s.cruise_voltage_std for s in recent if s.cruise_voltage_std]
    if stds and np.mean(stds) > 0.15:
        return True, f"Cruise voltage unstable (σ={np.mean(stds):.3f}V) — possible alternator diode issue"

    return False, ""

# ── Main detector class ───────────────────────────────────────────────────────

class BatteryHealthDetector:
    def __init__(self, history_path: Path = HISTORY_PATH):
        self.history_path = Path(history_path)
        self.state = self._load_state()

    def _load_state(self) -> BatteryState:
        if self.history_path.exists() and self.history_path.stat().st_size > 0:
            with open(self.history_path) as f:
                data = json.load(f)
            s = BatteryState()
            s.sessions             = data.get("sessions", [])
            s.battery_install_date = data.get("battery_install_date")
            s.battery_age_months   = data.get("battery_age_months")
            s.battery_brand        = data.get("battery_brand")
            s.soh_estimate         = data.get("soh_estimate", 1.0)
            s.soh_trend            = data.get("soh_trend", "stable")
            s.last_alert           = data.get("last_alert")
            s.alternator_concern   = data.get("alternator_concern", False)
            return s
        return BatteryState()

    def _save_state(self):
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_path, "w") as f:
            json.dump(asdict(self.state), f, indent=2, default=str)

    def ingest_session(self, df: pd.DataFrame, session_id: str) -> SessionBatteryMetrics:
        existing = [s["session_id"] for s in self.state.sessions]
        if session_id in existing:
            print(f"[BATT] Session {session_id} already ingested — skipping")
            return SessionBatteryMetrics(**next(s for s in self.state.sessions if s["session_id"] == session_id))

        metrics = extract_battery_metrics(df, session_id)
        self.state.sessions.append(asdict(metrics))

        # Update rolling SoH
        all_metrics = [SessionBatteryMetrics(**s) for s in self.state.sessions]
        recent_soh = [s.session_soh_estimate for s in all_metrics[-5:] if s.session_soh_estimate]
        if recent_soh:
            self.state.soh_estimate = round(float(np.mean(recent_soh)), 3)

        self.state.soh_trend = compute_soh_trend(all_metrics)

        # Alternator check
        alt_concern, alt_msg = detect_alternator_concern(all_metrics)
        self.state.alternator_concern = alt_concern
        if alt_concern:
            self.state.last_alert = alt_msg

        self._save_state()
        band, icon, label = _soh_band(self.state.soh_estimate)
        print(f"[BATT] Ingested {session_id}  "
              f"soh={self.state.soh_estimate:.0%}  "
              f"{icon} {label}  "
              f"trend={self.state.soh_trend}  "
              f"alt={'⚠️' if alt_concern else '✅'}")
        return metrics

    def status(self) -> dict:
        if not self.state.sessions:
            return {"status": "no_data", "message": "No sessions ingested yet"}

        soh   = self.state.soh_estimate
        band, icon, label = _soh_band(soh)
        latest = self.state.sessions[-1]

        result = {
            "soh_estimate":        soh,
            "soh_pct":             f"{soh:.0%}",
            "health_band":         band,
            "health_label":        label,
            "icon":                icon,
            "trend":               self.state.soh_trend,
            "sessions_analyzed":   len(self.state.sessions),
            "alternator_concern":  self.state.alternator_concern,
            "alert":               self.state.last_alert,

            # Latest session values
            "latest_cruise_v":     latest.get("cruise_voltage_mean"),
            "latest_idle_v":       latest.get("idle_voltage_mean"),
            "latest_idle_load_v":  latest.get("idle_with_load_voltage"),
            "latest_crank_sag":    latest.get("crank_sag_min"),
            "latest_recovery_s":   latest.get("recovery_time_s"),
            "latest_surface_v":    latest.get("surface_charge_voltage"),
        }

        # Age-based risk
        if self.state.battery_age_months:
            age = self.state.battery_age_months
            result["battery_age_months"] = age
            result["battery_install_date"] = self.state.battery_install_date
            if age > 60:
                result["age_risk"] = "high"
                result["age_note"] = f"Battery is {age} months old — past typical 48–60 month lifespan"
            elif age > 42:
                result["age_risk"] = "moderate"
                result["age_note"] = f"Battery is {age} months old — entering wear zone"
            else:
                result["age_risk"] = "low"

        # Recommendation
        result["recommendation"] = _recommendation(band, self.state.soh_trend,
                                                    self.state.alternator_concern,
                                                    self.state.battery_age_months)
        return result

    def set_battery_info(self, install_date: Optional[str] = None,
                          age_months: Optional[int] = None,
                          brand: Optional[str] = None):
        if install_date:
            self.state.battery_install_date = install_date
            # Compute age from install date
            try:
                from datetime import datetime
                install = datetime.strptime(install_date, "%Y-%m")
                now = datetime.now()
                months = (now.year - install.year) * 12 + (now.month - install.month)
                self.state.battery_age_months = months
                print(f"[BATT] Battery age: {months} months")
            except ValueError:
                pass
        if age_months:
            self.state.battery_age_months = age_months
        if brand:
            self.state.battery_brand = brand
        self._save_state()

def _recommendation(band: str, trend: str, alt_concern: bool, age_months: Optional[int]) -> str:
    if alt_concern:
        return ("Alternator concern detected — have the charging system tested before "
                "concluding the battery is at fault. A weak alternator can mask a healthy battery.")
    if band == "replace":
        return "Battery replacement recommended. Risk of no-start is high."
    if band == "due_soon":
        if trend == "declining":
            return "Battery declining and approaching end of life — schedule replacement within 1–2 months."
        return "Battery should be replaced within 3 months. Load test recommended."
    if band == "monitor":
        if age_months and age_months > 48:
            return "Battery is in the monitor zone and aging — have it load-tested at next service."
        return "Battery is functional but showing wear. Monitor across next 10 drives."
    if trend == "declining":
        return "Battery is still healthy but trending downward. Keep monitoring."
    return "Battery and charging system are healthy. No action needed."

# ── Pipeline integration helper ───────────────────────────────────────────────

def get_report_context(detector: "BatteryHealthDetector") -> dict:
    """
    Returns a dict suitable for injection into llm_report.py prompt context.
    """
    status = detector.status()
    return {
        "battery_soh":         status.get("soh_pct", "unknown"),
        "battery_health":      status.get("health_label", "unknown"),
        "battery_trend":       status.get("trend", "stable"),
        "alternator_ok":       not status.get("alternator_concern", False),
        "battery_alert":       status.get("alert"),
        "battery_recommend":   status.get("recommendation"),
        "battery_age_note":    status.get("age_note"),
        "cruise_voltage":      status.get("latest_cruise_v"),
        "idle_voltage":        status.get("latest_idle_v"),
        "crank_sag_min":       status.get("latest_crank_sag"),
    }

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Acty battery & alternator health monitor")
    parser.add_argument("--csv",                  help="Ingest a session CSV")
    parser.add_argument("--status",  action="store_true")
    parser.add_argument("--history", default=str(HISTORY_PATH))
    parser.add_argument("--set-battery-date",     metavar="YYYY-MM",
                        help="Battery install date (e.g. 2022-06)")
    parser.add_argument("--set-battery-age-months", type=int, metavar="N")
    parser.add_argument("--set-battery-brand",    metavar="BRAND")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    det = BatteryHealthDetector(history_path=args.history)

    if args.reset:
        det.state = BatteryState()
        det._save_state()
        print("[BATT] History cleared.")
        return

    if args.set_battery_date or args.set_battery_age_months or args.set_battery_brand:
        det.set_battery_info(
            install_date = args.set_battery_date,
            age_months   = args.set_battery_age_months,
            brand        = args.set_battery_brand,
        )

    if args.csv:
        path = Path(args.csv)
        if not path.exists():
            print(f"[ERROR] {path} not found")
            sys.exit(1)
        df = pd.read_csv(path, parse_dates=["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        metrics = det.ingest_session(df, path.stem)

        print(f"\n── Session Battery Metrics ──────────────────────────────")
        print(f"   Cold start:      {metrics.has_cold_start}")
        if metrics.surface_charge_voltage:
            print(f"   Surface charge:  {metrics.surface_charge_voltage:.3f}V")
        if metrics.crank_sag_min:
            print(f"   Crank sag min:   {metrics.crank_sag_min:.3f}V")
        if metrics.recovery_time_s:
            print(f"   Recovery to 13.8V: {metrics.recovery_time_s:.0f}s")
        if metrics.cruise_voltage_mean:
            print(f"   Cruise voltage:  {metrics.cruise_voltage_mean:.3f}V "
                  f"(σ={metrics.cruise_voltage_std:.4f})")
        if metrics.idle_voltage_mean:
            print(f"   Idle voltage:    {metrics.idle_voltage_mean:.3f}V")
        if metrics.idle_with_load_voltage:
            print(f"   Idle w/ load:    {metrics.idle_with_load_voltage:.3f}V")
        if metrics.session_soh_estimate:
            band, icon, label = _soh_band(metrics.session_soh_estimate)
            print(f"   Session SoH:     {metrics.session_soh_estimate:.0%}  {icon} {label}")
        print(f"────────────────────────────────────────────────────────\n")

    if args.status or args.csv or not any([args.set_battery_date,
                                           args.set_battery_age_months,
                                           args.set_battery_brand, args.reset]):
        s = det.status()
        if s.get("status") == "no_data":
            print("[BATT] No data. Ingest a CSV first with --csv.")
            return
        print(f"\n── Battery Health Status ────────────────────────────────")
        print(f"   SoH estimate:  {s['soh_pct']}  {s['icon']} {s['health_label']}")
        print(f"   Trend:         {s['trend']}")
        print(f"   Alternator:    {'⚠️  CONCERN — ' + s['alert'] if s['alternator_concern'] else '✅ OK'}")
        if s.get("age_note"):
            print(f"   Age:           {s['age_note']}")
        print(f"   Cruise V:      {s.get('latest_cruise_v', '—')}")
        print(f"   Idle V:        {s.get('latest_idle_v', '—')}")
        print(f"   Idle+Load V:   {s.get('latest_idle_load_v', '—')}")
        print(f"   Crank sag min: {s.get('latest_crank_sag', '—')}")
        print(f"   Recovery time: {s.get('latest_recovery_s', '—')}s")
        print(f"\n   → {s['recommendation']}")
        print(f"────────────────────────────────────────────────────────\n")

if __name__ == "__main__":
    main()
