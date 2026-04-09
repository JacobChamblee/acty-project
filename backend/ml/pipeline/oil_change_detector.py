#!/usr/bin/env python3
"""
oil_change_detector.py
----------------------
Acty ML Pipeline — Stage: Maintenance Event Detection

Detects oil change events from OBD-II telemetry without any manual
input from the driver. Compares multi-signal patterns across consecutive
drive sessions to identify the correlated improvements that follow a
fresh oil change.

No single PID proves an oil change. This module looks for 3+ signals
moving in the correct direction simultaneously on the same session,
cross-referenced against odometer to produce a confidence-weighted
detection.

Pipeline position:
    ingest.py → features.py → signal.py → rules.py → trends.py
                                                           ↓
                                              oil_change_detector.py  ← here
                                                           ↓
                                                    llm_report.py

Usage as library:
    from oil_change_detector import OilChangeDetector
    detector = OilChangeDetector(history_path="data/session_history.json")
    detector.ingest_session(df, session_id="acty_obd_20260313_071256")
    result = detector.evaluate()
    print(result)

Usage as CLI:
    python3 oil_change_detector.py --csv acty_obd_20260313_071256.csv
    python3 oil_change_detector.py --history data/session_history.json --status
    python3 oil_change_detector.py --reset-baseline   # call after confirmed change
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

HISTORY_PATH     = Path("data/oil_change_history.json")
MIN_SESSIONS     = 2      # need at least this many sessions to compare
DETECTION_THRESHOLD = 3   # signals that must improve to flag a probable change
CONFIDENCE_THRESHOLDS = {
    "probable":  3,   # 3 signals improved → probable change
    "likely":    4,   # 4 signals improved → likely change
    "confirmed": 5,   # 5+ signals improved → high confidence
}

# ── Signal definitions ────────────────────────────────────────────────────────
# Each signal: (pid, metric_fn, direction, threshold, weight, description)
#   direction: "down" = improvement is a decrease, "up" = improvement is increase
#   threshold: minimum delta to count as meaningful change
#   weight: contribution to confidence score (1–3)

SIGNALS = [
    {
        "name":        "oil_temp_peak",
        "pid":         "ENGINE_OIL_TEMP",
        "metric":      "max",
        "direction":   "down",
        "threshold":   2.0,      # °C — fresh oil peaks lower under same load
        "weight":      2,
        "description": "Peak oil temperature drop (fresh oil = better heat transfer)",
        "normalize_by": "ENGINE_LOAD",  # only compare at similar load levels
    },
    {
        "name":        "idle_load",
        "pid":         "ENGINE_LOAD",
        "metric":      "idle_mean",
        "direction":   "down",
        "threshold":   1.5,      # % — less friction at idle
        "weight":      2,
        "description": "Idle engine load reduction (less internal friction)",
    },
    {
        "name":        "idle_rpm_stability",
        "pid":         "RPM",
        "metric":      "idle_std",
        "direction":   "down",
        "threshold":   20.0,     # RPM — smoother idle
        "weight":      1,
        "description": "Idle RPM stability improvement (smoother operation)",
    },
    {
        "name":        "cold_start_rpm",
        "pid":         "RPM",
        "metric":      "cold_start_peak",
        "direction":   "down",
        "threshold":   50.0,     # RPM — lower cold start idle with fresh oil
        "weight":      2,
        "description": "Cold start RPM reduction (less cold viscosity friction)",
    },
    {
        "name":        "oil_temp_warmup_rate",
        "pid":         "ENGINE_OIL_TEMP",
        "metric":      "warmup_rate",
        "direction":   "up",
        "threshold":   0.3,      # °C/min — fresh oil warms up faster
        "weight":      1,
        "description": "Oil warmup rate increase (fresh oil conducts heat better)",
    },
    {
        "name":        "maf_at_idle",
        "pid":         "MAF",
        "metric":      "idle_mean",
        "direction":   "down",
        "threshold":   0.15,     # g/s — less air needed to maintain idle
        "weight":      1,
        "description": "MAF at idle reduction (less friction = less fuel needed at idle)",
    },
    {
        "name":        "coolant_warmup_time",
        "pid":         "COOLANT_TEMP",
        "metric":      "time_to_80c",
        "direction":   "down",
        "threshold":   15.0,     # seconds — fresh oil sheds heat to coolant faster
        "weight":      1,
        "description": "Coolant warmup speed (fresh oil transfers heat more efficiently)",
    },
]

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class SessionMetrics:
    session_id:           str
    timestamp:            str
    odometer_km:          float
    ambient_temp_c:       float
    avg_load:             float

    # Signal metrics
    oil_temp_peak_c:      Optional[float] = None
    idle_load_pct:        Optional[float] = None
    idle_rpm_std:         Optional[float] = None
    cold_start_rpm:       Optional[float] = None
    oil_warmup_rate:      Optional[float] = None   # °C/min in first 5 min
    maf_at_idle:          Optional[float] = None
    time_to_80c_s:        Optional[float] = None

    # Context
    has_cold_start:       bool = False             # session started cold (<40°C coolant)
    drive_type:           str = "unknown"          # "city", "highway", "mixed"

@dataclass
class OilChangeEvent:
    detected_session_id:  str
    detected_at:          str
    odometer_km:          float
    confidence:           str                      # "probable", "likely", "confirmed"
    confidence_score:     float                    # 0–1
    signals_triggered:    list = field(default_factory=list)
    confirmed_by_user:    bool = False
    confirmed_at:         Optional[str] = None

@dataclass
class MaintenanceState:
    last_change_event:     Optional[OilChangeEvent] = None
    last_change_odometer:  Optional[float] = None  # km — manually set or auto-detected
    last_change_date:      Optional[str] = None
    interval_km:           float = 8046.7          # 5,000 miles default
    sessions:              list = field(default_factory=list)
    pending_detection:     Optional[dict] = None

# ── Metric extractors ─────────────────────────────────────────────────────────

def extract_metrics(df: pd.DataFrame, session_id: str) -> SessionMetrics:
    """Extract all signal metrics from a session DataFrame."""
    idle   = df[df["SPEED"] <= 2].copy()
    moving = df[df["SPEED"] > 2].copy()

    # Odometer
    odo = df["ODOMETER"].dropna()
    odo_km = float(odo.iloc[-1]) if not odo.empty else 0.0

    # Ambient temp
    ambient = float(df["AMBIENT_TEMP"].mean()) if "AMBIENT_TEMP" in df.columns else 20.0

    # Drive type
    max_speed = df["SPEED"].max() if "SPEED" in df.columns else 0
    pct_moving = len(moving) / max(len(df), 1)
    if max_speed > 90 and pct_moving > 0.7:
        drive_type = "highway"
    elif max_speed < 60 or pct_moving < 0.5:
        drive_type = "city"
    else:
        drive_type = "mixed"

    # Cold start detection
    coolant_start = float(df["COOLANT_TEMP"].iloc[0]) if "COOLANT_TEMP" in df.columns else 90.0
    has_cold_start = coolant_start < 40.0

    # ── Oil temp peak ──────────────────────────────────────────────────────────
    oil_temp_peak = None
    if "ENGINE_OIL_TEMP" in df.columns and df["ENGINE_OIL_TEMP"].notna().any():
        # Use 95th percentile to avoid single-sample spikes
        oil_temp_peak = float(df["ENGINE_OIL_TEMP"].quantile(0.95))

    # ── Idle load ──────────────────────────────────────────────────────────────
    idle_load = None
    if "ENGINE_LOAD" in df.columns and len(idle) > 10:
        # Exclude first 2 minutes (warmup affects idle load)
        settled_idle = idle[idle["elapsed_s"] > 120] if "elapsed_s" in idle.columns else idle
        if len(settled_idle) > 5:
            idle_load = float(settled_idle["ENGINE_LOAD"].mean())

    # ── Idle RPM stability ─────────────────────────────────────────────────────
    idle_rpm_std = None
    if "RPM" in df.columns and len(idle) > 10:
        settled_idle = idle[idle["elapsed_s"] > 120] if "elapsed_s" in idle.columns else idle
        if len(settled_idle) > 5:
            idle_rpm_std = float(settled_idle["RPM"].std())

    # ── Cold start RPM peak ───────────────────────────────────────────────────
    cold_start_rpm = None
    if "RPM" in df.columns and has_cold_start and "elapsed_s" in df.columns:
        first_90s = df[df["elapsed_s"] <= 90]
        if not first_90s.empty:
            cold_start_rpm = float(first_90s["RPM"].quantile(0.85))

    # ── Oil warmup rate ────────────────────────────────────────────────────────
    oil_warmup_rate = None
    if "ENGINE_OIL_TEMP" in df.columns and has_cold_start and "elapsed_s" in df.columns:
        warmup_window = df[df["elapsed_s"] <= 300]  # first 5 minutes
        if len(warmup_window) > 10:
            temp_start = float(warmup_window["ENGINE_OIL_TEMP"].iloc[0])
            temp_end   = float(warmup_window["ENGINE_OIL_TEMP"].iloc[-1])
            duration_min = float(warmup_window["elapsed_s"].iloc[-1]) / 60
            if duration_min > 0:
                oil_warmup_rate = (temp_end - temp_start) / duration_min

    # ── MAF at idle ────────────────────────────────────────────────────────────
    maf_at_idle = None
    if "MAF" in df.columns and len(idle) > 10:
        settled_idle = idle[idle["elapsed_s"] > 120] if "elapsed_s" in idle.columns else idle
        if len(settled_idle) > 5:
            maf_at_idle = float(settled_idle["MAF"].mean())

    # ── Time to 80°C coolant ──────────────────────────────────────────────────
    time_to_80c = None
    if "COOLANT_TEMP" in df.columns and has_cold_start and "elapsed_s" in df.columns:
        above_80 = df[df["COOLANT_TEMP"] >= 80]
        if not above_80.empty:
            time_to_80c = float(above_80["elapsed_s"].iloc[0])

    return SessionMetrics(
        session_id        = session_id,
        timestamp         = str(df["timestamp"].iloc[0]) if "timestamp" in df.columns else datetime.now().isoformat(),
        odometer_km       = odo_km,
        ambient_temp_c    = ambient,
        avg_load          = float(df["ENGINE_LOAD"].mean()) if "ENGINE_LOAD" in df.columns else 0.0,
        oil_temp_peak_c   = oil_temp_peak,
        idle_load_pct     = idle_load,
        idle_rpm_std      = idle_rpm_std,
        cold_start_rpm    = cold_start_rpm,
        oil_warmup_rate   = oil_warmup_rate,
        maf_at_idle       = maf_at_idle,
        time_to_80c_s     = time_to_80c,
        has_cold_start    = has_cold_start,
        drive_type        = drive_type,
    )

# ── Comparison logic ──────────────────────────────────────────────────────────

METRIC_MAP = {
    "oil_temp_peak":        ("oil_temp_peak_c",  "down"),
    "idle_load":            ("idle_load_pct",     "down"),
    "idle_rpm_stability":   ("idle_rpm_std",      "down"),
    "cold_start_rpm":       ("cold_start_rpm",    "down"),
    "oil_temp_warmup_rate": ("oil_warmup_rate",   "up"),
    "maf_at_idle":          ("maf_at_idle",       "down"),
    "coolant_warmup_time":  ("time_to_80c_s",     "down"),
}

def compare_sessions(before: SessionMetrics, after: SessionMetrics) -> dict:
    """
    Compare two sessions. Returns a dict of signal results.
    Applies temperature normalization — ambient temp affects several metrics,
    so we only flag a change if the delta exceeds ambient variation.
    """
    ambient_delta = abs(after.ambient_temp_c - before.ambient_temp_c)
    results = {}

    for sig in SIGNALS:
        name     = sig["name"]
        field_name, direction = METRIC_MAP[name]
        threshold = sig["threshold"]
        weight    = sig["weight"]

        val_before = getattr(before, field_name)
        val_after  = getattr(after, field_name)

        if val_before is None or val_after is None:
            results[name] = {"available": False, "improved": False, "delta": None, "weight": weight}
            continue

        delta = val_after - val_before

        # Temperature normalization: if ambient changed significantly,
        # require a larger delta to reduce false positives
        adjusted_threshold = threshold
        if ambient_delta > 10:
            adjusted_threshold *= 1.5

        if direction == "down":
            improved = delta < -adjusted_threshold
        else:
            improved = delta > adjusted_threshold

        results[name] = {
            "available":   True,
            "improved":    improved,
            "delta":       round(delta, 3),
            "threshold":   round(adjusted_threshold, 3),
            "weight":      weight,
            "description": sig["description"],
        }

    return results

def score_detection(signal_results: dict) -> tuple[float, str]:
    """Convert signal results into a confidence score and label."""
    total_weight  = sum(s["weight"] for s in signal_results.values() if s["available"])
    earned_weight = sum(s["weight"] for s in signal_results.values() if s.get("improved"))
    improved_count = sum(1 for s in signal_results.values() if s.get("improved"))

    if total_weight == 0:
        return 0.0, "insufficient_data"

    score = earned_weight / total_weight

    if improved_count >= CONFIDENCE_THRESHOLDS["confirmed"]:
        label = "confirmed"
    elif improved_count >= CONFIDENCE_THRESHOLDS["likely"]:
        label = "likely"
    elif improved_count >= CONFIDENCE_THRESHOLDS["probable"]:
        label = "probable"
    else:
        label = "none"

    return round(score, 3), label

# ── Main detector class ───────────────────────────────────────────────────────

class OilChangeDetector:
    def __init__(self, history_path: Path = HISTORY_PATH):
        self.history_path = Path(history_path)
        self.state = self._load_state()

    def _load_state(self) -> MaintenanceState:
        if self.history_path.exists() and self.history_path.stat().st_size > 0:
            with open(self.history_path) as f:
                data = json.load(f)
            state = MaintenanceState()
            state.sessions            = data.get("sessions", [])
            state.interval_km         = data.get("interval_km", 8046.7)
            state.last_change_odometer= data.get("last_change_odometer")
            state.last_change_date    = data.get("last_change_date")
            if data.get("last_change_event"):
                e = data["last_change_event"]
                state.last_change_event = OilChangeEvent(**{
                    **e,
                    "signals_triggered": e.get("signals_triggered", [])
                })
            return state
        return MaintenanceState()

    def _save_state(self):
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "sessions":             self.state.sessions,
            "interval_km":          self.state.interval_km,
            "last_change_odometer": self.state.last_change_odometer,
            "last_change_date":     self.state.last_change_date,
            "last_change_event":    asdict(self.state.last_change_event) if self.state.last_change_event else None,
        }
        with open(self.history_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def ingest_session(self, df: pd.DataFrame, session_id: str) -> SessionMetrics:
        """Extract metrics from a session DataFrame and store them."""
        metrics = extract_metrics(df, session_id)

        # Check for duplicate session
        existing_ids = [s["session_id"] for s in self.state.sessions]
        if session_id not in existing_ids:
            self.state.sessions.append(asdict(metrics))
            self._save_state()
            print(f"[OIL] Ingested session {session_id}  odo={metrics.odometer_km:.1f}km  "
                  f"cold_start={metrics.has_cold_start}")
        else:
            print(f"[OIL] Session {session_id} already in history — skipping")

        return metrics

    def evaluate(self, n_baseline: int = 3) -> dict:
        """
        Compare the latest session against a baseline of recent sessions.
        Returns detection result dict.
        """
        if len(self.state.sessions) < MIN_SESSIONS:
            return {
                "detection":   "insufficient_data",
                "message":     f"Need at least {MIN_SESSIONS} sessions. Have {len(self.state.sessions)}.",
                "confidence":  0.0,
            }

        sessions = self.state.sessions
        latest_raw  = sessions[-1]
        baseline_raw = sessions[max(0, len(sessions) - n_baseline - 1) : -1]

        if not baseline_raw:
            return {"detection": "insufficient_data", "message": "No baseline sessions.", "confidence": 0.0}

        # Build average baseline metrics
        latest = SessionMetrics(**latest_raw)

        # Average baseline values across n_baseline sessions
        import dataclasses
        baseline_fields = [f.name for f in dataclasses.fields(SessionMetrics)
                           if f.name not in ("session_id","timestamp","drive_type","has_cold_start")]
        baseline_avgs = {}
        for field_name in baseline_fields:
            vals = [s.get(field_name) for s in baseline_raw if s.get(field_name) is not None]
            baseline_avgs[field_name] = float(np.mean(vals)) if vals else None

        baseline = SessionMetrics(
            session_id  = "baseline_avg",
            timestamp   = baseline_raw[-1]["timestamp"],
            odometer_km = baseline_avgs.get("odometer_km") or 0,
            ambient_temp_c = baseline_avgs.get("ambient_temp_c") or 20,
            avg_load    = baseline_avgs.get("avg_load") or 0,
            **{k: baseline_avgs.get(k) for k in [
                "oil_temp_peak_c","idle_load_pct","idle_rpm_std",
                "cold_start_rpm","oil_warmup_rate","maf_at_idle","time_to_80c_s"
            ]}
        )

        signal_results = compare_sessions(baseline, latest)
        score, confidence = score_detection(signal_results)
        improved = [k for k, v in signal_results.items() if v.get("improved")]
        available = [k for k, v in signal_results.items() if v.get("available")]

        result = {
            "detection":          confidence,
            "confidence_score":   score,
            "signals_improved":   improved,
            "signals_checked":    available,
            "signal_details":     signal_results,
            "latest_session":     latest.session_id,
            "latest_odometer_km": latest.odometer_km,
            "latest_odometer_mi": round(latest.odometer_km * 0.621, 1),
        }

        # If probable or better → create event record
        if confidence in ("probable", "likely", "confirmed"):
            event = OilChangeEvent(
                detected_session_id = latest.session_id,
                detected_at         = datetime.now().isoformat(),
                odometer_km         = latest.odometer_km,
                confidence          = confidence,
                confidence_score    = score,
                signals_triggered   = improved,
            )
            self.state.last_change_event    = event
            self.state.last_change_odometer = latest.odometer_km
            self.state.last_change_date     = latest.timestamp
            self._save_state()
            result["event"] = asdict(event)
            print(f"[OIL] 🔧 Oil change event detected! confidence={confidence}  "
                  f"score={score:.2f}  signals={improved}")

        return result

    def status(self) -> dict:
        """Return current oil change status and maintenance forecast."""
        last_odo = self.state.last_change_odometer
        if not self.state.sessions:
            return {"status": "no_data"}

        current_odo = self.state.sessions[-1].get("odometer_km", 0)
        current_mi  = current_odo * 0.621

        result = {
            "current_odometer_km":   round(current_odo, 1),
            "current_odometer_mi":   round(current_mi, 1),
            "interval_km":           self.state.interval_km,
            "interval_mi":           round(self.state.interval_km * 0.621, 0),
            "sessions_logged":       len(self.state.sessions),
        }

        if last_odo:
            km_since = current_odo - last_odo
            km_remaining = self.state.interval_km - km_since
            result.update({
                "last_change_odometer_km":  round(last_odo, 1),
                "last_change_odometer_mi":  round(last_odo * 0.621, 1),
                "last_change_date":         self.state.last_change_date,
                "km_since_change":          round(km_since, 1),
                "mi_since_change":          round(km_since * 0.621, 1),
                "km_remaining":             round(km_remaining, 1),
                "mi_remaining":             round(km_remaining * 0.621, 1),
                "pct_life_used":            round(km_since / self.state.interval_km * 100, 1),
                "status":                   "overdue" if km_remaining < 0 else
                                            "due_soon" if km_remaining < 160 else
                                            "ok",
                "last_change_event":        asdict(self.state.last_change_event) if self.state.last_change_event else None,
            })
        else:
            result["status"] = "no_baseline"
            result["message"] = "No oil change detected yet. Set manually with --set-change-odometer."

        return result

    def set_manual_change(self, odometer_km: float, date: Optional[str] = None):
        """Manually record a confirmed oil change (e.g. user tells the app)."""
        self.state.last_change_odometer = odometer_km
        self.state.last_change_date     = date or datetime.now().isoformat()
        # Mark last event as user-confirmed if it exists
        if self.state.last_change_event:
            self.state.last_change_event.confirmed_by_user = True
            self.state.last_change_event.confirmed_at = datetime.now().isoformat()
        self._save_state()
        print(f"[OIL] Manual change recorded at {odometer_km:.1f} km ({odometer_km*0.621:.0f} mi)")

    def reset(self):
        """Clear all session history."""
        self.state = MaintenanceState()
        self._save_state()
        print("[OIL] History cleared.")

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Acty oil change detector")
    parser.add_argument("--csv",                   help="Ingest a session CSV and evaluate")
    parser.add_argument("--status",  action="store_true", help="Show current oil change status")
    parser.add_argument("--history", default=str(HISTORY_PATH), help="Path to history JSON")
    parser.add_argument("--set-change-odometer", type=float, metavar="KM",
                        help="Manually record an oil change at this odometer (km)")
    parser.add_argument("--set-interval-miles", type=float, metavar="MI",
                        help="Set oil change interval in miles (default: 5000)")
    parser.add_argument("--reset", action="store_true", help="Clear all history")
    args = parser.parse_args()

    detector = OilChangeDetector(history_path=args.history)

    if args.reset:
        detector.reset()
        return

    if args.set_interval_miles:
        detector.state.interval_km = args.set_interval_miles * 1.60934
        detector._save_state()
        print(f"[OIL] Interval set to {args.set_interval_miles:.0f} miles "
              f"({detector.state.interval_km:.1f} km)")

    if args.set_change_odometer:
        detector.set_manual_change(args.set_change_odometer)

    if args.csv:
        path = Path(args.csv)
        if not path.exists():
            print(f"[ERROR] File not found: {path}")
            sys.exit(1)
        df = pd.read_csv(path, parse_dates=["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        session_id = path.stem
        detector.ingest_session(df, session_id)
        result = detector.evaluate()
        print(f"\n── Oil Change Detection Result ──────────────────────────")
        print(f"   Detection:   {result['detection'].upper()}")
        print(f"   Confidence:  {result['confidence_score']:.0%}")
        print(f"   Signals:     {len(result['signals_improved'])}/{len(result['signals_checked'])} improved")
        for sig in result.get("signals_improved", []):
            d = result["signal_details"][sig]
            print(f"     ✓ {sig}: Δ{d['delta']:+.2f}")
        print(f"────────────────────────────────────────────────────────\n")

    if args.status or not any([args.csv, args.set_change_odometer, args.reset]):
        status = detector.status()
        print(f"\n── Oil Change Status ────────────────────────────────────")
        for k, v in status.items():
            if k != "last_change_event":
                print(f"   {k}: {v}")
        print(f"────────────────────────────────────────────────────────\n")

if __name__ == "__main__":
    main()
