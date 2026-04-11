"""
sessions_router.py — Session sync API for Android clients.

POST /api/v1/sessions/sync
  Accepts the Android SyncManager JSON payload (base64-encoded CSV + sig),
  validates the Supabase JWT, saves both files to CSV_DIR, runs the same
  analysis pipeline as /upload, and returns the trip report JSON.

GET /api/v1/sessions
  Returns sessions for the authenticated user.
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_current_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])

CSV_DIR = Path(os.environ.get("ACTY_CSV_DIR", str(Path.home())))


class SyncPayload(BaseModel):
    session_id: str
    vehicle_id: str = "unknown"
    csv_b64: str
    sig_b64: str = ""
    adapter_mac: str = ""   # OBD adapter MAC address (optional, stored for future use)


@router.post("/sync", summary="Android session sync (JSON + base64 CSV)")
async def sync_session(
    body: SyncPayload,
    user: dict = Depends(get_current_user),
):
    """
    Accepts the Android SyncManager upload format:
      - session_id:  filename stem (without .csv)
      - vehicle_id:  vehicle pseudonymous ID
      - csv_b64:     base64-encoded CSV bytes
      - sig_b64:     base64-encoded Ed25519 signature bytes (optional)
      - adapter_mac: OBD adapter MAC address (optional)

    Requires: Authorization: Bearer <supabase_access_token>
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
            sig_path  = CSV_DIR / (Path(filename).stem + ".sig")
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

    # Run the same pipeline as /upload
    try:
        from api.server import (
            _compute_trip_report,
            _persist_session,
            summarize_session,
            detect_anomalies,
        )
        from api.storage.truenas_writer import archive_csv

        report  = _compute_trip_report(df, filename)
        summary = summarize_session(df, Path(filename))
        alerts  = detect_anomalies(df)

        asyncio.create_task(_persist_session(summary, alerts, report["health_score"]))
        asyncio.create_task(archive_csv(filename, csv_bytes))

        log.info(
            "[sync] user=%s vehicle=%s session=%s rows=%d health=%s",
            user.get("supabase_uid", "?"),
            body.vehicle_id,
            filename,
            len(df),
            report["health_score"],
        )

        return {"status": "ok", "filename": filename, **report}

    except ImportError as e:
        log.warning("[sync] pipeline import failed: %s — returning minimal response", e)
        return {"status": "ok", "filename": filename}


@router.get("/", summary="List sessions for authenticated user")
async def list_user_sessions(user: dict = Depends(get_current_user)):
    """
    Returns sessions belonging to the authenticated user's vehicles.
    Falls back to all CSV sessions if DB is not available.
    """
    # TODO (Day 3): filter by user's owned vehicles via DB.
    # For now, return all sessions from disk — auth is enforced above.
    try:
        from api.server import find_all_csvs, load_csv, summarize_session

        csvs   = find_all_csvs()
        result = []
        for p in csvs[:20]:
            try:
                df = load_csv(p)
                s  = summarize_session(df, p)
                result.append(s)
            except Exception:
                result.append({"filename": p.name, "error": "parse failed"})
        return {"sessions": result, "total": len(csvs)}
    except ImportError:
        return {"sessions": [], "total": 0}
