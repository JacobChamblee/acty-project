"""
Acty/Cactus MCP Server
======================
Exposes Acty platform capabilities as MCP tools for use with:
  - Claude Code (ThinkPad X280, local dev)
  - @ElPainBot (CM3588, always-on Telegram assistant)
  - claude.ai custom connector (SSE mode, future)

Infrastructure:
  - 4U DIY server (inference + acty-api): 192.168.68.138
  - CM3588 (signing service, reverse proxy): 192.168.68.121
  - TrueNAS (CSV archive, session data):   192.168.68.125
  - RAG server:  http://192.168.68.138:8766
  - acty-api:    http://192.168.68.138:8765
  - Ollama:      http://192.168.68.138:11434
  - PostgreSQL:  192.168.68.138:5432
  - Grafana:     http://192.168.68.138:3000
"""

import asyncio
import os
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import asyncpg
import httpx
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Config — override with environment variables in production
# ---------------------------------------------------------------------------

DB_DSN      = os.getenv("ACTY_DB_DSN",      "postgresql://acty:acty@192.168.68.138:5432/acty")
API_BASE    = os.getenv("ACTY_API_BASE",     "http://192.168.68.138:8765")
RAG_BASE    = os.getenv("ACTY_RAG_BASE",     "http://192.168.68.138:8766")
OLLAMA_BASE = os.getenv("ACTY_OLLAMA_BASE",  "http://192.168.68.138:11434")
VERIFY_BASE = os.getenv("ACTY_VERIFY_BASE",  "https://verify.acty-labs.com")
TRUENAS_CSV = os.getenv("ACTY_TRUENAS_PATH", "//192.168.68.125/share1")

# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Acty",
    instructions=(
        "You have access to the Acty/Cactus vehicle telemetry platform. "
        "Use these tools to query OBD session data, run diagnostics, "
        "generate reports, and verify tamper-evident session records. "
        "Always interpret fuel trim, voltage, and timing data in context of "
        "the vehicle's session history and known baselines."
    ),
)

# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

async def _db_fetch(query: str, *args) -> list[dict]:
    conn = await asyncpg.connect(DB_DSN)
    try:
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]
    finally:
        await conn.close()


# ===========================================================================
# TOOLS — Session & Data Access
# ===========================================================================

@mcp.tool()
async def list_sessions(vehicle_id: str, limit: int = 10) -> list[dict]:
    """
    List recent Acty OBD sessions for a vehicle.

    Args:
        vehicle_id: Vehicle identifier (e.g. 'gr86', 'rav4', 'tacoma')
        limit:      Max sessions to return (default 10)

    Returns list of sessions with id, start_time, end_time, row_count.
    """
    rows = await _db_fetch(
        """
        SELECT s.id, s.vehicle_id, s.started_at, s.ended_at,
               COUNT(sr.id) AS row_count
        FROM sessions s
        LEFT JOIN session_rows sr ON sr.session_id = s.id
        WHERE s.vehicle_id = $1
        GROUP BY s.id
        ORDER BY s.started_at DESC
        LIMIT $2
        """,
        vehicle_id, limit,
    )
    # Serialize datetimes
    for r in rows:
        for k in ("started_at", "ended_at"):
            if r.get(k) and isinstance(r[k], datetime):
                r[k] = r[k].isoformat()
    return rows


@mcp.tool()
async def get_session_summary(session_id: str) -> dict:
    """
    Compute a diagnostic summary for a single Acty session.

    Covers:
      - Fuel trims: avg/min/max STFT and LTFT (normal: STFT ±5%, LTFT ±7.5%)
      - Charging: avg/min voltage (normal: 13.8–14.5V)
      - Timing: avg advance, min (most retarded) event, retard cluster count
      - Thermal: warmup duration to 80°C coolant, max coolant temp
      - Session metadata: duration, row count, vehicle_id

    Args:
        session_id: UUID of the session to summarize
    """
    rows = await _db_fetch(
        """
        SELECT pid, value, recorded_at
        FROM session_rows
        WHERE session_id = $1
        ORDER BY recorded_at ASC
        """,
        session_id,
    )

    if not rows:
        return {"error": f"No rows found for session {session_id}"}

    # Bucket by PID
    pids: dict[str, list[float]] = {}
    for r in rows:
        pid = r["pid"]
        try:
            val = float(r["value"])
        except (TypeError, ValueError):
            continue
        pids.setdefault(pid, []).append(val)

    def _stats(pid_name: str) -> Optional[dict]:
        vals = pids.get(pid_name)
        if not vals:
            return None
        return {
            "avg":   round(statistics.mean(vals), 2),
            "min":   round(min(vals), 2),
            "max":   round(max(vals), 2),
            "count": len(vals),
        }

    # Timing retard clusters: consecutive warm-idle events < 0° advance
    timing_vals = pids.get("TIMING_ADVANCE", [])
    coolant_vals = pids.get("COOLANT_TEMP", [])
    warm_temp = 80.0
    retard_clusters = 0
    in_retard = False
    for v in timing_vals:
        if v < 0:
            if not in_retard:
                retard_clusters += 1
                in_retard = True
        else:
            in_retard = False

    # Warmup duration: rows until coolant first hits 80°C
    warmup_rows = None
    for i, r in enumerate(rows):
        if r["pid"] == "COOLANT_TEMP":
            try:
                if float(r["value"]) >= warm_temp:
                    warmup_rows = i
                    break
            except (TypeError, ValueError):
                pass

    start = rows[0]["recorded_at"]
    end   = rows[-1]["recorded_at"]
    if isinstance(start, datetime) and isinstance(end, datetime):
        duration_s = int((end - start).total_seconds())
    else:
        duration_s = None

    return {
        "session_id":       session_id,
        "row_count":        len(rows),
        "duration_seconds": duration_s,
        "fuel_trims": {
            "STFT_1": _stats("SHORT_FUEL_TRIM_1"),
            "LTFT_1": _stats("LONG_FUEL_TRIM_1"),
        },
        "charging": {
            "voltage": _stats("CONTROL_MODULE_VOLTAGE"),
        },
        "timing": {
            "advance":         _stats("TIMING_ADVANCE"),
            "retard_clusters": retard_clusters,
        },
        "thermal": {
            "coolant_temp":  _stats("COOLANT_TEMP"),
            "warmup_rows_to_80c": warmup_rows,
        },
        "engine": {
            "rpm":    _stats("RPM"),
            "load":   _stats("ENGINE_LOAD"),
            "maf":    _stats("MAF"),
            "speed":  _stats("SPEED"),
        },
    }


@mcp.tool()
async def get_session_pids(session_id: str, pids: list[str]) -> dict[str, list]:
    """
    Return raw time-series values for specific PIDs in a session.
    Useful for plotting or detailed analysis of a subset of channels.

    Args:
        session_id: UUID of the session
        pids:       List of PID names, e.g. ["LONG_FUEL_TRIM_1", "COOLANT_TEMP"]

    Returns dict of {pid: [{recorded_at, value}, ...]}
    """
    placeholders = ", ".join(f"${i+2}" for i in range(len(pids)))
    rows = await _db_fetch(
        f"""
        SELECT pid, value, recorded_at
        FROM session_rows
        WHERE session_id = $1 AND pid IN ({placeholders})
        ORDER BY recorded_at ASC
        """,
        session_id, *pids,
    )
    result: dict[str, list] = {p: [] for p in pids}
    for r in rows:
        ts = r["recorded_at"]
        result[r["pid"]].append({
            "t": ts.isoformat() if isinstance(ts, datetime) else str(ts),
            "v": r["value"],
        })
    return result


@mcp.tool()
async def get_vehicle_history(vehicle_id: str, sessions: int = 20) -> dict:
    """
    Cross-session trend analysis for a vehicle.
    Returns per-session LTFT avg, voltage avg, and peak timing retard
    to identify longitudinal patterns (e.g. worsening lean condition).

    Args:
        vehicle_id: Vehicle identifier
        sessions:   Number of recent sessions to include (default 20)
    """
    rows = await _db_fetch(
        """
        SELECT s.id AS session_id,
               s.started_at,
               sr.pid,
               AVG(CAST(sr.value AS FLOAT)) AS avg_val,
               MIN(CAST(sr.value AS FLOAT)) AS min_val
        FROM sessions s
        JOIN session_rows sr ON sr.session_id = s.id
        WHERE s.vehicle_id = $1
          AND sr.pid IN (
              'LONG_FUEL_TRIM_1', 'SHORT_FUEL_TRIM_1',
              'CONTROL_MODULE_VOLTAGE', 'TIMING_ADVANCE',
              'COOLANT_TEMP'
          )
        GROUP BY s.id, s.started_at, sr.pid
        ORDER BY s.started_at DESC
        LIMIT $2
        """,
        vehicle_id, sessions * 5,  # 5 PIDs × N sessions
    )

    # Pivot into per-session dict
    sessions_map: dict = {}
    for r in rows:
        sid = r["session_id"]
        if sid not in sessions_map:
            sessions_map[sid] = {
                "session_id": sid,
                "started_at": r["started_at"].isoformat() if isinstance(r["started_at"], datetime) else str(r["started_at"]),
            }
        sessions_map[sid][r["pid"]] = {
            "avg": round(r["avg_val"], 2) if r["avg_val"] is not None else None,
            "min": round(r["min_val"], 2) if r["min_val"] is not None else None,
        }

    return {
        "vehicle_id": vehicle_id,
        "sessions":   list(sessions_map.values()),
        "baseline_notes": {
            "LTFT_normal":    "±7.5% (action), ±10% (concern)",
            "voltage_normal": "13.8–14.5V under load",
            "timing_note":    "Warm-idle retard < 0° warrants investigation",
        },
    }


@mcp.tool()
async def list_vehicles() -> list[dict]:
    """
    List all vehicles registered in the Acty platform with their metadata.
    """
    return await _db_fetch(
        "SELECT id, make, model, year, vin, created_at FROM vehicles ORDER BY created_at DESC"
    )


# ===========================================================================
# TOOLS — Diagnostics & AI
# ===========================================================================

@mcp.tool()
async def query_fsm_rag(question: str, vehicle: str = "GR86") -> dict:
    """
    Query the Acty FSM RAG pipeline with a natural language diagnostic question.
    Retrieves relevant passages from GR86/BRZ factory service manuals and
    returns a grounded AI answer.

    Args:
        question: Natural language diagnostic question
                  e.g. "What causes persistent lean LTFT on the FA24?"
        vehicle:  Vehicle model for RAG context (default: GR86)

    Returns answer text plus retrieved source chunks.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{RAG_BASE}/query",
            json={"question": question, "vehicle": vehicle},
        )
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def generate_report(session_id: str, model: str = "deepseek-r1:14b") -> dict:
    """
    Trigger Ollama LLM report generation for an Acty session.
    Calls the acty-api /generate-report endpoint which assembles
    session context, runs the ML pipeline, and queries Ollama.

    Args:
        session_id: UUID of the session to report on
        model:      Ollama model to use (default: deepseek-r1:14b)

    Returns the generated narrative report text and any flagged anomalies.
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{API_BASE}/generate-report",
            json={"session_id": session_id, "model": model},
        )
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def run_anomaly_check(session_id: str) -> dict:
    """
    Trigger the Isolation Forest anomaly detection pass on a session
    via the acty-api /analyze endpoint.

    Returns list of anomalous rows with timestamps and flagged PIDs.

    Args:
        session_id: UUID of the session to analyze
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{API_BASE}/analyze",
            json={"session_id": session_id, "model": "isolation_forest"},
        )
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def ask_ollama(prompt: str, model: str = "llama3.1:8b") -> str:
    """
    Send a raw prompt directly to the local Ollama instance.
    Useful for quick diagnostic reasoning without full report pipeline.

    Args:
        prompt: The prompt to send
        model:  Ollama model (default: llama3.1:8b for speed; use deepseek-r1:14b for depth)
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
        )
        r.raise_for_status()
        return r.json().get("response", "")


# ===========================================================================
# TOOLS — Verification & Integrity
# ===========================================================================

@mcp.tool()
async def verify_session(session_id: str) -> dict:
    """
    Run the 7-layer independent verification of an Acty session record.
    Checks hash-chain integrity, Ed25519 signature, RFC 3161 timestamp
    anchor, and server-side audit log consistency.

    Args:
        session_id: UUID of the session to verify

    Returns verification result with pass/fail per layer.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{VERIFY_BASE}/verify/{session_id}")
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def get_session_manifest(session_id: str) -> dict:
    """
    Retrieve the signed session manifest for a completed session.
    Includes Merkle root of all record hashes, Ed25519 signature,
    and RFC 3161 timestamp token.

    Args:
        session_id: UUID of the session
    """
    rows = await _db_fetch(
        """
        SELECT id, session_id, merkle_root, signature, tsa_token,
               firmware_hash, device_id, created_at
        FROM session_manifests
        WHERE session_id = $1
        """,
        session_id,
    )
    if not rows:
        return {"error": f"No manifest found for session {session_id}"}
    r = rows[0]
    if isinstance(r.get("created_at"), datetime):
        r["created_at"] = r["created_at"].isoformat()
    return r


# ===========================================================================
# TOOLS — TrueNAS / CSV Archive
# ===========================================================================

@mcp.tool()
async def list_csv_archive(vehicle_id: Optional[str] = None) -> list[str]:
    """
    List raw session CSV files on TrueNAS share1 (192.168.68.125).
    Files are organized as: share1/<vehicle_id>/<session_id>.csv

    Args:
        vehicle_id: Filter to a specific vehicle folder (optional)

    Returns list of relative file paths.
    Note: Requires the MCP server to have the TrueNAS share mounted locally.
    """
    mount = Path(os.getenv("ACTY_TRUENAS_MOUNT", "/mnt/truenas/share1"))
    if not mount.exists():
        return [f"TrueNAS share not mounted at {mount}. Mount with: "
                f"mount -t cifs //192.168.68.125/share1 {mount} -o username=...,password=..."]

    search_root = mount / vehicle_id if vehicle_id else mount
    files = sorted(search_root.rglob("*.csv"))
    return [str(f.relative_to(mount)) for f in files]


@mcp.tool()
async def read_csv_head(relative_path: str, rows: int = 5) -> dict:
    """
    Read the first N rows of a raw session CSV from TrueNAS share1.
    Useful for inspecting capture format or debugging ingestion issues.

    Args:
        relative_path: Path relative to share1 root, e.g. 'gr86/session_abc123.csv'
        rows:          Number of rows to return (default 5)
    """
    import csv

    mount = Path(os.getenv("ACTY_TRUENAS_MOUNT", "/mnt/truenas/share1"))
    full_path = mount / relative_path

    if not full_path.exists():
        return {"error": f"File not found: {full_path}"}
    if not full_path.suffix == ".csv":
        return {"error": "Only .csv files supported"}

    result = []
    with open(full_path, newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= rows:
                break
            result.append(row)

    return {"path": relative_path, "rows": result}


# ===========================================================================
# TOOLS — Platform Health
# ===========================================================================

@mcp.tool()
async def platform_health() -> dict:
    """
    Check the health of all Acty/Cactus platform services:
      - PostgreSQL connectivity
      - acty-api (/health)
      - RAG server (/health)
      - Ollama (/api/tags)
      - TrueNAS share mount

    Returns per-service status with latency.
    """
    results = {}

    # PostgreSQL
    try:
        start = asyncio.get_event_loop().time()
        conn = await asyncpg.connect(DB_DSN)
        await conn.fetchval("SELECT 1")
        await conn.close()
        results["postgresql"] = {
            "status": "ok",
            "latency_ms": round((asyncio.get_event_loop().time() - start) * 1000, 1),
        }
    except Exception as e:
        results["postgresql"] = {"status": "error", "error": str(e)}

    # HTTP services
    endpoints = {
        "acty_api":   f"{API_BASE}/health",
        "rag_server": f"{RAG_BASE}/health",
        "ollama":     f"{OLLAMA_BASE}/api/tags",
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in endpoints.items():
            try:
                start = asyncio.get_event_loop().time()
                r = await client.get(url)
                results[name] = {
                    "status": "ok" if r.status_code < 400 else "degraded",
                    "http_status": r.status_code,
                    "latency_ms": round((asyncio.get_event_loop().time() - start) * 1000, 1),
                }
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}

    # TrueNAS mount
    mount = Path(os.getenv("ACTY_TRUENAS_MOUNT", "/mnt/truenas/share1"))
    results["truenas_mount"] = {
        "status": "ok" if mount.exists() else "not_mounted",
        "path": str(mount),
        "smb_target": "//192.168.68.125/share1",
    }

    results["checked_at"] = datetime.now(timezone.utc).isoformat()
    return results


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    mcp.run()