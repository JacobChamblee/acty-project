#!/usr/bin/env python3
"""
maintenance_tracker.py
----------------------
Acty ML Pipeline — Unified Maintenance Interval Tracker

Tracks multiple maintenance items beyond oil changes using OBD-II telemetry,
odometer data, and driving behavior analysis. Each item uses the best available
detection strategy given what OBD-II can actually measure.

Detection strategies by item:
  Brakes        — stop event severity + deceleration profile analysis
  Tires         — odometer + stop event count + rotation reminder
  Trans fluid   — RPM/speed efficiency ratio drift (automatics) or interval (manuals)
  Diff fluid    — drivetrain efficiency proxy + interval
  Coolant       — interval + cold start temp delta drift
  Spark plugs   — misfire proxy via RPM jitter + timing scatter
  Air filter    — MAF vs throttle efficiency ratio drift
  Cabin filter  — interval only (no OBD signal)

Pipeline position:
    ingest.py → features.py → signal.py → rules.py → trends.py
                                                           ↓
                                           maintenance_tracker.py ← here
                                                           ↓
                                                    llm_report.py

Usage:
    python3 maintenance_tracker.py --csv acty_obd_20260313_161517.csv
    python3 maintenance_tracker.py --status
    python3 maintenance_tracker.py --set BRAKES --odometer 45856
    python3 maintenance_tracker.py --set TIRES --odometer 45856
    python3 maintenance_tracker.py --set-interval BRAKES_PADS --miles 30000
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

# ── Storage ───────────────────────────────────────────────────────────────────
HISTORY_PATH = Path("data/maintenance_history.json")

# ── Default intervals (km) ────────────────────────────────────────────────────
# All converted from common mile intervals
INTERVALS_KM = {
    "BRAKE_PADS":       48280,   # ~30,000 mi (varies widely by driving style)
    "BRAKE_FLUID":      32187,   # ~20,000 mi or 2 years
    "TIRE_ROTATION":     8047,   # ~5,000 mi
    "TIRE_REPLACEMENT": 64374,   # ~40,000 mi (varies by tire)
    "TRANS_FLUID":      72420,   # ~45,000 mi manual / 30k automatic
    "DIFF_FLUID":       48280,   # ~30,000 mi
    "COOLANT":          80467,   # ~50,000 mi or 5 years
    "SPARK_PLUGS":      96561,   # ~60,000 mi (iridium) / 30k conventional
    "AIR_FILTER":       24140,   # ~15,000 mi
    "CABIN_FILTER":     24140,   # ~15,000 mi
}

STATUS_COLORS = {
    "ok":        "✅",
    "monitor":   "👀",
    "due_soon":  "⚠️",
    "overdue":   "🔴",
    "no_data":   "❓",
}

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class StopEvent:
    """A single deceleration-to-stop event extracted from telemetry."""
    timestamp:         str
    speed_before_kmh:  float
    decel_rate:        float    # km/h per second — higher = harder stop
    elapsed_s:         float

@dataclass
class SessionDrivingMetrics:
    """Driving behavior metrics extracted from one session, used for wear modeling."""
    session_id:              str
    timestamp:               str
    odometer_km:             float
    ambient_temp_c:          float

    # Brakes
    stop_event_count:        int   = 0
    hard_stop_count:         int   = 0     # decel > 15 km/h/s
    avg_decel_rate:          float = 0.0
    max_decel_rate:          float = 0.0

    # Tires / drivetrain
    avg_speed_kmh:           float = 0.0
    pct_time_above_80kmh:    float = 0.0
    pct_time_idle:           float = 0.0

    # Transmission / drivetrain efficiency
    rpm_speed_ratio_mean:    float = 0.0   # RPM per km/h — drifts up as drivetrain wears
    rpm_speed_ratio_std:     float = 0.0

    # Air filter / MAF efficiency
    maf_per_load_unit:       float = 0.0   # MAF / engine_load — rises as filter clogs
    maf_at_idle:             float = 0.0

    # Spark plug proxy
    idle_rpm_jitter:         float = 0.0   # std dev of RPM at idle
    timing_scatter:          float = 0.0   # std dev of timing advance

    # Coolant
    coolant_start_temp_c:    Optional[float] = None
    coolant_time_to_80c_s:   Optional[float] = None

@dataclass
class MaintenanceItem:
    """State for a single maintenance item."""
    name:                  str
    last_service_odo_km:   Optional[float] = None
    last_service_date:     Optional[str]   = None
    interval_km:           float           = 0.0
    wear_score:            float           = 0.0    # 0–1, 1 = needs service
    behavior_adjustment:   float           = 0.0    # +/- from driving style
    confirmed_by_user:     bool            = False
    notes:                 str             = ""

@dataclass
class MaintenanceState:
    items:    dict = field(default_factory=dict)   # name -> MaintenanceItem dict
    sessions: list = field(default_factory=list)   # list of SessionDrivingMetrics dicts

# ── Metric extraction ─────────────────────────────────────────────────────────

def extract_stop_events(df: pd.DataFrame) -> list[StopEvent]:
    """Identify deceleration-to-stop events from speed trace."""
    events = []
    if "SPEED" not in df.columns or "timestamp" not in df.columns:
        return events

    speeds = df["SPEED"].fillna(0).values
    times  = df["elapsed_s"].values if "elapsed_s" in df.columns else np.arange(len(df))

    i = 1
    while i < len(speeds):
        # Detect transition from moving (>10 km/h) to stopped
        if speeds[i-1] > 10 and speeds[i] < 5:
            # Find the start of the deceleration (where speed was highest)
            j = i - 1
            while j > 0 and speeds[j-1] >= speeds[j]:
                j -= 1
            speed_before = float(speeds[j])
            dt = float(times[i]) - float(times[j])
            if dt > 0 and speed_before > 10:
                decel_rate = speed_before / dt   # km/h per second
                events.append(StopEvent(
                    timestamp        = str(df["timestamp"].iloc[i]),
                    speed_before_kmh = round(speed_before, 1),
                    decel_rate       = round(decel_rate, 2),
                    elapsed_s        = float(times[i]),
                ))
        i += 1

    return events

def extract_session_metrics(df: pd.DataFrame, session_id: str) -> SessionDrivingMetrics:
    """Extract all wear-relevant metrics from a session."""
    df = df.copy()
    idle   = df[df["SPEED"] <= 2] if "SPEED" in df.columns else pd.DataFrame()
    moving = df[df["SPEED"] > 2]  if "SPEED" in df.columns else pd.DataFrame()

    odo_km   = float(df["ODOMETER"].dropna().iloc[-1]) if "ODOMETER" in df.columns and df["ODOMETER"].notna().any() else 0.0
    ambient  = float(df["AMBIENT_TEMP"].mean()) if "AMBIENT_TEMP" in df.columns else 20.0

    # ── Stop events ───────────────────────────────────────────────────────────
    stops      = extract_stop_events(df)
    hard_stops = [s for s in stops if s.decel_rate > 15.0]
    avg_decel  = float(np.mean([s.decel_rate for s in stops])) if stops else 0.0
    max_decel  = float(max([s.decel_rate for s in stops], default=0.0))

    # ── Speed profile ─────────────────────────────────────────────────────────
    avg_speed   = float(moving["SPEED"].mean()) if len(moving) > 0 else 0.0
    pct_highway = float((df["SPEED"] > 80).mean()) if "SPEED" in df.columns else 0.0
    pct_idle    = float(len(idle) / max(len(df), 1))

    # ── RPM/speed ratio (drivetrain efficiency) ────────────────────────────────
    rpm_speed_mean = rpm_speed_std = 0.0
    if "RPM" in df.columns and "SPEED" in df.columns:
        steady = moving[(moving["SPEED"] > 30) & (moving["RPM"] > 500)]
        if len(steady) > 10:
            ratio = steady["RPM"] / steady["SPEED"].replace(0, np.nan)
            rpm_speed_mean = float(ratio.mean())
            rpm_speed_std  = float(ratio.std())

    # ── MAF efficiency (air filter proxy) ─────────────────────────────────────
    maf_per_load = maf_idle = 0.0
    if "MAF" in df.columns and "ENGINE_LOAD" in df.columns:
        valid = df[(df["ENGINE_LOAD"] > 5) & df["MAF"].notna()]
        if len(valid) > 10:
            maf_per_load = float((valid["MAF"] / valid["ENGINE_LOAD"].replace(0, np.nan)).mean())
        if len(idle) > 5:
            maf_idle = float(idle["MAF"].mean())

    # ── Spark plug proxies ────────────────────────────────────────────────────
    idle_jitter = timing_scatter = 0.0
    if "RPM" in df.columns and len(idle) > 10:
        settled = idle[idle["elapsed_s"] > 120] if "elapsed_s" in idle.columns else idle
        idle_jitter = float(settled["RPM"].std()) if len(settled) > 5 else 0.0
    if "TIMING_ADVANCE" in df.columns:
        timing_scatter = float(df["TIMING_ADVANCE"].std())

    # ── Coolant warmup ────────────────────────────────────────────────────────
    coolant_start = time_to_80c = None
    if "COOLANT_TEMP" in df.columns:
        coolant_start = float(df["COOLANT_TEMP"].iloc[0])
        if coolant_start < 40 and "elapsed_s" in df.columns:
            above = df[df["COOLANT_TEMP"] >= 80]
            if not above.empty:
                time_to_80c = float(above["elapsed_s"].iloc[0])

    return SessionDrivingMetrics(
        session_id           = session_id,
        timestamp            = str(df["timestamp"].iloc[0]) if "timestamp" in df.columns else datetime.now().isoformat(),
        odometer_km          = odo_km,
        ambient_temp_c       = ambient,
        stop_event_count     = len(stops),
        hard_stop_count      = len(hard_stops),
        avg_decel_rate       = round(avg_decel, 3),
        max_decel_rate       = round(max_decel, 3),
        avg_speed_kmh        = round(avg_speed, 1),
        pct_time_above_80kmh = round(pct_highway, 3),
        pct_time_idle        = round(pct_idle, 3),
        rpm_speed_ratio_mean = round(rpm_speed_mean, 3),
        rpm_speed_ratio_std  = round(rpm_speed_std, 3),
        maf_per_load_unit    = round(maf_per_load, 4),
        maf_at_idle          = round(maf_idle, 3),
        idle_rpm_jitter      = round(idle_jitter, 1),
        timing_scatter       = round(timing_scatter, 2),
        coolant_start_temp_c = coolant_start,
        coolant_time_to_80c_s= time_to_80c,
    )

# ── Wear models ───────────────────────────────────────────────────────────────

def brake_wear_rate(sessions: list[SessionDrivingMetrics]) -> float:
    """
    Returns a wear multiplier (1.0 = normal, >1.0 = accelerated wear).
    Hard stops and high decel rate increase pad wear significantly.
    City driving with many stops wears brakes faster than highway.
    """
    if not sessions:
        return 1.0
    recent = sessions[-min(10, len(sessions)):]
    avg_hard_stops_per_session = np.mean([s.hard_stop_count for s in recent])
    avg_decel = np.mean([s.avg_decel_rate for s in recent])

    # Hard stops add significant wear — each hard stop (>15 km/h/s)
    # is roughly 3x the wear of a normal stop
    hard_stop_multiplier = 1.0 + (avg_hard_stops_per_session * 0.08)
    decel_multiplier     = 1.0 + max(0, (avg_decel - 8.0) * 0.03)

    return round(min(hard_stop_multiplier * decel_multiplier, 3.0), 3)

def air_filter_efficiency(sessions: list[SessionDrivingMetrics]) -> float:
    """
    Track MAF/load ratio trend over time. Rising ratio = filter clogging.
    Returns normalized drift (0 = baseline, 1 = likely clogged).
    """
    if len(sessions) < 5:
        return 0.0
    ratios = [s.maf_per_load_unit for s in sessions if s.maf_per_load_unit > 0]
    if len(ratios) < 5:
        return 0.0
    baseline = np.mean(ratios[:3])
    recent   = np.mean(ratios[-3:])
    if baseline == 0:
        return 0.0
    drift = (recent - baseline) / baseline
    return round(max(0.0, min(1.0, drift * 5)), 3)

def spark_plug_health(sessions: list[SessionDrivingMetrics]) -> float:
    """
    Idle RPM jitter and timing scatter both increase as plugs wear.
    Returns normalized degradation score (0 = healthy, 1 = worn).
    """
    if len(sessions) < 5:
        return 0.0
    jitters = [s.idle_rpm_jitter for s in sessions if s.idle_rpm_jitter > 0]
    if len(jitters) < 5:
        return 0.0
    baseline = np.mean(jitters[:3])
    recent   = np.mean(jitters[-3:])
    if baseline == 0:
        return 0.0
    drift = (recent - baseline) / max(baseline, 50)
    return round(max(0.0, min(1.0, drift)), 3)

def drivetrain_efficiency_drift(sessions: list[SessionDrivingMetrics]) -> float:
    """
    RPM/speed ratio should be stable for a given gear ratio.
    Drift upward suggests drivetrain friction increase (relevant for fluid changes).
    Returns normalized drift (0 = baseline, 1 = significant degradation).
    """
    if len(sessions) < 5:
        return 0.0
    ratios = [s.rpm_speed_ratio_mean for s in sessions if s.rpm_speed_ratio_mean > 0]
    if len(ratios) < 5:
        return 0.0
    baseline = np.mean(ratios[:3])
    recent   = np.mean(ratios[-3:])
    if baseline == 0:
        return 0.0
    drift = (recent - baseline) / baseline
    return round(max(0.0, min(1.0, drift * 10)), 3)

# ── Main tracker class ────────────────────────────────────────────────────────

class MaintenanceTracker:
    def __init__(self, history_path: Path = HISTORY_PATH):
        self.history_path = Path(history_path)
        self.state = self._load_state()
        self._ensure_items()

    def _ensure_items(self):
        """Make sure all known maintenance items exist in state."""
        for name, interval_km in INTERVALS_KM.items():
            if name not in self.state.items:
                self.state.items[name] = asdict(MaintenanceItem(
                    name        = name,
                    interval_km = interval_km,
                ))
        self._save_state()

    def _load_state(self) -> MaintenanceState:
        if self.history_path.exists() and self.history_path.stat().st_size > 0:
            with open(self.history_path) as f:
                data = json.load(f)
            state = MaintenanceState()
            state.items    = data.get("items", {})
            state.sessions = data.get("sessions", [])
            return state
        return MaintenanceState()

    def _save_state(self):
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_path, "w") as f:
            json.dump({"items": self.state.items, "sessions": self.state.sessions},
                      f, indent=2, default=str)

    def ingest_session(self, df: pd.DataFrame, session_id: str):
        """Extract metrics and store session."""
        existing = [s["session_id"] for s in self.state.sessions]
        if session_id in existing:
            print(f"[MAINT] Session {session_id} already ingested — skipping")
            return
        metrics = extract_session_metrics(df, session_id)
        self.state.sessions.append(asdict(metrics))
        self._save_state()
        print(f"[MAINT] Ingested {session_id}  odo={metrics.odometer_km:.0f}km  "
              f"stops={metrics.stop_event_count}  hard_stops={metrics.hard_stop_count}")
        self._update_wear_scores()

    def _update_wear_scores(self):
        """Recalculate behavior-adjusted wear scores for all items."""
        sessions = [SessionDrivingMetrics(**s) for s in self.state.sessions]
        if not sessions:
            return

        brake_mult   = brake_wear_rate(sessions)
        filter_drift = air_filter_efficiency(sessions)
        plug_health  = spark_plug_health(sessions)
        dt_drift     = drivetrain_efficiency_drift(sessions)

        # Store behavior adjustments on relevant items
        for name in ["BRAKE_PADS", "BRAKE_FLUID"]:
            if name in self.state.items:
                self.state.items[name]["behavior_adjustment"] = round(brake_mult - 1.0, 3)

        if "AIR_FILTER" in self.state.items:
            self.state.items["AIR_FILTER"]["wear_score"] = filter_drift

        if "SPARK_PLUGS" in self.state.items:
            self.state.items["SPARK_PLUGS"]["wear_score"] = plug_health

        for name in ["TRANS_FLUID", "DIFF_FLUID"]:
            if name in self.state.items:
                self.state.items[name]["behavior_adjustment"] = round(dt_drift, 3)

        self._save_state()

    def record_service(self, item_name: str, odometer_km: float,
                       date: Optional[str] = None, notes: str = ""):
        """Record that a maintenance service was performed."""
        name = item_name.upper()
        if name not in self.state.items:
            print(f"[MAINT] Unknown item: {name}. Known: {list(INTERVALS_KM.keys())}")
            return
        self.state.items[name].update({
            "last_service_odo_km":  odometer_km,
            "last_service_date":    date or datetime.now().isoformat(),
            "confirmed_by_user":    True,
            "wear_score":           0.0,
            "behavior_adjustment":  0.0,
            "notes":                notes,
        })
        self._save_state()
        mi = odometer_km * 0.621
        print(f"[MAINT] ✅ {name} serviced at {odometer_km:.0f} km ({mi:.0f} mi)")

    def set_interval(self, item_name: str, miles: float):
        """Override the default service interval."""
        name = item_name.upper()
        if name not in self.state.items:
            print(f"[MAINT] Unknown item: {name}")
            return
        km = miles * 1.60934
        self.state.items[name]["interval_km"] = km
        self._save_state()
        print(f"[MAINT] {name} interval set to {miles:.0f} mi ({km:.0f} km)")

    def status(self, current_odo_km: Optional[float] = None) -> list[dict]:
        """
        Return status for all maintenance items.
        Uses latest session odometer if current_odo_km not provided.
        """
        if current_odo_km is None and self.state.sessions:
            current_odo_km = self.state.sessions[-1]["odometer_km"]
        if current_odo_km is None:
            return []

        current_mi = current_odo_km * 0.621
        results = []

        for name, item_data in self.state.items.items():
            item     = MaintenanceItem(**item_data)
            last_odo = item.last_service_odo_km
            interval = item.interval_km

            # Apply behavior multiplier to effective interval
            behavior_adj = item.behavior_adjustment
            if behavior_adj > 0:
                # Aggressive driving → shorter effective interval
                effective_interval = interval / (1 + behavior_adj)
            else:
                effective_interval = interval

            result = {
                "item":               name,
                "label":              name.replace("_", " ").title(),
                "current_odo_km":     round(current_odo_km, 1),
                "current_odo_mi":     round(current_mi, 1),
                "interval_mi":        round(interval * 0.621, 0),
                "behavior_multiplier":round(1 + behavior_adj, 2),
                "effective_interval_mi": round(effective_interval * 0.621, 0),
                "wear_score":         item.wear_score,
            }

            if last_odo:
                km_since   = current_odo_km - last_odo
                km_remain  = effective_interval - km_since
                pct_used   = km_since / effective_interval

                result.update({
                    "last_service_odo_mi":  round(last_odo * 0.621, 0),
                    "last_service_date":    item.last_service_date,
                    "mi_since_service":     round(km_since * 0.621, 1),
                    "mi_remaining":         round(km_remain * 0.621, 1),
                    "pct_interval_used":    round(pct_used * 100, 1),
                    "confirmed_by_user":    item.confirmed_by_user,
                    "notes":                item.notes,
                })

                if pct_used >= 1.0:
                    result["status"] = "overdue"
                elif pct_used >= 0.85:
                    result["status"] = "due_soon"
                elif pct_used >= 0.65:
                    result["status"] = "monitor"
                else:
                    result["status"] = "ok"

                # Sensor-based override for air filter and spark plugs
                if name == "AIR_FILTER" and item.wear_score > 0.5:
                    result["status"] = "due_soon"
                    result["sensor_flag"] = f"MAF efficiency drift {item.wear_score:.0%} — filter may be clogged"
                if name == "SPARK_PLUGS" and item.wear_score > 0.4:
                    result["status"] = "monitor"
                    result["sensor_flag"] = f"Idle jitter drift {item.wear_score:.0%} — plugs degrading"
            else:
                result["status"]  = "no_data"
                result["message"] = f"No service recorded. Use --set {name} --odometer <km>"

            result["icon"] = STATUS_COLORS.get(result["status"], "❓")
            results.append(result)

        # Sort by urgency
        order = {"overdue": 0, "due_soon": 1, "monitor": 2, "ok": 3, "no_data": 4}
        results.sort(key=lambda x: order.get(x["status"], 5))
        return results

    def driving_report(self) -> dict:
        """Summary of driving behavior and its maintenance implications."""
        if len(self.state.sessions) < 2:
            return {"message": "Need more sessions for driving behavior analysis"}
        sessions = [SessionDrivingMetrics(**s) for s in self.state.sessions]
        recent   = sessions[-min(10, len(sessions)):]
        return {
            "sessions_analyzed":        len(recent),
            "avg_stop_events_per_trip": round(np.mean([s.stop_event_count for s in recent]), 1),
            "avg_hard_stops_per_trip":  round(np.mean([s.hard_stop_count for s in recent]), 1),
            "avg_decel_rate":           round(np.mean([s.avg_decel_rate for s in recent if s.avg_decel_rate > 0]), 2),
            "brake_wear_multiplier":    brake_wear_rate(sessions),
            "air_filter_drift":         air_filter_efficiency(sessions),
            "spark_plug_health_drift":  spark_plug_health(sessions),
            "drivetrain_efficiency_drift": drivetrain_efficiency_drift(sessions),
            "driving_style":            _classify_style(recent),
        }

def _classify_style(sessions: list[SessionDrivingMetrics]) -> str:
    avg_hard = np.mean([s.hard_stop_count for s in sessions])
    avg_hwy  = np.mean([s.pct_time_above_80kmh for s in sessions])
    if avg_hard > 3:
        return "aggressive_city"
    if avg_hwy > 0.5:
        return "highway_dominant"
    if avg_hard > 1:
        return "moderate_city"
    return "gentle_mixed"

# ── Pretty printer ────────────────────────────────────────────────────────────

def print_status(status_list: list[dict]):
    print(f"\n{'═'*62}")
    print(f"  Acty Maintenance Status")
    print(f"{'═'*62}")
    for item in status_list:
        icon  = item["icon"]
        label = item["label"]
        s     = item["status"]
        if s == "no_data":
            print(f"  {icon}  {label:<22}  No service date recorded")
            continue
        pct   = item.get("pct_interval_used", 0)
        mi_r  = item.get("mi_remaining", 0)
        since = item.get("mi_since_service", 0)
        bx    = item.get("behavior_multiplier", 1.0)
        flag  = item.get("sensor_flag", "")
        bx_str = f"  [drive adj ×{bx:.2f}]" if bx != 1.0 else ""
        print(f"  {icon}  {label:<22}  {pct:5.1f}% used  {mi_r:+6.0f} mi remaining{bx_str}")
        if flag:
            print(f"       ⚡ {flag}")
    print(f"{'═'*62}\n")

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Acty unified maintenance tracker")
    parser.add_argument("--csv",          help="Ingest a session CSV")
    parser.add_argument("--status",       action="store_true", help="Show maintenance status")
    parser.add_argument("--driving",      action="store_true", help="Show driving behavior report")
    parser.add_argument("--set",          metavar="ITEM", help="Record a service (e.g. BRAKE_PADS)")
    parser.add_argument("--odometer",     type=float, metavar="KM", help="Odometer at service (km)")
    parser.add_argument("--odometer-mi",  type=float, metavar="MI", help="Odometer at service (miles)")
    parser.add_argument("--set-interval", metavar="ITEM", help="Set interval for item")
    parser.add_argument("--miles",        type=float, help="Interval in miles")
    parser.add_argument("--history",      default=str(HISTORY_PATH))
    parser.add_argument("--reset",        action="store_true")
    args = parser.parse_args()

    tracker = MaintenanceTracker(history_path=args.history)

    if args.reset:
        tracker.state = MaintenanceState()
        tracker._ensure_items()
        print("[MAINT] History cleared.")
        return

    if args.set:
        odo = args.odometer or (args.odometer_mi * 1.60934 if args.odometer_mi else None)
        if not odo:
            print("[ERROR] Provide --odometer (km) or --odometer-mi (miles)")
            sys.exit(1)
        tracker.record_service(args.set, odo)

    if args.set_interval and args.miles:
        tracker.set_interval(args.set_interval, args.miles)

    if args.csv:
        path = Path(args.csv)
        if not path.exists():
            print(f"[ERROR] File not found: {path}")
            sys.exit(1)
        df = pd.read_csv(path, parse_dates=["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        tracker.ingest_session(df, path.stem)

    if args.driving:
        report = tracker.driving_report()
        print("\n── Driving Behavior ─────────────────────────────────────")
        for k, v in report.items():
            print(f"   {k}: {v}")
        print("─────────────────────────────────────────────────────────\n")

    if args.status or args.csv or not any([args.set, args.set_interval, args.reset]):
        status = tracker.status()
        if status:
            print_status(status)
        else:
            print("[MAINT] No data yet. Ingest a CSV first with --csv.")

if __name__ == "__main__":
    main()
