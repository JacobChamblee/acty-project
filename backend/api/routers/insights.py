"""
insights.py — BYOK insight generation + SSE streaming endpoints.

POST /api/v1/insights/generate
  Returns 202 Accepted + job_id immediately. Never blocks on LLM.
  Starts background async task for LLM generation.

GET  /api/v1/insights/stream/{job_id}
  SSE endpoint — streams tokens as they arrive from the LLM provider.
  Tier 3 output only. Tier 4 (LSTM) delivered separately when ready.

Pipeline integration:
  This router calls the existing server.py pipeline functions for Tier 1 + Tier 2
  results and wraps them into a CactusPrompt via prompt_builder.py before
  any call to the LLM layer.

Job store:
  Uses asyncio.Queue in a module-level dict for single-instance dev operation.
  Production: replace with Redis pub/sub (each instance subscribes to job channel).
  The interface is identical — swap _job_store for a Redis-backed implementation.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from llm.prompt_builder import build_prompt
from llm.providers import CactusPrompt, get_provider

from .llm_config import VALID_PROVIDERS, current_user_id, fetch_decrypted_key, get_db_connection, mark_key_used

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])

# ── Job store (dev: in-memory asyncio.Queue) ──────────────────────────────────
# Production: replace with Redis pub/sub. Client subscribes to job channel.
# Each token published to channel is forwarded to the SSE response.

_job_store: dict[str, asyncio.Queue] = {}
_job_meta: dict[str, dict] = {}
_JOB_TTL_SECONDS = 600  # 10 minutes


def _new_job(job_id: str, provider: str, model_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=2048)
    _job_store[job_id] = q
    _job_meta[job_id] = {
        "provider": provider,
        "model_id": model_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }
    return q


def _get_job_queue(job_id: str) -> asyncio.Queue:
    q = _job_store.get(job_id)
    if q is None:
        raise HTTPException(404, f"Job {job_id!r} not found or expired")
    return q


# ── Schemas ────────────────────────────────────────────────────────────────────

class InsightRequest(BaseModel):
    vehicle_id: str
    session_filename: Optional[str] = None  # if None, use latest session for vehicle
    user_query: str = "Summarize the key findings from this drive session."
    provider: Optional[str] = None          # None → use local fallback
    model_id: Optional[str] = None          # None → provider default


class InsightJobResponse(BaseModel):
    job_id: str
    provider: str
    model_id: str
    stream_url: str
    created_at: str


# ── Background LLM task ───────────────────────────────────────────────────────

async def _run_llm_generation(
    job_id: str,
    cactus_prompt: CactusPrompt,
    provider_id: str,
    model_id: str,
    api_key: str,
) -> None:
    """
    Runs as a FastAPI BackgroundTask. Streams tokens into the job queue.
    Puts a sentinel None to signal stream completion.
    Puts an Exception instance to signal error (SSE client renders it gracefully).
    """
    q = _job_store.get(job_id)
    if q is None:
        return

    _job_meta[job_id]["status"] = "running"
    try:
        provider = get_provider(provider_id)
        async for token in provider.stream_insight(cactus_prompt, model_id, api_key):
            await q.put(token)
        _job_meta[job_id]["status"] = "complete"
    except Exception as exc:
        _job_meta[job_id]["status"] = "error"
        await q.put(exc)
    finally:
        await q.put(None)  # sentinel — SSE handler closes the stream


# ── Helper: build CactusPrompt from DB + pipeline ─────────────────────────────

async def _build_cactus_prompt(
    vehicle_id: str,
    session_filename: Optional[str],
    user_query: str,
    conn: asyncpg.Connection,
) -> CactusPrompt:
    """
    Pull session summary, LTFT trend, anomaly flags, FSM refs from existing
    pipeline outputs and assemble a CactusPrompt.

    RAG retrieval (Tier 2) calls the rag_server at port 8766.
    If RAG is unreachable, FSM references degrade gracefully to empty list.
    """
    import httpx
    import os

    # --- vehicle context ---
    vehicle = await conn.fetchrow(
        "SELECT make, model, year, engine FROM vehicles WHERE vehicle_id = $1",
        vehicle_id,
    )
    if not vehicle:
        raise HTTPException(404, f"Vehicle {vehicle_id!r} not found")

    # --- session to analyze ---
    if session_filename:
        session = await conn.fetchrow(
            "SELECT * FROM sessions WHERE vehicle_id = $1 AND filename = $2",
            vehicle_id, session_filename,
        )
    else:
        session = await conn.fetchrow(
            "SELECT * FROM sessions WHERE vehicle_id = $1 ORDER BY session_date DESC, session_time DESC LIMIT 1",
            vehicle_id,
        )
    if not session:
        raise HTTPException(404, f"No sessions found for vehicle {vehicle_id!r}")

    session_id = session["id"]

    # --- anomaly flags from Tier 1 ---
    anomaly_rows = await conn.fetch(
        """
        SELECT method, anomaly_score, is_anomaly, flagged_pids, details
        FROM anomaly_results WHERE session_id = $1
        """,
        session_id,
    )
    anomaly_flags = [
        {
            "name": r["method"],
            "confidence": float(r["anomaly_score"]) if r["anomaly_score"] else None,
            "description": (r["details"] or {}).get("message", ""),
            "severity": "warning" if r["is_anomaly"] else "info",
            "flagged_pids": r["flagged_pids"] or [],
        }
        for r in anomaly_rows
        if r["is_anomaly"]
    ]

    # --- also pull rule-based alerts as anomaly flags ---
    alert_rows = await conn.fetch(
        "SELECT pid, label, severity, value, unit, message FROM alerts WHERE session_id = $1",
        session_id,
    )
    for a in alert_rows:
        anomaly_flags.append({
            "name": a["label"],
            "pid": a["pid"],
            "confidence": None,
            "description": a["message"] or f"{a['label']}: {a['value']}{a['unit']}",
            "severity": a["severity"],
        })

    # --- cross-session LTFT trend ---
    ltft_rows = await conn.fetch(
        """
        SELECT ltft_b1, session_date FROM sessions
        WHERE vehicle_id = $1 AND ltft_b1 IS NOT NULL
        ORDER BY session_date, session_time
        """,
        vehicle_id,
    )
    ltft_values = [float(r["ltft_b1"]) for r in ltft_rows]
    n_sessions = len(ltft_values)
    direction = "stable"
    rate = None
    if n_sessions >= 2:
        delta = ltft_values[-1] - ltft_values[0]
        rate = round(delta / (n_sessions - 1), 4)
        if delta < -0.5:
            direction = "worsening lean"
        elif delta > 0.5:
            direction = "improving"

    ltft_trend = {
        "n_sessions": n_sessions,
        "values": ltft_values,
        "direction": direction,
        "rate_per_session": rate,
    }

    # --- total session count for this vehicle ---
    total_sessions = await conn.fetchval(
        "SELECT COUNT(*) FROM sessions WHERE vehicle_id = $1",
        vehicle_id,
    )

    # --- previous reports summary ---
    prev_reports = await conn.fetch(
        """
        SELECT report_text, created_at FROM diagnostic_reports
        WHERE vehicle_id = $1 ORDER BY created_at DESC LIMIT 3
        """,
        vehicle_id,
    )
    prev_summary = None
    if prev_reports:
        snippets = [r["report_text"][:200] for r in prev_reports if r["report_text"]]
        if snippets:
            prev_summary = " | ".join(snippets)

    # --- RAG retrieval (Tier 2) — degrade gracefully if unreachable ---
    rag_url = os.environ.get("CACTUS_RAG_URL", "http://localhost:8766")
    fsm_refs = []
    # Build RAG query from anomaly flags + vehicle info
    rag_query = f"{vehicle['make']} {vehicle['model']} {vehicle['year']} {vehicle['engine']} " + " ".join(
        f["name"] for f in anomaly_flags[:3]
    )
    if not rag_query.strip():
        rag_query = f"{vehicle['make']} {vehicle['model']} diagnostic"

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(f"{rag_url}/retrieve", json={"query": rag_query, "top_k": 5})
            if resp.status_code == 200:
                chunks = resp.json().get("chunks", [])
                fsm_refs = [
                    {
                        "section": c.get("source", "?"),
                        "page": c.get("page", "?"),
                        "spec_value": "",
                        "description": c.get("text", "")[:300],
                    }
                    for c in chunks
                ]
    except Exception:
        # RAG unavailable — prompt_builder will insert reduced-confidence note
        fsm_refs = []

    # asyncpg.Record does not implement .get() — use dict() conversion or key check
    session_dict = dict(session)
    vehicle_context = {
        "make": vehicle["make"],
        "model": vehicle["model"],
        "year": vehicle["year"],
        "engine": vehicle["engine"],
        "odometer_km": session_dict.get("odometer_km"),
    }

    session_summary = session_dict
    session_summary.pop("id", None)
    session_summary.pop("vehicle_id", None)
    # drive_type heuristic from pct_time_moving
    pct = session_summary.get("pct_time_moving", 50)
    session_summary["drive_type"] = (
        "highway" if pct and pct > 75
        else "city" if pct and pct < 40
        else "mixed"
    )

    return build_prompt(
        vehicle_context=vehicle_context,
        session_summary=session_summary,
        ltft_trend=ltft_trend,
        anomaly_flags=anomaly_flags,
        fsm_references=fsm_refs,
        user_query=user_query,
        session_count=int(total_sessions),
        fleet_pattern_match=None,    # Tier 5 FL — not yet implemented
        lstm_reconstruction=None,    # Tier 4 — delivered async separately
        previous_reports_summary=prev_summary,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=InsightJobResponse,
    summary="Submit insight generation request (non-blocking)",
)
async def generate_insight(
    body: InsightRequest,
    background_tasks: BackgroundTasks,
    user_id: uuid.UUID = Depends(current_user_id),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    # Resolve provider + api_key
    provider_id = body.provider
    model_id = body.model_id or ""

    if provider_id and provider_id not in VALID_PROVIDERS:
        raise HTTPException(400, f"Unknown provider: {provider_id!r}")

    if provider_id:
        # BYOK path: decrypt key, record last_used_at
        try:
            api_key = await fetch_decrypted_key(user_id, provider_id, conn)
        except HTTPException:
            # Key not found — degrade to local fallback, note it in response
            provider_id = "local"
            api_key = ""
        else:
            # Confirm model is supported by this provider
            try:
                prov = get_provider(provider_id)
                if model_id not in prov.supported_models:
                    model_id = prov.supported_models[0]
            except ValueError:
                provider_id = "local"
                api_key = ""
    else:
        # No provider specified → local fallback
        provider_id = "local"
        api_key = ""

    if not model_id:
        model_id = get_provider(provider_id).supported_models[0]

    # Build the CactusPrompt from pipeline outputs
    try:
        cactus_prompt = await _build_cactus_prompt(
            body.vehicle_id, body.session_filename, body.user_query, conn
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Pipeline error building prompt: {exc}")

    # Create job + start background generation
    job_id = str(uuid.uuid4())
    _new_job(job_id, provider_id, model_id)

    background_tasks.add_task(
        _run_llm_generation,
        job_id, cactus_prompt, provider_id, model_id, api_key,
    )

    # Mark key as used (fire-and-forget, don't block 202 response)
    if provider_id != "local":
        background_tasks.add_task(mark_key_used, user_id, provider_id, conn)

    return InsightJobResponse(
        job_id=job_id,
        provider=provider_id,
        model_id=model_id,
        stream_url=f"/api/v1/insights/stream/{job_id}",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "/stream/{job_id}",
    summary="SSE stream for insight generation job (Tier 3 LLM output)",
)
async def stream_insight(job_id: str):
    """
    Server-Sent Events endpoint. Client connects after receiving the 202 job_id.
    Yields tokens as the LLM produces them.

    SSE format:
      data: <token>\n\n
      data: [DONE]\n\n  (on completion)
      data: [ERROR] <message>\n\n  (on failure — degrades gracefully)
    """
    q = _get_job_queue(job_id)
    meta = _job_meta.get(job_id, {})

    async def event_stream() -> AsyncGenerator[str, None]:
        # Send job metadata as first event
        yield f"data: {json.dumps({'type': 'meta', 'provider': meta.get('provider'), 'model_id': meta.get('model_id')})}\n\n"

        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=90.0)
            except asyncio.TimeoutError:
                yield "data: [ERROR] Generation timed out after 90s\n\n"
                break

            if item is None:
                # Sentinel — generation complete
                yield "data: [DONE]\n\n"
                # Clean up job state after completion
                _job_store.pop(job_id, None)
                _job_meta.pop(job_id, None)
                break

            if isinstance(item, Exception):
                # Provider failed — degrade gracefully, don't 500
                error_msg = str(item)[:200]
                yield f"data: [ERROR] {error_msg}\n\n"
                yield "data: [DONE]\n\n"
                _job_store.pop(job_id, None)
                _job_meta.pop(job_id, None)
                break

            # Normal token — escape newlines within the SSE data field
            token = str(item).replace("\n", "\\n")
            yield f"data: {token}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
            "Connection": "keep-alive",
        },
    )


@router.get("/job/{job_id}/status", summary="Poll job status (use SSE stream instead when possible)")
async def job_status(job_id: str):
    meta = _job_meta.get(job_id)
    if meta is None:
        raise HTTPException(404, f"Job {job_id!r} not found or expired")
    return meta
