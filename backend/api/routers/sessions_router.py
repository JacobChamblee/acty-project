"""
sessions_router.py — Session sync API for Android clients.

POST /api/v1/sessions/sync
  Accepts the Android SyncManager JSON payload (base64-encoded CSV + sig),
  saves both files to CSV_DIR, runs the same analysis pipeline as /upload,
  and returns the trip report JSON.

GET /api/v1/sessions
  Returns the same list as GET /sessions but as a v1 endpoint (forwards).
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])

CSV_DIR = Path(os.environ.get("ACTY_CSV_DIR", str(Path.home())))


class SyncPayload(BaseModel):
    session_id: str
    vehicle_id: str = "unknown"
    csv_b64: str
    sig_b64: str = ""


@router.post("/sync", summary="Android session sync (JSON + base64 CSV)")
async def sync_session(body: SyncPayload):
    """
    Accepts the Android SyncManager upload format:
      - session_id: filename stem (without .csv)
      - vehicle_id: vehicle pseudonymous ID
      - csv_b64: base64-encoded CSV bytes
      - sig_b64: base64-encoded Ed25519 signature bytes
    Saves CSV (and .sig if present) to CSV_DIR, then runs full trip analysis.
    """
    # Decode CSV
    try:
        csv_bytes = base64.b64decode(body.csv_b64)
    except Exception:
        raise HTTPException(400, "csv_b64 is not valid base64")

    # Ensure filename ends in .csv
    filename = body.session_id if body.session_id.endswith(".csv") else f"{body.session_id}.csv"
    csv_path = CSV_DIR / filename

    # Save sig
    if body.sig_b64:
        try:
            sig_bytes = base64.b64decode(body.sig_b64)
            sig_path = CSV_DIR / (Path(filename).stem + ".sig")
            sig_path.write_bytes(sig_bytes)
        except Exception:
            pass  # sig decode failure is non-fatal

    # Parse CSV
    try:
        df = pd.read_csv(io.BytesIO(csv_bytes), parse_dates=["timestamp"])
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    except Exception as e:
        raise HTTPException(422, f"Could not parse CSV: {e}")

    if len(df) < 5:
        raise HTTPException(422, "CSV has too few rows to analyse.")

    # Save to disk (after parse succeeds)
    csv_path.write_bytes(csv_bytes)

    # Run the same pipeline as /upload (imported lazily to avoid circular deps)
    try:
        from api.server import (
            _compute_trip_report,
            _persist_session,
            summarize_session,
            detect_anomalies,
        )
        from api.storage.truenas_writer import archive_csv

        report = _compute_trip_report(df, filename)

        summary = summarize_session(df, Path(filename))
        alerts  = detect_anomalies(df)
        asyncio.create_task(_persist_session(summary, alerts, report["health_score"]))
        asyncio.create_task(archive_csv(filename, csv_bytes))

        return {"status": "ok", "filename": filename, **report}
    except ImportError as e:
        log.warning("[sync] pipeline import failed: %s — returning minimal response", e)
        return {"status": "ok", "filename": filename}
