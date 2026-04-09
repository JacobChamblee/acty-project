"""
prompt_builder.py — Cactus structured prompt construction.

This file is the PRIMARY reason Cactus insight is better than a user uploading
a raw CSV to Claude/ChatGPT directly. Every section in the output is grounded
in upstream pipeline data — never raw PID values or CSV rows.

Pipeline inputs:
  Tier 0: session feature aggregates + cross-session LTFT trend
  Tier 1: anomaly_flags from Isolation Forest + rule engine
  Tier 2: fsm_references from RAG retrieval (ChromaDB)
  Tier 4: lstm_reconstruction (may be None if background job not finished)
  Tier 5: fleet_pattern_match (may be None if insufficient fleet data)

The system prompt text adapts based on session_count to surface the most
relevant Cactus differentiator for the user's stage (see BYOK value prop doc).
"""

from __future__ import annotations

from .providers import CactusPrompt


# ── Session-count UX tiers ─────────────────────────────────────────────────────
# Matches the table in CACTUS_BYOK_VALUE_PROP.md §"Session-1 vs Mature"

def _session_tier(count: int) -> str:
    if count == 1:
        return "session_1"
    if count <= 4:
        return "early"   # sessions 2-4
    return "mature"      # sessions 5+


def _system_prompt(tier: str, has_fleet: bool) -> str:
    base = (
        "You are a vehicle diagnostic specialist working with pre-analyzed telemetry data "
        "from the Cactus platform. You receive structured outputs from the Cactus ML pipeline — "
        "NOT raw sensor data. Every numeric threshold you cite must come from the FSM reference "
        "section below; do not generate thresholds from general knowledge."
    )

    if tier == "session_1":
        emphasis = (
            "\n\nThis is the vehicle's FIRST captured session. Emphasize:\n"
            "1. FSM-grounded diagnostics — cite section and OEM threshold for every flagged value.\n"
            "2. The tamper-evident signed report the user will receive.\n"
            "3. What longitudinal context will unlock as more sessions accumulate.\n"
            "Do NOT speculate about trends — there is no trend data yet."
        )
    elif tier == "early":
        emphasis = (
            "\n\nThis vehicle has a small session history (2-4 sessions). Emphasize:\n"
            "1. Emerging trend direction from the LTFT cross-session data (even a single delta is meaningful).\n"
            "2. FSM-grounded diagnostics with OEM thresholds for flagged conditions.\n"
            "3. What the trend trajectory means if it continues at this rate."
        )
    else:  # mature
        fleet_note = (
            "\n4. Fleet pattern context — compare to the privacy-preserving fleet aggregate."
            if has_fleet else ""
        )
        emphasis = (
            "\n\nThis vehicle has a mature session history (5+ sessions). Emphasize:\n"
            "1. Full longitudinal LTFT trend — rate of change, direction, kilometers of drift.\n"
            "2. Cross-session anomaly pattern evolution (improving / stable / worsening).\n"
            "3. FSM-grounded diagnostics with OEM thresholds — cite section for every threshold."
            + fleet_note
        )

    return base + emphasis


def _ltft_section(ltft: dict) -> str:
    n = ltft.get("n_sessions", 0)
    values = ltft.get("values", [])
    direction = ltft.get("direction", "unknown")
    rate = ltft.get("rate_per_session")

    if n == 0 or not values:
        return "Cross-session LTFT trend: No prior sessions — baseline not yet established."

    vals_str = ", ".join(f"{v:+.2f}%" for v in values[-5:])  # last 5 sessions max
    rate_str = f"{rate:+.3f}%/session" if rate is not None else "rate unknown"
    return (
        f"Cross-session LTFT trend ({n} sessions):\n"
        f"  Recent values: {vals_str}\n"
        f"  Direction: {direction} | Rate: {rate_str}"
    )


def _anomaly_section(flags: list[dict]) -> str:
    if not flags:
        return "Anomaly flags (Isolation Forest + rule engine):\n  None detected this session."
    lines = ["Anomaly flags (Isolation Forest + rule engine):"]
    for f in flags:
        name = f.get("name") or f.get("pid") or f.get("label", "Unknown")
        conf = f.get("confidence") or f.get("anomaly_score")
        conf_str = f" confidence {conf:.2f}" if conf is not None else ""
        desc = f.get("description") or f.get("message", "")
        sev = f.get("severity", "")
        lines.append(f"  [{sev.upper()}] {name}{conf_str}: {desc}")
    return "\n".join(lines)


def _fleet_section(fleet: dict | None) -> str:
    if fleet is None:
        return (
            "Fleet pattern match: Insufficient fleet data for this vehicle configuration "
            "(requires minimum fleet size for privacy-preserving FL aggregation)."
        )
    pattern = fleet.get("pattern_name", "Unknown pattern")
    n = fleet.get("n_vehicles", 0)
    conf = fleet.get("confidence_pct", 0)
    outcome = fleet.get("outcome_summary", "")
    return (
        f"Fleet pattern match (privacy-preserving — no individual data exposed):\n"
        f"  Pattern: {pattern}\n"
        f"  Fleet sample: {n} vehicles | Match confidence: {conf:.0f}%\n"
        f"  Typical outcome in matched fleet: {outcome}"
    )


def _fsm_section(refs: list[dict]) -> str:
    if not refs:
        return (
            "FSM reference: No FSM context retrieved for this vehicle/condition combination. "
            "[REDUCED CONFIDENCE — thresholds not OEM-verified for this session]"
        )
    lines = [
        "FSM reference (OEM-specified thresholds — cite these, do not invent thresholds):"
    ]
    for r in refs:
        section = r.get("section", "?")
        page = r.get("page", "?")
        spec = r.get("spec_value", "")
        desc = r.get("description", "")
        spec_str = f" | Spec: {spec}" if spec else ""
        lines.append(f"  §{section} p.{page}{spec_str} — {desc}")
    return "\n".join(lines)


def _lstm_section(lstm: dict | None) -> str:
    if lstm is None:
        return (
            "LSTM reconstruction analysis: Background job not yet complete — "
            "deep temporal analysis will be delivered asynchronously."
        )
    error = lstm.get("error")
    threshold = lstm.get("threshold")
    status = lstm.get("status", "unknown")
    return (
        f"LSTM reconstruction error: {error:.4f} (threshold: {threshold:.4f}) — {status}"
        if error is not None and threshold is not None
        else f"LSTM reconstruction: {status}"
    )


def _data_richness_note(session_count: int) -> str:
    if session_count >= 3:
        return ""
    return (
        f"\n[DATA RICHNESS] This vehicle has {session_count} captured session(s). "
        "Trend analysis and fleet pattern matching improve significantly after 3+ sessions. "
        "FSM-grounded diagnostics and the tamper-evident signed report are available immediately."
    )


def _session_section(summary: dict) -> str:
    date = summary.get("session_date", "Unknown date")
    dur = summary.get("duration_min", "?")
    drive_type = summary.get("drive_type", "mixed")
    lines = [f"Session: {date}, {dur} min, drive type: {drive_type}"]

    feature_map = {
        "avg_rpm": ("Avg RPM", "{:.0f}"),
        "max_rpm": ("Max RPM", "{:.0f}"),
        "avg_speed_kmh": ("Avg speed", "{:.1f} kph"),
        "max_speed_kmh": ("Max speed", "{:.1f} kph"),
        "avg_coolant_c": ("Avg coolant", "{:.1f}°C"),
        "max_coolant_c": ("Max coolant", "{:.1f}°C"),
        "avg_engine_load": ("Avg load", "{:.1f}%"),
        "ltft_b1": ("LTFT B1 (this session)", "{:+.2f}%"),
        "stft_b1": ("STFT B1 (this session)", "{:+.2f}%"),
        "avg_timing": ("Avg timing advance", "{:.1f}°"),
        "avg_maf": ("Avg MAF", "{:.2f} g/s"),
        "pct_time_moving": ("Time moving", "{:.1f}%"),
        "battery_v": ("Battery voltage", "{:.2f}V"),
        "fuel_level_pct": ("Fuel level", "{:.1f}%"),
    }
    aggregates = []
    for key, (label, fmt) in feature_map.items():
        val = summary.get(key)
        if val is not None:
            try:
                aggregates.append(f"  {label}: {fmt.format(val)}")
            except (TypeError, ValueError):
                pass

    if aggregates:
        lines.append("Session feature summary (pre-aggregated — NOT raw PID rows):")
        lines.extend(aggregates)

    return "\n".join(lines)


# ── Public API ─────────────────────────────────────────────────────────────────

def build_prompt(
    vehicle_context: dict,
    session_summary: dict,
    ltft_trend: dict,
    anomaly_flags: list[dict],
    fsm_references: list[dict],
    user_query: str,
    session_count: int,
    fleet_pattern_match: dict | None = None,
    lstm_reconstruction: dict | None = None,
    previous_reports_summary: str | None = None,
) -> CactusPrompt:
    """
    Construct a CactusPrompt from pipeline tier outputs.

    This function validates that no raw PID row data slips through.
    The CactusPrompt fields contain ONLY derived/aggregated features.
    """
    # Sanitize: strip any key that looks like a raw time-series array
    safe_summary = {
        k: v for k, v in session_summary.items()
        if not isinstance(v, (list, tuple)) or len(v) <= 10
    }

    return CactusPrompt(
        vehicle_context=vehicle_context,
        session_summary=safe_summary,
        ltft_trend=ltft_trend,
        anomaly_flags=anomaly_flags,
        fleet_pattern_match=fleet_pattern_match,
        fsm_references=fsm_references,
        lstm_reconstruction=lstm_reconstruction,
        previous_reports_summary=previous_reports_summary,
        user_query=user_query,
        session_count=session_count,
    )


def render_prompt_messages(prompt: CactusPrompt) -> list[dict]:
    """
    Render a CactusPrompt into an OpenAI-style messages list:
      [{"role": "system", "content": ...}, {"role": "user", "content": ...}]

    Providers that use a different format (e.g. Anthropic, Google) should
    convert from this canonical form in their own implementation.
    """
    tier = _session_tier(prompt.session_count)
    has_fleet = prompt.fleet_pattern_match is not None

    vc = prompt.vehicle_context
    vehicle_str = (
        f"Vehicle: {vc.get('make', '?')} {vc.get('model', '?')} {vc.get('year', '?')}, "
        f"{vc.get('engine', 'engine unknown')}, "
        f"{vc.get('odometer_km', '?')} km odometer"
    )

    prev_reports = (
        f"\nPrevious reports summary (last 3):\n  {prompt.previous_reports_summary}"
        if prompt.previous_reports_summary
        else ""
    )

    sections = [
        vehicle_str,
        _session_section(prompt.session_summary),
        _ltft_section(prompt.ltft_trend),
        _anomaly_section(prompt.anomaly_flags),
        _fleet_section(prompt.fleet_pattern_match),
        _fsm_section(prompt.fsm_references),
        _lstm_section(prompt.lstm_reconstruction),
        prev_reports,
        _data_richness_note(prompt.session_count),
        f'User question: "{prompt.user_query}"',
    ]
    user_content = "\n\n".join(s for s in sections if s).strip()

    return [
        {"role": "system", "content": _system_prompt(tier, has_fleet)},
        {"role": "user", "content": user_content},
    ]
