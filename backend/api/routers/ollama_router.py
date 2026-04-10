"""
ollama_router.py — Local Ollama AI integration for OBD session analysis.

GET  /api/v1/ollama/models
  Lists models available on the local Ollama server.

POST /api/v1/ollama/analyze
  Reads the specified (or latest) OBD-II CSV from ACTY_CSV_DIR,
  extracts summary stats + rule-based alerts, and streams an AI
  diagnostic analysis via Server-Sent Events.

Ollama runs natively on the 4U server (192.168.68.138:11434).
The backend reaches it at OLLAMA_BASE_URL (defaults to that address).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/ollama", tags=["ollama"])

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://192.168.68.138:11434")
CSV_DIR = Path(os.environ.get("ACTY_CSV_DIR", str(Path.home())))

# ── Rule-based thresholds (mirrors server.py) ─────────────────────────────────
_THRESHOLDS = {
    "LONG_FUEL_TRIM_1":  ("Long Fuel Trim B1",  "%",   8.0,  12.0, "abs"),
    "SHORT_FUEL_TRIM_1": ("Short Fuel Trim B1",  "%",  10.0,  20.0, "abs"),
    "LONG_FUEL_TRIM_2":  ("Long Fuel Trim B2",   "%",   8.0,  12.0, "abs"),
    "CONTROL_VOLTAGE":   ("Battery Voltage",      "V",  13.8,  11.5, "low"),
    "COOLANT_TEMP":      ("Coolant Temp",         "°C", 100,   108,  "high"),
    "ENGINE_OIL_TEMP":   ("Oil Temp",             "°C", 120,   135,  "high"),
    "ENGINE_LOAD":       ("Engine Load",          "%",   85,    95,  "high"),
    "RPM":               ("RPM",                  "rpm", 5000, 6000, "high"),
    "INTAKE_TEMP":       ("Intake Air Temp",       "°C",  50,   65,  "high"),
}


# ── Schemas ────────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    session_filename: Optional[str] = None   # None → latest CSV
    question: str = "Summarize the key findings from this drive session."
    model: str = "llama3.2"


# ── CSV helpers ────────────────────────────────────────────────────────────────

def _find_csv(filename: Optional[str]) -> Path:
    if filename:
        p = CSV_DIR / filename
        if not p.exists():
            raise HTTPException(404, f"Session file not found: {filename!r}")
        return p
    csvs = sorted(CSV_DIR.glob("acty_obd_*.csv"), key=lambda x: x.stat().st_mtime)
    if not csvs:
        raise HTTPException(404, "No OBD session CSV files found on server")
    return csvs[-1]


def _col_stats(df: pd.DataFrame, col: str) -> dict | None:
    if col not in df.columns:
        return None
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    if s.empty:
        return None
    return {
        "mean": round(float(s.mean()), 2),
        "max":  round(float(s.max()),  2),
        "min":  round(float(s.min()),  2),
    }


def _summarize_csv(path: Path) -> dict:
    """Read CSV and extract key metrics + rule-based alerts."""
    try:
        df = pd.read_csv(path, parse_dates=["timestamp"])
    except Exception:
        df = pd.read_csv(path)

    # Duration
    duration_min = None
    if "elapsed_s" in df.columns:
        elapsed = pd.to_numeric(df["elapsed_s"], errors="coerce").dropna()
        if not elapsed.empty:
            duration_min = round(float(elapsed.max()) / 60, 1)
    elif "timestamp" in df.columns:
        try:
            ts = pd.to_datetime(df["timestamp"], errors="coerce").dropna()
            if len(ts) >= 2:
                duration_min = round((ts.iloc[-1] - ts.iloc[0]).total_seconds() / 60, 1)
        except Exception:
            pass

    # Session date
    session_date = path.stem
    if "timestamp" in df.columns:
        try:
            ts0 = pd.to_datetime(df["timestamp"].iloc[0], errors="coerce")
            if pd.notna(ts0):
                session_date = ts0.strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass

    # Rule-based alerts
    alerts: list[str] = []
    for col, (label, unit, warn, crit, mode) in _THRESHOLDS.items():
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            continue
        val = float(s.mean())
        if mode == "abs":
            if abs(val) >= crit:  alerts.append(f"CRITICAL: {label} avg {val:+.1f}{unit}")
            elif abs(val) >= warn: alerts.append(f"WARNING:  {label} avg {val:+.1f}{unit}")
        elif mode == "low":
            if val <= crit:  alerts.append(f"CRITICAL: {label} avg {val:.2f}{unit} (low)")
            elif val <= warn: alerts.append(f"WARNING:  {label} avg {val:.2f}{unit} (low)")
        else:  # high
            if val >= crit:  alerts.append(f"CRITICAL: {label} avg {val:.1f}{unit}")
            elif val >= warn: alerts.append(f"WARNING:  {label} avg {val:.1f}{unit}")

    # Key PID stats
    pids = ["RPM", "SPEED", "COOLANT_TEMP", "ENGINE_OIL_TEMP", "ENGINE_LOAD",
            "LONG_FUEL_TRIM_1", "SHORT_FUEL_TRIM_1", "CONTROL_VOLTAGE",
            "MAF", "INTAKE_TEMP", "TIMING_ADVANCE", "THROTTLE_POS"]
    stats = {pid.lower(): _col_stats(df, pid) for pid in pids}

    # Sample rows (first 5 rows of key columns)
    sample_cols = [c for c in
                   ["timestamp", "elapsed_s", "RPM", "SPEED", "COOLANT_TEMP",
                    "ENGINE_LOAD", "LONG_FUEL_TRIM_1", "SHORT_FUEL_TRIM_1",
                    "CONTROL_VOLTAGE", "MAF"]
                   if c in df.columns]
    sample_csv = df[sample_cols].head(5).to_csv(index=False)

    return {
        "filename":     path.name,
        "session_date": session_date,
        "sample_count": len(df),
        "duration_min": duration_min,
        "alerts":       alerts,
        "sample_csv":   sample_csv,
        **stats,
    }


def _build_prompt(stats: dict, question: str) -> str:
    def fmt(key: str, unit: str = "") -> str:
        d = stats.get(key)
        if not d:
            return "N/A"
        return f"avg {d['mean']}{unit}  (min {d['min']}, max {d['max']})"

    lines = [
        "You are an expert automotive diagnostic AI assistant.",
        "Analyze the following OBD-II drive session data and answer the question below.",
        "Be concise, practical, and explain any concerning findings clearly.",
        "",
        f"SESSION: {stats['session_date']}  |  {stats['sample_count']} data points"
        + (f"  |  {stats['duration_min']} min" if stats['duration_min'] else ""),
        "",
        "KEY METRICS:",
        f"  RPM:               {fmt('rpm', ' rpm')}",
        f"  Speed:             {fmt('speed', ' km/h')}",
        f"  Coolant Temp:      {fmt('coolant_temp', '°C')}",
        f"  Oil Temp:          {fmt('engine_oil_temp', '°C')}",
        f"  Engine Load:       {fmt('engine_load', '%')}",
        f"  Long Fuel Trim B1: {fmt('long_fuel_trim_1', '%')}",
        f"  Short Fuel Trim B1:{fmt('short_fuel_trim_1', '%')}",
        f"  Battery Voltage:   {fmt('control_voltage', ' V')}",
        f"  MAF:               {fmt('maf', ' g/s')}",
        f"  Intake Air Temp:   {fmt('intake_temp', '°C')}",
        f"  Timing Advance:    {fmt('timing_advance', '°')}",
        f"  Throttle Position: {fmt('throttle_pos', '%')}",
        "",
    ]

    if stats["alerts"]:
        lines += ["ALERTS TRIGGERED:", *[f"  {a}" for a in stats["alerts"]], ""]
    else:
        lines += ["ALERTS: None — all monitored parameters within normal range.", ""]

    lines += [
        "SAMPLE DATA (first 5 rows of captured session):",
        stats["sample_csv"].strip(),
        "",
        f"QUESTION: {question}",
        "",
        "Respond with a focused diagnostic assessment. "
        "Highlight any issues, explain what they mean for vehicle health, "
        "and provide actionable next steps where applicable.",
    ]

    return "\n".join(lines)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/models", summary="List available Ollama models")
async def list_models():
    """Returns models currently available on the Ollama server."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            resp.raise_for_status()
            raw = resp.json().get("models", [])
            models = [
                {
                    "name":    m["name"],
                    "size_gb": round(m.get("size", 0) / 1_000_000_000, 1),
                }
                for m in raw
            ]
            return {"models": models, "ollama_base": OLLAMA_BASE}
    except httpx.ConnectError:
        raise HTTPException(
            503,
            f"Ollama server unreachable at {OLLAMA_BASE}. "
            "Make sure Ollama is running on the inference host.",
        )
    except Exception as exc:
        raise HTTPException(502, f"Ollama error: {exc}")


@router.post("/analyze", summary="Stream Ollama AI analysis of an OBD-II session")
async def analyze_session(body: AnalyzeRequest):
    """
    Reads the specified (or latest) OBD-II CSV, extracts summary stats
    + rule-based alerts, and streams an Ollama diagnostic analysis as SSE.

    SSE format:
      data: <JSON meta>\\n\\n          ← first event, type="meta"
      data: <token>\\n\\n              ← response tokens
      data: [DONE]\\n\\n               ← completion sentinel
      data: [ERROR] <msg>\\n\\n        ← error (stream closes after)
    """
    csv_path = _find_csv(body.session_filename)
    stats = _summarize_csv(csv_path)
    prompt = _build_prompt(stats, body.question)

    payload = {
        "model":  body.model,
        "prompt": prompt,
        "stream": True,
        "options": {
            "temperature": 0.3,
            "num_predict": 1024,
        },
    }

    async def event_stream():
        # First event: session metadata so the client can display context
        meta = {
            "type":         "meta",
            "session":      stats["session_date"],
            "filename":     stats["filename"],
            "model":        body.model,
            "sample_count": stats["sample_count"],
            "duration_min": stats["duration_min"],
            "alerts":       stats["alerts"],
        }
        yield f"data: {json.dumps(meta)}\n\n"

        try:
            timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", f"{OLLAMA_BASE}/api/generate", json=payload
                ) as resp:
                    if resp.status_code != 200:
                        body_bytes = await resp.aread()
                        msg = body_bytes[:300].decode(errors="replace")
                        yield f"data: [ERROR] Ollama returned HTTP {resp.status_code}: {msg}\n\n"
                        yield "data: [DONE]\n\n"
                        return

                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        token = chunk.get("response", "")
                        if token:
                            # Escape embedded newlines so SSE framing is preserved
                            yield f"data: {token.replace(chr(10), '\\n')}\n\n"

                        if chunk.get("done"):
                            break

        except httpx.ConnectError:
            yield f"data: [ERROR] Cannot reach Ollama at {OLLAMA_BASE}. Is it running?\n\n"
        except httpx.ReadTimeout:
            yield "data: [ERROR] Ollama timed out. Try a smaller/faster model.\n\n"
        except Exception as exc:
            yield f"data: [ERROR] {str(exc)[:300]}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive",
        },
    )
