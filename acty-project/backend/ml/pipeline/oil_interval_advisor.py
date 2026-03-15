#!/usr/bin/env python3
"""
oil_interval_advisor.py
-----------------------
Acty ML Pipeline — Severity-Weighted Oil Change Interval Advisor

Replaces fixed-mileage oil change intervals with a degradation score model
that accumulates severity points per session based on actual operating
conditions. When the score crosses a threshold, Acty recommends a change —
not because the odometer said so, but because the oil actually needs it.

Degradation factors tracked (all from existing OBD-II PIDs):
  - Thermal cycling severity    ENGINE_OIL_TEMP sustained above thresholds
  - Cold start frequency        COOLANT_TEMP at session start
  - High-RPM operation          RPM time above 4,000 rpm
  - Sustained high load         ENGINE_LOAD sustained above 70%
  - Fuel dilution risk          LONG_FUEL_TRIM_1 / SHORT_FUEL_TRIM_1
  - Stop-and-go intensity       Stop event count + idle time ratio
  - Ambient heat exposure       AMBIENT_TEMP (Texas summer penalty)

Score model:
  Each session accumulates a degradation score. Score is denominated in
  "equivalent clean miles" — 1.0 = one mile of ideal highway driving.
  Harsh city driving scores 2–3x per mile. Track driving scores 4–5x.
  Oil change is recommended when cumulative score since last change
  crosses the configured threshold (default: equivalent of 5,000 ideal miles).

Pipeline position:
    ingest.py → features.py → signal.py → rules.py → trends.py
                                                           ↓
                                           oil_change_detector.py
                                                           ↓
                                           oil_interval_advisor.py ← here
                                                           ↓
                                                    llm_report.py

Integrations:
  - Reads oil_change_detector.py history for last confirmed change
  - Reads maintenance_tracker.py session metrics where available
  - Outputs recommendation for llm_report.py injection

Usage:
    python3 oil_interval_advisor.py --csv acty_obd_20260313_161517.csv
    python3 oil_interval_advisor.py --status
    python3 oil_interval_advisor.py --set-last-change-mi 23500
    python3 oil_interval_advisor.py --set-threshold-mi 5000
    python3 oil_interval_advisor.py --profile   # show driving style analysis
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

# ── Storage paths ─────────────────────────────────────────────────────────────
HISTORY_PATH        = Path("data/oil_advisor_history.json")
OIL_CHANGE_HISTORY  = Path("data/oil_change_history.json")

# ── Degradation model constants ───────────────────────────────────────────────
# Threshold: cumulative degradation score triggering a change recommendation.
# Denominated in "equivalent ideal miles".
DEFAULT_THRESHOLD   = 5000.0    # equivalent to 5k ideal highway miles

# Oil temp severity bands (°C) — each minute above these adds score
OIL_TEMP_NORMAL     = 90.0      # normal operating temp, no penalty
OIL_TEMP_WARM       = 100.0     # mild thermal stress
OIL_TEMP_HOT        = 108.0     # significant oxidation acceleration
OIL_TEMP_CRITICAL   = 115.0     # severe — uncommon but possible in S&G traffic

# RPM severity bands
RPM_NORMAL          = 3000      # below this, no penalty
RPM_ELEVATED        = 4000      # moderate blowby increase
RPM_HIGH            = 5000      # significant blowby

# Load severity
LOAD_MODERATE       = 50        # % — moderate penalty
LOAD_HIGH           = 70        # % — significant penalty
LOAD_SEVERE         = 85        # % — severe penalty

# Fuel trim thresholds — rich running dilutes oil
LTFT_RICH_WARN      = 5.0       # % positive = rich = fuel dilution risk
LTFT_RICH_SEVERE    = 10.0

# Cold start severity — each cold start below threshold ages oil
COLD_START_FULL     = 20.0      # °C — cold soak, maximum cold start penalty
COLD_START_PARTIAL  = 50.0      # °C — partial warmup, moderate penalty

# Ambient temperature penalty — heat accelerates oxidation
AMBIENT_HOT         = 30.0      # °C (86°F) — mild penalty
AMBIENT_VERY_HOT    = 38.0      # °C (100°F) — significant penalty

# ── Scoring weights ───────────────────────────────────────────────────────────
# These are multipliers applied per mile driven under each condition.
# Baseline (ideal highway, 90°C oil, no cold starts) = 1.0x per mile.

WEIGHTS = {
    # Thermal stress: added per mile when oil exceeds temp bands
    "thermal_warm":         0.15,   # per mile above 100°C
    "thermal_hot":          0.40,   # per mile above 108°C
    "thermal_critical":     0.80,   # per mile above 115°C

    # Cold start: one-time penalty per session
    "cold_start_full":      8.0,    # equivalent miles per full cold start
    "cold_start_partial":   3.0,    # partial warmup (50°C start)

    # RPM stress: per mile above threshold
    "rpm_elevated":         0.20,   # per mile above 4k RPM
    "rpm_high":             0.50,   # per mile above 5k RPM

    # Load stress: per mile above threshold
    "load_moderate":        0.10,
    "load_high":            0.25,
    "load_severe":          0.50,

    # Stop-and-go: per stop event (thermal cycling + partial combustion)
    "stop_event":           0.30,   # per full stop in city driving

    # Fuel dilution risk: per mile when LTFT indicates rich running
    "fuel_dilution_warn":   0.20,
    "fuel_dilution_severe": 0.50,

    # Ambient heat: per mile in hot conditions
    "ambient_hot":          0.05,
    "ambient_very_hot":     0.15,
}

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class SessionDegradation:
    """Degradation score breakdown for a single drive session."""
    session_id:              str
    timestamp:               str
    odometer_km:             float
    trip_km:                 float
    ambient_temp_c:          float

    # Score components
    base_score:              float = 0.0   # miles × 1.0 (baseline)
    thermal_score:           float = 0.0
    cold_start_score:        float = 0.0
    rpm_score:               float = 0.0
    load_score:              float = 0.0
    stop_score:              float = 0.0
    fuel_dilution_score:     float = 0.0
    ambient_score:           float = 0.0

    # Total
    total_score:             float = 0.0
    severity_multiplier:     float = 1.0   # total / base (how harsh vs. ideal)

    # Context flags
    has_cold_start:          bool  = False
    drive_type:              str   = "unknown"
    dominant_factor:         str   = "baseline"

@dataclass
class AdvisorState:
    """Persistent state for the oil interval advisor."""
    sessions:                list  = field(default_factory=list)
    last_change_odometer_km: Optional[float] = None
    last_change_date:        Optional[str]   = None
    threshold_equiv_miles:   float           = DEFAULT_THRESHOLD
    cumulative_score:        float           = 0.0
    sessions_since_change:   int             = 0
    driving_profile:         str             = "unknown"

# ── Score computation ─────────────────────────────────────────────────────────

def compute_session_degradation(df: pd.DataFrame, session_id: str) -> SessionDegradation:
    """
    Compute the degradation score for one drive session.
    All scoring is per-mile so sessions of different lengths are comparable.
    """
    # ── Trip distance ─────────────────────────────────────────────────────────
    odo = df["ODOMETER"].dropna() if "ODOMETER" in df.columns else pd.Series([0, 0])
    odo_end   = float(odo.iloc[-1]) if not odo.empty else 0.0
    odo_start = float(odo.iloc[0])  if not odo.empty else 0.0
    trip_km   = max(0.0, odo_end - odo_start)
    trip_mi   = trip_km * 0.621

    timestamp = str(df["timestamp"].iloc[0]) if "timestamp" in df.columns else datetime.now().isoformat()
    ambient   = float(df["AMBIENT_TEMP"].mean()) if "AMBIENT_TEMP" in df.columns else 20.0

    # Cold start detection
    coolant_start = float(df["COOLANT_TEMP"].iloc[0]) if "COOLANT_TEMP" in df.columns else 90.0
    has_cold      = coolant_start < COLD_START_PARTIAL
    is_full_cold  = coolant_start < COLD_START_FULL

    # ── Drive type classification ─────────────────────────────────────────────
    if "SPEED" in df.columns:
        moving  = df[df["SPEED"] > 2]
        pct_hwy = float((df["SPEED"] > 80).mean())
        pct_idl = float(len(df[df["SPEED"] <= 2]) / max(len(df), 1))
        max_spd = float(df["SPEED"].max())
        if pct_hwy > 0.5 and max_spd > 90:
            drive_type = "highway"
        elif pct_idl > 0.35 or (max_spd < 70):
            drive_type = "city"
        else:
            drive_type = "mixed"
    else:
        drive_type = "unknown"
        pct_hwy = 0.5
        pct_idl = 0.3

    # ── Baseline score: 1.0 per mile ──────────────────────────────────────────
    base_score = trip_mi

    # ── Thermal score ─────────────────────────────────────────────────────────
    thermal_score = 0.0
    if "ENGINE_OIL_TEMP" in df.columns and trip_mi > 0:
        oil_t = df["ENGINE_OIL_TEMP"].dropna()
        pct_warm     = float((oil_t > OIL_TEMP_WARM).mean())
        pct_hot      = float((oil_t > OIL_TEMP_HOT).mean())
        pct_critical = float((oil_t > OIL_TEMP_CRITICAL).mean())
        thermal_score = trip_mi * (
            pct_warm     * WEIGHTS["thermal_warm"] +
            pct_hot      * WEIGHTS["thermal_hot"] +
            pct_critical * WEIGHTS["thermal_critical"]
        )

    # ── Cold start score ──────────────────────────────────────────────────────
    cold_start_score = 0.0
    if is_full_cold:
        cold_start_score = WEIGHTS["cold_start_full"]
    elif has_cold:
        cold_start_score = WEIGHTS["cold_start_partial"]

    # ── RPM score ─────────────────────────────────────────────────────────────
    rpm_score = 0.0
    if "RPM" in df.columns and trip_mi > 0:
        rpm = df["RPM"].dropna()
        pct_elevated = float((rpm > RPM_ELEVATED).mean())
        pct_high     = float((rpm > RPM_HIGH).mean())
        rpm_score = trip_mi * (
            pct_elevated * WEIGHTS["rpm_elevated"] +
            pct_high     * WEIGHTS["rpm_high"]
        )

    # ── Load score ────────────────────────────────────────────────────────────
    load_score = 0.0
    if "ENGINE_LOAD" in df.columns and trip_mi > 0:
        load = df["ENGINE_LOAD"].dropna()
        # Only penalize load when actually moving (idle high load ≠ oil stress)
        if "SPEED" in df.columns:
            moving_load = df.loc[df["SPEED"] > 10, "ENGINE_LOAD"].dropna()
        else:
            moving_load = load
        if len(moving_load) > 0:
            pct_mod    = float((moving_load > LOAD_MODERATE).mean())
            pct_high   = float((moving_load > LOAD_HIGH).mean())
            pct_severe = float((moving_load > LOAD_SEVERE).mean())
            load_score = trip_mi * (
                pct_mod    * WEIGHTS["load_moderate"] +
                pct_high   * WEIGHTS["load_high"] +
                pct_severe * WEIGHTS["load_severe"]
            )

    # ── Stop-and-go score ─────────────────────────────────────────────────────
    stop_score = 0.0
    if "SPEED" in df.columns:
        speeds = df["SPEED"].fillna(0).values
        stop_count = 0
        for i in range(1, len(speeds)):
            if speeds[i-1] > 10 and speeds[i] < 5:
                stop_count += 1
        stop_score = stop_count * WEIGHTS["stop_event"]

    # ── Fuel dilution score ───────────────────────────────────────────────────
    fuel_dilution_score = 0.0
    if "LONG_FUEL_TRIM_1" in df.columns and trip_mi > 0:
        ltft = df["LONG_FUEL_TRIM_1"].dropna()
        # Positive LTFT = ECU adding fuel = rich running = fuel dilution risk
        pct_rich_warn   = float((ltft > LTFT_RICH_WARN).mean())
        pct_rich_severe = float((ltft > LTFT_RICH_SEVERE).mean())
        fuel_dilution_score = trip_mi * (
            pct_rich_warn   * WEIGHTS["fuel_dilution_warn"] +
            pct_rich_severe * WEIGHTS["fuel_dilution_severe"]
        )
    # Note: negative LTFT (your current -6 to -8%) = lean = ECU pulling fuel
    # = actually LESS fuel dilution than neutral. No penalty for negative LTFT.

    # ── Ambient heat score ────────────────────────────────────────────────────
    ambient_score = 0.0
    if trip_mi > 0:
        if ambient > AMBIENT_VERY_HOT:
            ambient_score = trip_mi * WEIGHTS["ambient_very_hot"]
        elif ambient > AMBIENT_HOT:
            ambient_score = trip_mi * WEIGHTS["ambient_hot"]

    # ── Total and multiplier ──────────────────────────────────────────────────
    total_score = (
        base_score + thermal_score + cold_start_score +
        rpm_score + load_score + stop_score +
        fuel_dilution_score + ambient_score
    )
    severity_mult = round(total_score / max(base_score, 0.001), 2)

    # ── Dominant degradation factor ───────────────────────────────────────────
    components = {
        "thermal cycling":   thermal_score,
        "cold starts":       cold_start_score,
        "high RPM":          rpm_score,
        "sustained load":    load_score,
        "stop-and-go":       stop_score,
        "fuel dilution":     fuel_dilution_score,
        "ambient heat":      ambient_score,
    }
    dominant = max(components, key=components.get)
    if components[dominant] < 0.5:
        dominant = "baseline (normal driving)"

    return SessionDegradation(
        session_id           = session_id,
        timestamp            = timestamp,
        odometer_km          = odo_end,
        trip_km              = round(trip_km, 2),
        ambient_temp_c       = round(ambient, 1),
        base_score           = round(base_score, 2),
        thermal_score        = round(thermal_score, 2),
        cold_start_score     = round(cold_start_score, 2),
        rpm_score            = round(rpm_score, 2),
        load_score           = round(load_score, 2),
        stop_score           = round(stop_score, 2),
        fuel_dilution_score  = round(fuel_dilution_score, 2),
        ambient_score        = round(ambient_score, 2),
        total_score          = round(total_score, 2),
        severity_multiplier  = severity_mult,
        has_cold_start       = has_cold,
        drive_type           = drive_type,
        dominant_factor      = dominant,
    )

# ── Driving profile analysis ──────────────────────────────────────────────────

def analyze_driving_profile(sessions: list[SessionDegradation]) -> dict:
    """Summarize driving style and its oil change implications."""
    if not sessions:
        return {"profile": "unknown", "avg_severity": 1.0}

    mults  = [s.severity_multiplier for s in sessions]
    types  = [s.drive_type for s in sessions]
    colds  = sum(1 for s in sessions if s.has_cold_start)
    stops  = [s.stop_score / max(s.trip_km * 0.621, 0.1) for s in sessions]

    avg_mult  = float(np.mean(mults))
    avg_stops = float(np.mean(stops))

    # Classify driving profile
    if avg_mult < 1.3:
        profile = "highway_light"
        label   = "Highway / light city — low oil stress"
        implied = "8,000–10,000 miles"
    elif avg_mult < 1.7:
        profile = "mixed_moderate"
        label   = "Mixed suburban driving — moderate oil stress"
        implied = "6,000–8,000 miles"
    elif avg_mult < 2.2:
        profile = "city_moderate"
        label   = "City / stop-and-go — elevated oil stress"
        implied = "4,500–6,000 miles"
    elif avg_mult < 3.0:
        profile = "city_severe"
        label   = "Heavy city / hot climate — high oil stress"
        implied = "3,500–5,000 miles"
    else:
        profile = "extreme"
        label   = "Extreme use / track — severe oil stress"
        implied = "2,000–3,500 miles"

    dominant_type = max(set(types), key=types.count) if types else "unknown"

    return {
        "profile":              profile,
        "label":                label,
        "implied_interval_mi":  implied,
        "avg_severity_mult":    round(avg_mult, 2),
        "sessions_analyzed":    len(sessions),
        "cold_starts":          colds,
        "dominant_drive_type":  dominant_type,
        "avg_stops_per_mile":   round(avg_stops, 3),
        "toyota_10k_appropriate": avg_mult < 1.4,
    }

# ── Recommendation ────────────────────────────────────────────────────────────

def build_recommendation(
    pct_used:       float,
    equiv_miles:    float,
    threshold_mi:   float,
    profile:        dict,
    dominant:       str,
    actual_miles:   float,
) -> str:
    remaining = threshold_mi - equiv_miles
    if pct_used >= 1.0:
        return (
            f"Oil change recommended now. Accumulated {equiv_miles:.0f} equivalent "
            f"severity-miles ({actual_miles:.0f} actual miles) — primary stress factor: "
            f"{dominant}. Your driving style implies a {profile['implied_interval_mi']}-mile "
            f"interval, not Toyota's 10k."
        )
    if pct_used >= 0.85:
        return (
            f"Oil change due soon (~{remaining:.0f} equivalent miles remaining). "
            f"Current severity multiplier: {profile['avg_severity_mult']:.1f}× "
            f"({profile['label']})."
        )
    if pct_used >= 0.65:
        return (
            f"Oil at ~{pct_used:.0%} of recommended severity threshold. "
            f"Primary wear factor: {dominant}. "
            f"Estimated {remaining:.0f} equivalent miles remaining."
        )
    return (
        f"Oil condition good — {pct_used:.0%} of severity threshold used "
        f"({equiv_miles:.0f} equiv. miles of {threshold_mi:.0f}). "
        f"Severity multiplier: {profile['avg_severity_mult']:.1f}× vs. ideal driving."
    )

# ── Main advisor class ────────────────────────────────────────────────────────

class OilIntervalAdvisor:
    def __init__(self, history_path: Path = HISTORY_PATH):
        self.history_path = Path(history_path)
        self.state = self._load_state()
        self._sync_from_oil_change_detector()

    def _load_state(self) -> AdvisorState:
        if self.history_path.exists() and self.history_path.stat().st_size > 0:
            with open(self.history_path) as f:
                data = json.load(f)
            s = AdvisorState()
            for k, v in data.items():
                if hasattr(s, k):
                    setattr(s, k, v)
            return s
        return AdvisorState()

    def _save_state(self):
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_path, "w") as f:
            json.dump(asdict(self.state), f, indent=2, default=str)

    def _sync_from_oil_change_detector(self):
        """Pull last confirmed change from oil_change_detector.py."""
        if not OIL_CHANGE_HISTORY.exists():
            return
        try:
            with open(OIL_CHANGE_HISTORY) as f:
                data = json.load(f)
            det_odo  = data.get("last_change_odometer")
            det_date = data.get("last_change_date")
            if det_odo and det_odo != self.state.last_change_odometer_km:
                print(f"[ADVISOR] Synced oil change from detector: "
                      f"{det_odo:.1f} km ({det_odo*0.621:.0f} mi)")
                self._reset_after_change(det_odo, det_date)
        except (json.JSONDecodeError, KeyError):
            pass

    def _reset_after_change(self, odo_km: float, date: Optional[str] = None):
        self.state.last_change_odometer_km = odo_km
        self.state.last_change_date        = date or datetime.now().isoformat()
        self.state.cumulative_score        = 0.0
        self.state.sessions_since_change   = 0
        # Keep sessions list but mark change point
        self._save_state()

    def set_last_change(self, odometer_km: float, date: Optional[str] = None):
        """Manually set the last oil change seed point."""
        self._reset_after_change(odometer_km, date)
        # Remove sessions that predate this change
        self.state.sessions = [
            s for s in self.state.sessions
            if s["odometer_km"] > odometer_km
        ]
        self._save_state()
        print(f"[ADVISOR] Last change set: {odometer_km:.1f} km ({odometer_km*0.621:.0f} mi)")

    def set_threshold(self, equiv_miles: float):
        self.state.threshold_equiv_miles = equiv_miles
        self._save_state()
        print(f"[ADVISOR] Threshold set: {equiv_miles:.0f} equivalent miles")

    def ingest_session(self, df: pd.DataFrame, session_id: str):
        """Score a session and accumulate degradation."""
        existing = [s["session_id"] for s in self.state.sessions]
        if session_id in existing:
            print(f"[ADVISOR] {session_id} already ingested — skipping")
            return

        deg = compute_session_degradation(df, session_id)
        self.state.sessions.append(asdict(deg))

        # Only accumulate score for sessions after the last change
        if (self.state.last_change_odometer_km is None or
                deg.odometer_km > self.state.last_change_odometer_km):
            self.state.cumulative_score  += deg.total_score
            self.state.sessions_since_change += 1

        # Update driving profile
        post_change_sessions = self._post_change_sessions()
        if post_change_sessions:
            profile = analyze_driving_profile(post_change_sessions)
            self.state.driving_profile = profile["profile"]

        self._save_state()

        pct = self.state.cumulative_score / self.state.threshold_equiv_miles
        flag = "🔴" if pct >= 1.0 else "⚠️" if pct >= 0.85 else "✅"
        print(f"[ADVISOR] {session_id}  "
              f"session_score={deg.total_score:.1f}  "
              f"mult={deg.severity_multiplier:.2f}×  "
              f"cumulative={self.state.cumulative_score:.0f}/"
              f"{self.state.threshold_equiv_miles:.0f}  "
              f"({pct:.0%})  {flag}")

    def _post_change_sessions(self) -> list[SessionDegradation]:
        """Sessions accumulated since the last confirmed oil change."""
        cutoff = self.state.last_change_odometer_km or 0
        return [
            SessionDegradation(**s) for s in self.state.sessions
            if s["odometer_km"] > cutoff
        ]

    def status(self) -> dict:
        """Full status and recommendation."""
        threshold_mi = self.state.threshold_equiv_miles
        cumul        = self.state.cumulative_score
        pct_used     = cumul / threshold_mi if threshold_mi > 0 else 0.0

        if not self.state.sessions:
            return {"status": "no_data", "message": "No sessions ingested yet."}
        if not self.state.last_change_odometer_km:
            return {
                "status": "no_seed",
                "message": "Set last oil change with --set-last-change-mi <miles>",
                "cumulative_score": round(cumul, 1),
            }

        post = self._post_change_sessions()
        profile = analyze_driving_profile(post) if post else {"profile": "unknown",
            "label": "unknown", "implied_interval_mi": "unknown",
            "avg_severity_mult": 1.0, "sessions_analyzed": 0,
            "cold_starts": 0, "dominant_drive_type": "unknown",
            "avg_stops_per_mile": 0, "toyota_10k_appropriate": False}

        # Find dominant factor across all post-change sessions
        if post:
            factor_totals = {
                "thermal cycling":  sum(s.thermal_score for s in post),
                "cold starts":      sum(s.cold_start_score for s in post),
                "high RPM":         sum(s.rpm_score for s in post),
                "sustained load":   sum(s.load_score for s in post),
                "stop-and-go":      sum(s.stop_score for s in post),
                "fuel dilution":    sum(s.fuel_dilution_score for s in post),
                "ambient heat":     sum(s.ambient_score for s in post),
            }
            dominant = max(factor_totals, key=factor_totals.get)
        else:
            dominant = "baseline"
            factor_totals = {}

        actual_km = (
            (post[-1].odometer_km - self.state.last_change_odometer_km)
            if post else 0
        )
        actual_mi = actual_km * 0.621

        # Status band
        if pct_used >= 1.0:   status = "overdue"
        elif pct_used >= 0.85: status = "due_soon"
        elif pct_used >= 0.65: status = "monitor"
        else:                  status = "ok"

        icons = {"ok": "✅", "monitor": "👀", "due_soon": "⚠️", "overdue": "🔴"}

        return {
            "status":                  status,
            "icon":                    icons[status],
            "pct_threshold_used":      round(pct_used * 100, 1),
            "cumulative_equiv_miles":  round(cumul, 1),
            "threshold_equiv_miles":   threshold_mi,
            "equiv_miles_remaining":   round(max(0, threshold_mi - cumul), 1),
            "actual_miles_since_change": round(actual_mi, 1),
            "sessions_since_change":   self.state.sessions_since_change,
            "last_change_mi":          round((self.state.last_change_odometer_km or 0) * 0.621, 0),
            "last_change_date":        self.state.last_change_date,

            # Driving profile
            "driving_profile":         profile["label"],
            "avg_severity_mult":       profile["avg_severity_mult"],
            "implied_interval_mi":     profile["implied_interval_mi"],
            "toyota_10k_appropriate":  profile["toyota_10k_appropriate"],
            "dominant_degradation_factor": dominant,

            # Score breakdown (total since last change)
            "score_breakdown": {
                k: round(v, 1) for k, v in factor_totals.items()
            } if factor_totals else {},

            "recommendation": build_recommendation(
                pct_used, cumul, threshold_mi, profile, dominant, actual_mi
            ),
        }

# ── Pipeline integration helper ───────────────────────────────────────────────

def get_report_context(advisor: "OilIntervalAdvisor") -> dict:
    """Clean dict for injection into llm_report.py prompt context."""
    s = advisor.status()
    return {
        "oil_interval_status":      s.get("status", "unknown"),
        "oil_severity_pct":         s.get("pct_threshold_used"),
        "oil_equiv_miles_used":     s.get("cumulative_equiv_miles"),
        "oil_equiv_miles_remaining":s.get("equiv_miles_remaining"),
        "oil_actual_miles":         s.get("actual_miles_since_change"),
        "oil_severity_mult":        s.get("avg_severity_mult"),
        "oil_dominant_factor":      s.get("dominant_degradation_factor"),
        "oil_driving_profile":      s.get("driving_profile"),
        "oil_implied_interval":     s.get("implied_interval_mi"),
        "oil_toyota_10k_ok":        s.get("toyota_10k_appropriate"),
        "oil_recommendation":       s.get("recommendation"),
    }

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Acty severity-weighted oil interval advisor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--csv",                  help="Ingest and score a session CSV")
    parser.add_argument("--status",  action="store_true", help="Show full status")
    parser.add_argument("--profile", action="store_true", help="Show driving profile breakdown")
    parser.add_argument("--history", default=str(HISTORY_PATH))
    parser.add_argument("--set-last-change-mi",  type=float, metavar="MI")
    parser.add_argument("--set-last-change-km",  type=float, metavar="KM")
    parser.add_argument("--set-threshold-mi",    type=float, metavar="MI",
                        help="Override severity threshold in equivalent miles (default: 5000)")
    parser.add_argument("--reset",   action="store_true")
    args = parser.parse_args()

    advisor = OilIntervalAdvisor(history_path=args.history)

    if args.reset:
        advisor.state = AdvisorState()
        advisor._save_state()
        print("[ADVISOR] History cleared.")
        return

    if args.set_last_change_mi:
        advisor.set_last_change(args.set_last_change_mi * 1.60934)
    if args.set_last_change_km:
        advisor.set_last_change(args.set_last_change_km)
    if args.set_threshold_mi:
        advisor.set_threshold(args.set_threshold_mi)

    if args.csv:
        path = Path(args.csv)
        if not path.exists():
            print(f"[ERROR] {path} not found")
            sys.exit(1)
        df = pd.read_csv(path, parse_dates=["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        advisor.ingest_session(df, path.stem)

    if args.profile and advisor.state.sessions:
        post = advisor._post_change_sessions()
        p = analyze_driving_profile(post)
        print(f"\n── Driving Profile ──────────────────────────────────────")
        for k, v in p.items():
            print(f"   {k}: {v}")
        print(f"────────────────────────────────────────────────────────\n")

    if args.status or args.csv or not any([
        args.set_last_change_mi, args.set_last_change_km,
        args.set_threshold_mi, args.reset
    ]):
        s = advisor.status()
        if s.get("status") in ("no_data", "no_seed"):
            print(f"\n[ADVISOR] {s.get('message', s['status'])}\n")
            return

        print(f"\n── Oil Interval Advisor ─────────────────────────────────")
        print(f"   Status:          {s['icon']}  {s['status'].upper()}")
        print(f"   Severity used:   {s['pct_threshold_used']}%  "
              f"({s['cumulative_equiv_miles']:.0f} / {s['threshold_equiv_miles']:.0f} equiv. miles)")
        print(f"   Actual miles:    {s['actual_miles_since_change']:.0f} mi since last change")
        print(f"   Severity mult:   {s['avg_severity_mult']:.2f}×  "
              f"(1.0× = ideal highway, {s['avg_severity_mult']:.2f}× = your driving)")
        print(f"   Profile:         {s['driving_profile']}")
        print(f"   Implied interval:{s['implied_interval_mi']}")
        print(f"   10k Toyota OK?   {'Yes' if s['toyota_10k_appropriate'] else 'No — your conditions warrant shorter interval'}")
        print(f"   Top factor:      {s['dominant_degradation_factor']}")
        if s.get("score_breakdown"):
            print(f"   Score breakdown:")
            for factor, score in sorted(s["score_breakdown"].items(),
                                        key=lambda x: x[1], reverse=True):
                if score > 0.5:
                    print(f"     {factor:<22} {score:.1f} equiv. mi")
        print(f"\n   → {s['recommendation']}")
        print(f"────────────────────────────────────────────────────────\n")

if __name__ == "__main__":
    main()
