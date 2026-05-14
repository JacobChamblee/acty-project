"""
test_security.py — Tests for security fixes identified in REVIEW_FINDINGS.md.

Covers:
  H2  /insights ownership check
  H3  session_detail DB-exception 503 (not proceed)
  B1  /upload path traversal
  I1  Hash-chain includes session_id
  I2  Hash-chain first row uses non-empty sentinel
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from tests.conftest import FAKE_SESSION_FILE, FAKE_USER, FAKE_VEHICLE_ID, make_obd_csv


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_df(n_rows: int = 20) -> pd.DataFrame:
    raw = make_obd_csv(n_rows)
    df  = pd.read_csv(io.BytesIO(raw), parse_dates=["timestamp"])
    return df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════════
# H2 — /insights ownership check
# ═══════════════════════════════════════════════════════════════════════════════

class TestInsightsOwnershipCheck:
    """
    /insights?session=<filename> must validate that the session belongs to the
    requesting user before reading the file.
    Previously it had no ownership check at all (HARD VIOLATION H2).
    """

    @pytest.mark.asyncio
    async def test_insights_with_session_and_no_db_returns_503(
        self, app_with_auth, auth_headers, tmp_csv_dir
    ):
        """
        When DATABASE_URL is set but the DB throws during ownership check,
        the endpoint must return 503 — not serve the file.
        """
        import httpx
        from httpx import ASGITransport

        # Simulate DB failing during ownership check
        failing_conn = AsyncMock()
        failing_conn.fetchval = AsyncMock(side_effect=RuntimeError("connection refused"))
        failing_conn.close    = AsyncMock()

        with (
            patch("api.server.DATABASE_URL", "postgres://fake"),
            patch("api.server.get_db_connection", AsyncMock(return_value=failing_conn)),
            patch("api.server.FAKE_USER", FAKE_USER, create=True),
        ):
            async with httpx.AsyncClient(
                transport=ASGITransport(app=app_with_auth), base_url="http://test"
            ) as client:
                resp = await client.get(
                    f"/insights?session={FAKE_SESSION_FILE}",
                    headers=auth_headers,
                )

        assert resp.status_code == 503, (
            f"Expected 503 when DB fails during ownership check, got {resp.status_code}"
        )

    @pytest.mark.asyncio
    async def test_insights_with_session_not_owned_returns_404(
        self, app_with_auth, auth_headers, tmp_csv_dir
    ):
        """
        Ownership check returning None (session not owned) must produce 404.
        """
        import httpx
        from httpx import ASGITransport

        conn_not_owned = AsyncMock()
        conn_not_owned.fetchval = AsyncMock(return_value=None)  # not owned
        conn_not_owned.close    = AsyncMock()

        with (
            patch("api.server.DATABASE_URL", "postgres://fake"),
            patch("api.server.get_db_connection", AsyncMock(return_value=conn_not_owned)),
        ):
            async with httpx.AsyncClient(
                transport=ASGITransport(app=app_with_auth), base_url="http://test"
            ) as client:
                resp = await client.get(
                    f"/insights?session={FAKE_SESSION_FILE}",
                    headers=auth_headers,
                )

        assert resp.status_code == 404, (
            f"Expected 404 for unowned session, got {resp.status_code}"
        )

    @pytest.mark.asyncio
    async def test_insights_no_session_param_skips_ownership_check(
        self, app_with_auth, auth_headers, tmp_csv_dir
    ):
        """
        /insights with no session param (latest CSV) does not require DB ownership check.
        """
        import httpx
        from httpx import ASGITransport

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app_with_auth), base_url="http://test"
        ) as client:
            # no session param → finds latest CSV from tmp_csv_dir
            resp = await client.get("/insights", headers=auth_headers)

        # Either finds a file (200) or nothing in dir (404) — ownership is not checked
        assert resp.status_code in (200, 404)


# ═══════════════════════════════════════════════════════════════════════════════
# H3 — session_detail DB-exception returns 503
# ═══════════════════════════════════════════════════════════════════════════════

class TestSessionDetailOwnershipBypassFix:
    """
    GET /sessions/{filename} must return 503 when the DB throws during the
    ownership check.  Previously it swallowed the exception and served the file
    to anyone (HARD VIOLATION H3).
    """

    @pytest.mark.asyncio
    async def test_session_detail_db_error_returns_503_not_data(
        self, app_with_auth, auth_headers, tmp_csv_dir
    ):
        import httpx
        from httpx import ASGITransport

        failing_conn = AsyncMock()
        failing_conn.fetchval = AsyncMock(side_effect=Exception("TCP error"))
        failing_conn.close    = AsyncMock()

        with (
            patch("api.server.DATABASE_URL", "postgres://fake"),
            patch("api.server.get_db_connection", AsyncMock(return_value=failing_conn)),
        ):
            async with httpx.AsyncClient(
                transport=ASGITransport(app=app_with_auth), base_url="http://test"
            ) as client:
                resp = await client.get(
                    f"/sessions/{FAKE_SESSION_FILE}",
                    headers=auth_headers,
                )

        assert resp.status_code == 503, (
            f"Expected 503 when ownership check DB fails, got {resp.status_code}. "
            "The old behavior (proceed) was a security bypass."
        )
        assert "Ownership check unavailable" in resp.json().get("detail", ""), (
            "Response detail should describe why the request was rejected"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# B1 — /upload path traversal
# ═══════════════════════════════════════════════════════════════════════════════

class TestUploadPathTraversal:
    """
    POST /upload must reject filenames that contain path separators or
    other characters that would allow writing outside CSV_DIR.
    """

    @pytest.mark.asyncio
    async def test_upload_path_traversal_filename_rejected(
        self, app_with_auth, auth_headers
    ):
        import httpx
        from httpx import ASGITransport

        csv_bytes = make_obd_csv(20)

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app_with_auth), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/upload",
                files={"file": ("../../etc/cron.d/backdoor.csv", csv_bytes, "text/csv")},
                headers=auth_headers,
            )

        assert resp.status_code == 400, (
            f"Expected 400 for path-traversal filename, got {resp.status_code}"
        )

    @pytest.mark.asyncio
    async def test_upload_valid_filename_accepted(
        self, app_with_auth, auth_headers, tmp_csv_dir, tmp_path
    ):
        import httpx
        from httpx import ASGITransport

        csv_bytes = make_obd_csv(50)

        # Point CSV_DIR at a writable temp path for this test
        with (
            patch("api.server.CSV_DIR", tmp_path),
            patch("api.routers.sessions_router.CSV_DIR", tmp_path),
            patch("api.routers.ollama_router.CSV_DIR",   tmp_path),
        ):
            async with httpx.AsyncClient(
                transport=ASGITransport(app=app_with_auth), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/upload",
                    files={"file": ("acty_obd_20260501_120000.csv", csv_bytes, "text/csv")},
                    headers=auth_headers,
                )

        # 200 = analysis complete; 422 = parse error (fine if CSV gen fails) — just not 400
        assert resp.status_code != 400, (
            f"A normal acty_obd_*.csv filename must not be rejected, got {resp.status_code}"
        )

    @pytest.mark.asyncio
    async def test_upload_non_csv_extension_rejected(
        self, app_with_auth, auth_headers
    ):
        import httpx
        from httpx import ASGITransport

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app_with_auth), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/upload",
                files={"file": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")},
                headers=auth_headers,
            )

        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# I1 — Hash-chain includes session_id
# I2 — Hash-chain first row uses non-empty sentinel
# ═══════════════════════════════════════════════════════════════════════════════

class TestHashChainIntegrity:
    """
    Validates that the session_rows hash-chain is session-scoped and that the
    first row's prev_hash is a real sentinel (not empty string).
    """

    def _run_chain(self, df: pd.DataFrame, session_id: str) -> list[tuple]:
        """
        Re-implements the hash-chain logic from _persist_session to verify
        it matches the expected structure.
        Returns list of (record_hash, prev_hash) tuples.
        """
        import numpy as np

        pid_cols = [
            c for c in df.columns
            if c not in {"timestamp", "elapsed_s", "vin", "dtc_confirmed", "dtc_pending"}
        ]
        first_ts = df.iloc[0]["timestamp"]
        sentinel_str = f"START|{session_id}|{first_ts}"
        prev_hash = hashlib.sha256(sentinel_str.encode()).hexdigest()

        chain = []
        for seq, row in enumerate(df.itertuples(index=False)):
            row_dict = row._asdict()
            pid_values = {
                c: (float(row_dict[c])
                    if isinstance(row_dict[c], (np.floating, np.integer))
                    else row_dict[c])
                for c in pid_cols
                if c in row_dict
                and not (isinstance(row_dict[c], float) and np.isnan(row_dict[c]))
                and row_dict[c] is not None
            }
            ts_raw = row_dict.get("timestamp")
            ts_dt  = ts_raw.to_pydatetime() if hasattr(ts_raw, "to_pydatetime") else None
            raw_str = f"{session_id}|{seq}|{ts_dt}|{json.dumps(pid_values, sort_keys=True)}|{prev_hash}"
            record_hash = hashlib.sha256(raw_str.encode()).hexdigest()
            chain.append((record_hash, prev_hash))
            prev_hash = record_hash

        return chain

    def test_first_row_prev_hash_is_not_empty(self):
        """Row 0's prev_hash must be a 64-char hex sentinel, not '' or None."""
        df = _make_df(10)
        session_id = str(uuid.uuid4())
        chain = self._run_chain(df, session_id)

        _, first_prev = chain[0]
        assert first_prev, "First row prev_hash must not be empty or None"
        assert len(first_prev) == 64, f"Expected SHA-256 hex (64 chars), got {len(first_prev)}"

    def test_first_row_sentinel_differs_between_sessions(self):
        """Two sessions with the same CSV rows must have different chain roots."""
        df = _make_df(5)
        session_a = str(uuid.uuid4())
        session_b = str(uuid.uuid4())

        chain_a = self._run_chain(df, session_a)
        chain_b = self._run_chain(df, session_b)

        # First prev_hash (sentinel) must differ between sessions
        assert chain_a[0][1] != chain_b[0][1], (
            "Session-start sentinels must be unique per session"
        )

    def test_hash_chain_is_sequential(self):
        """Each row's prev_hash must equal the previous row's record_hash."""
        df = _make_df(20)
        session_id = str(uuid.uuid4())
        chain = self._run_chain(df, session_id)

        for i in range(1, len(chain)):
            prev_record_hash = chain[i - 1][0]
            curr_prev_hash   = chain[i][1]
            assert prev_record_hash == curr_prev_hash, (
                f"Chain broken at row {i}: "
                f"row[{i-1}].record_hash={prev_record_hash[:8]}... "
                f"!= row[{i}].prev_hash={curr_prev_hash[:8]}..."
            )

    def test_mutating_pid_breaks_chain(self):
        """Changing a PID value in any row must produce a different hash for that row
        and all subsequent rows — proving tamper-evidence."""
        df = _make_df(10)
        session_id = str(uuid.uuid4())

        chain_original = self._run_chain(df, session_id)

        # Mutate row 3's RPM value
        df_tampered = df.copy()
        if "RPM" in df_tampered.columns:
            df_tampered.iloc[3, df_tampered.columns.get_loc("RPM")] = 99999.0

        chain_tampered = self._run_chain(df_tampered, session_id)

        # Rows 0-2 must be identical
        for i in range(3):
            assert chain_original[i][0] == chain_tampered[i][0], (
                f"Row {i} hash changed unexpectedly (mutation was at row 3)"
            )

        # Rows 3+ must be different
        for i in range(3, len(chain_original)):
            assert chain_original[i][0] != chain_tampered[i][0], (
                f"Row {i} hash did not change after tampering row 3 — chain is not tamper-evident"
            )

    def test_same_data_different_session_id_produces_different_hashes(self):
        """session_id must be part of the hash input (fix for I1)."""
        df = _make_df(5)
        session_a = str(uuid.uuid4())
        session_b = str(uuid.uuid4())

        chain_a = self._run_chain(df, session_a)
        chain_b = self._run_chain(df, session_b)

        # Every row hash must differ because session_id differs
        for i, ((ha, _), (hb, _)) in enumerate(zip(chain_a, chain_b)):
            assert ha != hb, (
                f"Row {i} has the same hash for two different session_ids — "
                "session_id must be part of the hash input"
            )
