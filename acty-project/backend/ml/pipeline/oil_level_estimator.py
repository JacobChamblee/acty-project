#!/usr/bin/env python3
"""
oil_level_estimator.py
----------------------
Acty ML Pipeline — Oil Level Estimator

Estimates current oil level as a percentage of capacity after a known
oil change, using a consumption model corrected by thermal drift signals
from OBD-II telemetry.

No OBD-II PID directly reports oil level. This module combines:
  1. Odometer-based consumption math (seeded at confirmed oil change)
  2. ENGINE_OIL_TEMP / ENGINE_LOAD ratio drift (thermal confirmation)
  3. Driving style adjustments (high RPM, sustained load, heat events)

Output is always a probabilistic range (low%, high%) with a confidence
score — never a false-precision single number.

Integration with oil_change_detector.py:
  - Reads last confirmed change odometer as seed point
  - Resets automatically when oil_change_detector fires a new event

Pipeline position:
    ingest.py → features.py → signal.py → rules.py → trends.py
                                                           ↓
                                           oil_change_detector.py
                                                           ↓
                                           oil_level_estimator.py ← here
                                                           ↓
                                                    llm_report.py

Usage:
    python3 oil_level_estimator.py --csv acty_obd_20260313_161517.csv
    python3 oil_level_estimator.py --status
    python3 oil_level_estimator.py --set-change-odometer-mi 28487
    python3 oil_level_estimator.py --set-oil-capacity-qt 5.7
    python3 oil_level_estimator.py --set-interval-miles 5000
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
HISTORY_PATH      = Path("data/oil_level_history.json")
OIL_CHANGE_HISTORY = Path("data/oil_change_history.json")   # from oil_change_detector.py

# ── FA24 (GR86) defaults ──────────────────────────────────────────────────────
# Toyota spec: 5.7 qt with filter change
# Normal consumption: 0.3–0.7 qt / 1,000 mi
# Toyota acceptable limit: 1.0 qt / 1,000 mi
FA24_OIL_CAPACITY_QT   = 5.7
FA24_BASE_CONSUMPTION  = 0.5     # qt / 1,000 mi midpoint of normal range
FA24_CONSUMPTION_MIN   = 0.3     # qt / 1,000 mi best case
FA24_CONSUMPTION_MAX   = 1.0     # qt / 1,000 mi Toyota acceptable limit

# Thermal drift thresholds
# oil_temp / engine_load ratio rising >8% from baseline = elevated consumption signal
THERMAL_DRIFT_WARN     = 0.06    # 6% rise in oil_temp/load ratio → mild flag
THERMAL_DRIFT_CRIT     = 0.12    # 12% rise → significant consumption concern

# Consumption adjustment multipliers from driving behavior
HIGH_RPM_THRESHOLD     = 4000   # rpm — sustained above this increases consumption
HIGH_LOAD_THRESHOLD    = 70     # % — sustained engine load increasing blowby
HIGH_TEMP_THRESHOLD    = 100    # °C oil temp — high temp degrades oil faster

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class SessionOilMetrics:
    """Per-session metrics relevant to oil level estimation."""
    session_id:               str
    timestamp:                str
    odometer_km:              float
    trip_km:                  float

    # Thermal signal
    oil_temp_load_ratio:      Optional[float] = None   # ENGINE_OIL_TEMP / ENGINE_LOAD mean
    oil_temp_max:             float = 0.0
    oil_temp_mean:            float = 0.0

    # Consumption risk factors
    pct_time_above_4k_rpm:    float = 0.0
    pct_time_high_load:       float = 0.0
    pct_time_oil_hot:         float = 0.0   # oil temp > threshold

    # Computed consumption adjustment for this session
    consumption_multiplier:   float = 1.0   # 1.0 = normal, >1.0 = elevated

@dataclass
class OilLevelState:
    """Persistent state for the oil level estimator."""
    sessions:                 list  = field(default_factory=list)

    # Seed point — set from oil_change_detector or manually
    last_change_odometer_km:  Optional[float] = None
    last_change_date:         Optional[str]   = None

    # Vehicle config
    oil_capacity_qt:          float = FA24_OIL_CAPACITY_QT
    base_consumption_qt_per_1kmi: float = FA24_BASE_CONSUMPTION
    interval_km:              float = 8046.7   # 5,000 mi default

    # Thermal baseline (established from first N sessions after change)
    thermal_baseline_ratio:   Optional[float] = None
    thermal_baseline_sessions: int = 0

    # Current estimate
    estimated_level_low_pct:  float = 100.0
    estimated_level_high_pct: float = 100.0
    estimated_qt_consumed:    float = 0.0
    thermal_drift_score:      float = 0.0    # 0–1
    consumption_flag:         bool  = False
    confidence:               float = 0.0

# ── Extraction ────────────────────────────────────────────────────────────────

def extract_session_metrics(df: pd.DataFrame, session_id: str) -> SessionOilMetrics:
    """Extract oil-consumption-relevant metrics from a session DataFrame."""
    odo_series = df["ODOMETER"].dropna() if "ODOMETER" in df.columns else pd.Series([0])
    odo_km     = float(odo_series.iloc[-1]) if not odo_series.empty else 0.0
    odo_start  = float(odo_series.iloc[0])  if not odo_series.empty else 0.0
    trip_km    = odo_km - odo_start

    # Thermal signal: oil_temp / engine_load ratio at moving, warmed conditions
    oil_temp_load_ratio = None
    oil_temp_max = oil_temp_mean = 0.0

    if "ENGINE_OIL_TEMP" in df.columns and "ENGINE_LOAD" in df.columns:
        # Only use samples where engine is warmed and under real load
        warm_mask = (
            (df["ENGINE_OIL_TEMP"] > 70) &
            (df["ENGINE_LOAD"] > 10) &
            (df["SPEED"] > 5 if "SPEED" in df.columns else True)
        )
        warm = df[warm_mask]
        if len(warm) > 10:
            ratio_series = warm["ENGINE_OIL_TEMP"] / warm["ENGINE_LOAD"].replace(0, np.nan)
            oil_temp_load_ratio = float(ratio_series.mean())

        oil_temp_max  = float(df["ENGINE_OIL_TEMP"].max())
        oil_temp_mean = float(df["ENGINE_OIL_TEMP"].mean())

    # Consumption risk: high RPM time
    pct_high_rpm = 0.0
    if "RPM" in df.columns:
        pct_high_rpm = float((df["RPM"] > HIGH_RPM_THRESHOLD).mean())

    # Consumption risk: high load time
    pct_high_load = 0.0
    if "ENGINE_LOAD" in df.columns:
        pct_high_load = float((df["ENGINE_LOAD"] > HIGH_LOAD_THRESHOLD).mean())

    # Consumption risk: high oil temp time
    pct_oil_hot = 0.0
    if "ENGINE_OIL_TEMP" in df.columns:
        pct_oil_hot = float((df["ENGINE_OIL_TEMP"] > HIGH_TEMP_THRESHOLD).mean())

    # Compute session consumption multiplier
    multiplier = _compute_consumption_multiplier(pct_high_rpm, pct_high_load, pct_oil_hot)

    return SessionOilMetrics(
        session_id              = session_id,
        timestamp               = str(df["timestamp"].iloc[0]) if "timestamp" in df.columns else datetime.now().isoformat(),
        odometer_km             = odo_km,
        trip_km                 = round(trip_km, 2),
        oil_temp_load_ratio     = round(oil_temp_load_ratio, 4) if oil_temp_load_ratio else None,
        oil_temp_max            = round(oil_temp_max, 1),
        oil_temp_mean           = round(oil_temp_mean, 1),
        pct_time_above_4k_rpm   = round(pct_high_rpm, 4),
        pct_time_high_load      = round(pct_high_load, 4),
        pct_time_oil_hot        = round(pct_oil_hot, 4),
        consumption_multiplier  = round(multiplier, 3),
    )

def _compute_consumption_multiplier(pct_high_rpm: float, pct_high_load: float,
                                     pct_oil_hot: float) -> float:
    """
    Returns a consumption rate multiplier based on driving harshness.
    1.0 = normal FA24 consumption (0.5 qt/1k mi midpoint)
    1.5 = moderate tracking / spirited driving
    2.0+ = extended high-RPM or high-load operation
    """
    mult = 1.0
    mult += pct_high_rpm  * 1.5   # each 10% time above 4k RPM adds 0.15x
    mult += pct_high_load * 0.8   # sustained high load adds blowby
    mult += pct_oil_hot   * 0.5   # running hot degrades oil viscosity faster
    return min(mult, 3.0)

# ── Thermal drift analysis ────────────────────────────────────────────────────

def compute_thermal_drift(sessions: list[SessionOilMetrics],
                           baseline_ratio: Optional[float]) -> tuple[float, bool]:
    """
    Compare recent oil_temp/load ratio to baseline.
    Returns (drift_score 0-1, consumption_flag bool).
    """
    if baseline_ratio is None or baseline_ratio == 0:
        return 0.0, False

    recent_ratios = [
        s.oil_temp_load_ratio for s in sessions[-5:]
        if s.oil_temp_load_ratio is not None
    ]
    if not recent_ratios:
        return 0.0, False

    recent_avg = float(np.mean(recent_ratios))
    drift      = (recent_avg - baseline_ratio) / baseline_ratio

    # Normalize to 0–1 score
    score = max(0.0, min(1.0, drift / THERMAL_DRIFT_CRIT))
    flag  = drift >= THERMAL_DRIFT_WARN

    return round(score, 3), flag

# ── Level estimation ──────────────────────────────────────────────────────────

def estimate_level(
    current_odo_km:        float,
    last_change_odo_km:    float,
    oil_capacity_qt:       float,
    base_consumption:      float,   # qt / 1,000 mi
    avg_multiplier:        float,   # from session history
    thermal_drift_score:   float,   # 0–1
    confidence:            float,
) -> tuple[float, float, float, float]:
    """
    Returns (level_low_pct, level_high_pct, qt_consumed_est, confidence).

    Uses a range model:
      - Low estimate: aggressive consumption (base * avg_multiplier * 1.2)
      - High estimate: conservative consumption (FA24 min rate)
      - Thermal drift pushes both estimates downward
    """
    km_since   = current_odo_km - last_change_odo_km
    mi_since   = km_since * 0.621

    # Consumed estimates in quarts
    # Conservative (best case): minimum published consumption rate
    consumed_low_qt = (mi_since / 1000) * FA24_CONSUMPTION_MIN

    # Aggressive (worst case): adjusted rate, incorporating driving style
    adjusted_rate   = base_consumption * avg_multiplier
    consumed_high_qt = (mi_since / 1000) * min(adjusted_rate, FA24_CONSUMPTION_MAX)

    # Thermal drift correction: if thermal signal is elevated,
    # shift estimates downward by up to 15%
    thermal_correction = thermal_drift_score * 0.15
    consumed_low_qt  *= (1 + thermal_correction)
    consumed_high_qt *= (1 + thermal_correction)

    # Convert to % of capacity
    # Level high = less consumption (conservative estimate)
    # Level low  = more consumption (aggressive estimate)
    level_high_pct = max(0.0, (oil_capacity_qt - consumed_low_qt)  / oil_capacity_qt * 100)
    level_low_pct  = max(0.0, (oil_capacity_qt - consumed_high_qt) / oil_capacity_qt * 100)

    # Central estimate for reporting
    consumed_est_qt = (consumed_low_qt + consumed_high_qt) / 2

    # Round to nearest 5% band for honest communication
    level_high_pct = min(100.0, round(level_high_pct / 5) * 5)
    level_low_pct  = max(0.0,   round(level_low_pct  / 5) * 5)

    return level_low_pct, level_high_pct, round(consumed_est_qt, 2), round(confidence, 2)

def _confidence_score(sessions_since_change: int, has_thermal: bool,
                       thermal_sessions: int) -> float:
    """Confidence rises with more sessions and thermal signal availability."""
    base = min(0.5, sessions_since_change * 0.08)   # up to 0.5 from session count
    if has_thermal and thermal_sessions >= 3:
        base += 0.35
    elif has_thermal:
        base += 0.15
    return min(0.95, base)

# ── Recommendation ────────────────────────────────────────────────────────────

def _recommendation(level_low: float, level_high: float,
                     consumption_flag: bool, thermal_drift: float,
                     qt_consumed: float, oil_capacity: float) -> str:
    level_mid = (level_low + level_high) / 2

    if level_mid < 50:
        return (f"Estimated oil level is low (~{level_low:.0f}–{level_high:.0f}%). "
                f"Check dipstick before next drive — approximately {qt_consumed:.1f} qt consumed.")
    if level_mid < 65:
        return (f"Estimated oil level approaching half capacity (~{level_low:.0f}–{level_high:.0f}%). "
                f"Check dipstick soon, especially before any long drives.")
    if consumption_flag:
        return (f"Oil level estimated at ~{level_low:.0f}–{level_high:.0f}% but thermal drift "
                f"suggests consumption may be elevated. Check dipstick to confirm.")
    if level_mid < 80:
        return (f"Oil level estimated at ~{level_low:.0f}–{level_high:.0f}% "
                f"({qt_consumed:.1f} qt consumed). Normal range — check dipstick at next fill-up.")
    return (f"Oil level estimated at ~{level_low:.0f}–{level_high:.0f}% "
            f"({qt_consumed:.1f} qt consumed). Normal consumption for mileage accumulated.")

# ── Main estimator class ──────────────────────────────────────────────────────

class OilLevelEstimator:
    def __init__(self, history_path: Path = HISTORY_PATH):
        self.history_path = Path(history_path)
        self.state = self._load_state()
        self._sync_from_oil_change_detector()

    def _load_state(self) -> OilLevelState:
        if self.history_path.exists() and self.history_path.stat().st_size > 0:
            with open(self.history_path) as f:
                data = json.load(f)
            s = OilLevelState()
            for k, v in data.items():
                if hasattr(s, k):
                    setattr(s, k, v)
            return s
        return OilLevelState()

    def _save_state(self):
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_path, "w") as f:
            json.dump(asdict(self.state), f, indent=2, default=str)

    def _sync_from_oil_change_detector(self):
        """Pull last confirmed oil change odometer from oil_change_detector.py's history."""
        if not OIL_CHANGE_HISTORY.exists():
            return
        try:
            with open(OIL_CHANGE_HISTORY) as f:
                data = json.load(f)
            detector_odo = data.get("last_change_odometer")
            detector_date = data.get("last_change_date")
            if detector_odo and detector_odo != self.state.last_change_odometer_km:
                print(f"[OIL-LVL] Synced oil change from detector: "
                      f"{detector_odo:.1f} km ({detector_odo*0.621:.0f} mi)")
                self.state.last_change_odometer_km = detector_odo
                self.state.last_change_date = detector_date
                # Reset thermal baseline on new change
                self.state.thermal_baseline_ratio = None
                self.state.thermal_baseline_sessions = 0
                self._save_state()
        except (json.JSONDecodeError, KeyError):
            pass

    def set_change_odometer(self, odometer_km: float, date: Optional[str] = None):
        """Manually set the oil change seed point."""
        self.state.last_change_odometer_km = odometer_km
        self.state.last_change_date = date or datetime.now().isoformat()
        self.state.thermal_baseline_ratio = None
        self.state.thermal_baseline_sessions = 0
        # Clear sessions that predate the change
        self.state.sessions = [
            s for s in self.state.sessions
            if s["odometer_km"] > odometer_km
        ]
        self._save_state()
        print(f"[OIL-LVL] Seed set: {odometer_km:.1f} km ({odometer_km*0.621:.0f} mi)")

    def ingest_session(self, df: pd.DataFrame, session_id: str):
        """Extract metrics and update running estimate."""
        existing = [s["session_id"] for s in self.state.sessions]
        if session_id in existing:
            print(f"[OIL-LVL] {session_id} already ingested — skipping")
            return

        metrics = extract_session_metrics(df, session_id)
        self.state.sessions.append(asdict(metrics))

        # Build thermal baseline from first 3 sessions after change
        if (self.state.thermal_baseline_ratio is None and
                metrics.oil_temp_load_ratio is not None and
                self.state.thermal_baseline_sessions < 3):
            ratios = [
                s["oil_temp_load_ratio"] for s in self.state.sessions
                if s.get("oil_temp_load_ratio") is not None
            ]
            if len(ratios) >= 3:
                self.state.thermal_baseline_ratio = float(np.mean(ratios[:3]))
                self.state.thermal_baseline_sessions = 3
                print(f"[OIL-LVL] Thermal baseline established: "
                      f"{self.state.thermal_baseline_ratio:.4f}")
            else:
                self.state.thermal_baseline_sessions = len(ratios)

        self._update_estimate(metrics.odometer_km)
        self._save_state()

        lvl_lo = self.state.estimated_level_low_pct
        lvl_hi = self.state.estimated_level_high_pct
        flag   = "⚠️" if self.state.consumption_flag else "✅"
        print(f"[OIL-LVL] {session_id}  "
              f"level={lvl_lo:.0f}–{lvl_hi:.0f}%  "
              f"consumed≈{self.state.estimated_qt_consumed:.2f}qt  "
              f"thermal_drift={self.state.thermal_drift_score:.2f}  {flag}")

    def _update_estimate(self, current_odo_km: float):
        """Recalculate level estimate with latest data."""
        if not self.state.last_change_odometer_km:
            return

        sessions_obj = [SessionOilMetrics(**s) for s in self.state.sessions]
        # Only sessions after the last change
        post_change = [
            s for s in sessions_obj
            if s.odometer_km >= self.state.last_change_odometer_km
        ]
        if not post_change:
            return

        # Average consumption multiplier (weighted toward recent)
        multipliers = [s.consumption_multiplier for s in post_change]
        weights = np.linspace(0.5, 1.0, len(multipliers))
        avg_mult = float(np.average(multipliers, weights=weights))

        # Thermal drift
        drift_score, consumption_flag = compute_thermal_drift(
            post_change, self.state.thermal_baseline_ratio
        )

        # Confidence
        conf = _confidence_score(
            sessions_since_change = len(post_change),
            has_thermal           = self.state.thermal_baseline_ratio is not None,
            thermal_sessions      = self.state.thermal_baseline_sessions,
        )

        lo, hi, consumed, conf = estimate_level(
            current_odo_km      = current_odo_km,
            last_change_odo_km  = self.state.last_change_odometer_km,
            oil_capacity_qt     = self.state.oil_capacity_qt,
            base_consumption    = self.state.base_consumption_qt_per_1kmi,
            avg_multiplier      = avg_mult,
            thermal_drift_score = drift_score,
            confidence          = conf,
        )

        self.state.estimated_level_low_pct  = lo
        self.state.estimated_level_high_pct = hi
        self.state.estimated_qt_consumed    = consumed
        self.state.thermal_drift_score      = drift_score
        self.state.consumption_flag         = consumption_flag
        self.state.confidence               = conf

    def status(self) -> dict:
        """Return current oil level estimate and recommendation."""
        if not self.state.last_change_odometer_km:
            return {
                "status":  "no_seed",
                "message": "No oil change date set. Use --set-change-odometer-mi <miles>",
            }

        lo   = self.state.estimated_level_low_pct
        hi   = self.state.estimated_level_high_pct
        mid  = (lo + hi) / 2
        conf = self.state.confidence

        # Status band
        if mid < 50:   status = "low"
        elif mid < 65: status = "monitor"
        elif mid < 80: status = "ok"
        else:          status = "good"

        icons = {"good": "✅", "ok": "✅", "monitor": "👀", "low": "🔴"}

        sessions_since = [
            s for s in self.state.sessions
            if s["odometer_km"] >= (self.state.last_change_odometer_km or 0)
        ]

        return {
            "status":                  status,
            "icon":                    icons[status],
            "level_low_pct":           lo,
            "level_high_pct":          hi,
            "level_display":           f"~{lo:.0f}–{hi:.0f}%",
            "qt_consumed_est":         self.state.estimated_qt_consumed,
            "oil_capacity_qt":         self.state.oil_capacity_qt,
            "qt_remaining_est":        round(self.state.oil_capacity_qt - self.state.estimated_qt_consumed, 2),
            "thermal_drift_score":     self.state.thermal_drift_score,
            "consumption_flag":        self.state.consumption_flag,
            "confidence":              f"{conf:.0%}",
            "sessions_since_change":   len(sessions_since),
            "last_change_odometer_mi": round((self.state.last_change_odometer_km or 0) * 0.621, 0),
            "last_change_date":        self.state.last_change_date,
            "recommendation":          _recommendation(
                lo, hi,
                self.state.consumption_flag,
                self.state.thermal_drift_score,
                self.state.estimated_qt_consumed,
                self.state.oil_capacity_qt,
            ),
        }

# ── Pipeline integration helper ───────────────────────────────────────────────

def get_report_context(estimator: "OilLevelEstimator") -> dict:
    """Clean dict for injection into llm_report.py prompt context."""
    s = estimator.status()
    return {
        "oil_level_display":     s.get("level_display", "unknown"),
        "oil_level_status":      s.get("status", "unknown"),
        "oil_qt_consumed":       s.get("qt_consumed_est"),
        "oil_qt_remaining":      s.get("qt_remaining_est"),
        "oil_consumption_flag":  s.get("consumption_flag", False),
        "oil_level_confidence":  s.get("confidence", "0%"),
        "oil_level_recommend":   s.get("recommendation"),
    }

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Acty oil level estimator")
    parser.add_argument("--csv",                      help="Ingest a session CSV")
    parser.add_argument("--status",  action="store_true")
    parser.add_argument("--history", default=str(HISTORY_PATH))
    parser.add_argument("--set-change-odometer-mi",   type=float, metavar="MI",
                        help="Set last oil change odometer in miles")
    parser.add_argument("--set-change-odometer-km",   type=float, metavar="KM")
    parser.add_argument("--set-oil-capacity-qt",      type=float, metavar="QT",
                        help="Override oil capacity (default: 5.7 qt for FA24/GR86)")
    parser.add_argument("--set-interval-miles",       type=float, metavar="MI")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    est = OilLevelEstimator(history_path=args.history)

    if args.reset:
        est.state = OilLevelState()
        est._save_state()
        print("[OIL-LVL] History cleared.")
        return

    if args.set_change_odometer_mi:
        est.set_change_odometer(args.set_change_odometer_mi * 1.60934)
    if args.set_change_odometer_km:
        est.set_change_odometer(args.set_change_odometer_km)
    if args.set_oil_capacity_qt:
        est.state.oil_capacity_qt = args.set_oil_capacity_qt
        est._save_state()
        print(f"[OIL-LVL] Oil capacity set to {args.set_oil_capacity_qt} qt")
    if args.set_interval_miles:
        est.state.interval_km = args.set_interval_miles * 1.60934
        est._save_state()

    if args.csv:
        path = Path(args.csv)
        if not path.exists():
            print(f"[ERROR] {path} not found")
            sys.exit(1)
        df = pd.read_csv(path, parse_dates=["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        est.ingest_session(df, path.stem)

    if args.status or args.csv or not any([
        args.set_change_odometer_mi, args.set_change_odometer_km,
        args.set_oil_capacity_qt, args.set_interval_miles, args.reset
    ]):
        s = est.status()
        if s.get("status") == "no_seed":
            print(f"\n[OIL-LVL] {s['message']}\n")
            return
        print(f"\n── Oil Level Estimate ───────────────────────────────────")
        print(f"   Level:        {s['icon']}  {s['level_display']}")
        print(f"   Qt consumed:  ~{s['qt_consumed_est']:.2f} qt  "
              f"({s['qt_remaining_est']:.2f} qt remaining of {s['oil_capacity_qt']} qt)")
        print(f"   Thermal drift: {s['thermal_drift_score']:.2f}  "
              f"consumption_flag={'YES ⚠️' if s['consumption_flag'] else 'no'}")
        print(f"   Confidence:   {s['confidence']}  "
              f"({s['sessions_since_change']} sessions since change)")
        print(f"   Last change:  {s['last_change_odometer_mi']:.0f} mi  "
              f"({s['last_change_date'] or 'date unknown'})")
        print(f"\n   → {s['recommendation']}")
        print(f"────────────────────────────────────────────────────────\n")

if __name__ == "__main__":
    main()
