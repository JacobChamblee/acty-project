"""
truenas_writer.py — Cold-storage archiver for TrueNAS (192.168.68.125).

Docker Compose mounts the TrueNAS SMB shares at the paths below.
All writes are fire-and-forget: if the NAS is offline or unmounted
the function logs a warning and returns cleanly. PostgreSQL remains
the authoritative hot store.

Mount points (set in .env → docker-compose.yml → container):
  /mnt/data1/share1/sessions   ← session JSON summaries
  /mnt/data1/share1/reports    ← diagnostic report text
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

SESSION_STORE = Path(os.environ.get("ACTY_SESSION_STORE", "/mnt/data1/share1/sessions"))
REPORT_STORE  = Path(os.environ.get("ACTY_REPORT_STORE",  "/mnt/data1/share1/reports"))
CSV_STORE     = Path(os.environ.get("ACTY_CSV_STORE",     "/mnt/data1/share1/csvs"))


async def archive_session(session_filename: str, data: dict) -> None:
    """
    Write a session summary JSON to TrueNAS cold storage.

    File pattern: sessions/<filename_stem>_<UTC timestamp>.json
    """
    try:
        SESSION_STORE.mkdir(parents=True, exist_ok=True)
        stem = Path(session_filename).stem
        ts   = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest = SESSION_STORE / f"{stem}_{ts}.json"
        dest.write_text(json.dumps(data, default=str, indent=2), encoding="utf-8")
        log.info("[truenas] session archived → %s", dest)
    except OSError as exc:
        log.warning("[truenas] session archive skipped (NAS offline?): %s", exc)


async def archive_csv(filename: str, raw_bytes: bytes) -> None:
    """
    Write a raw OBD-II CSV to TrueNAS cold storage.

    File pattern: csvs/<filename>
    The filename is used as-is so it can be matched to session DB records.
    """
    if not raw_bytes:
        return
    try:
        CSV_STORE.mkdir(parents=True, exist_ok=True)
        dest = CSV_STORE / filename
        dest.write_bytes(raw_bytes)
        log.info("[truenas] csv archived → %s", dest)
    except OSError as exc:
        log.warning("[truenas] csv archive skipped (NAS offline?): %s", exc)


async def archive_report(vehicle_id: str, report_text: str) -> None:
    """
    Write a diagnostic report to TrueNAS cold storage.

    File pattern: reports/<vehicle_id>_<UTC timestamp>.txt
    """
    if not report_text:
        return
    try:
        REPORT_STORE.mkdir(parents=True, exist_ok=True)
        safe_vid = str(vehicle_id).replace("/", "_")
        ts       = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest     = REPORT_STORE / f"{safe_vid}_{ts}.txt"
        dest.write_text(report_text, encoding="utf-8")
        log.info("[truenas] report archived → %s", dest)
    except OSError as exc:
        log.warning("[truenas] report archive skipped (NAS offline?): %s", exc)
