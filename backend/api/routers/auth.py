"""
auth.py - Account endpoints for web and Android.

Supabase is the single source of truth for authentication.
This router provides:
  - POST /register  — create a local account record (bcrypt password)
  - POST /login     — verify password (bcrypt), return account JSON
  - POST /sync      — upsert account snapshot across web/Android
  - POST /lookup    — get account by email (no password returned)
  - GET  /me        — return profile for a Supabase-authenticated user (JWT required)

The app_user_accounts table is the shared account store. It bridges web and
Android until Supabase Auth is fully propagated everywhere.

Password security: bcrypt via passlib. Timing-safe comparison via
passlib.context.CryptContext.verify().
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from pydantic import BaseModel, Field, field_validator

from api.deps import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ---------------------------------------------------------------------------
# Password hashing (bcrypt, cost factor 12)
# ---------------------------------------------------------------------------

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def _hash_password(plaintext: str) -> str:
    return _pwd_ctx.hash(plaintext)


def _verify_password(plaintext: str, hashed: str) -> bool:
    """Timing-safe bcrypt verification. Returns False on any error."""
    try:
        return _pwd_ctx.verify(plaintext, hashed)
    except Exception:
        return False


def _is_bcrypt(value: str | None) -> bool:
    """True if value looks like a bcrypt hash (starts with $2b$ or $2a$)."""
    return bool(value and value.startswith(("$2b$", "$2a$")))


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class AuthPayload(BaseModel):
    email: str
    password: str | None = Field(default=None, min_length=0, max_length=256)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("A valid email is required.")
        return normalized


class RegisterRequest(AuthPayload):
    password: str = Field(..., min_length=8, max_length=256)
    account: dict[str, Any]


class SyncRequest(AuthPayload):
    account: dict[str, Any]


class LoginRequest(AuthPayload):
    password: str = Field(..., min_length=1, max_length=256)


class LookupRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("A valid email is required.")
        return normalized


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def _open_db_connection() -> asyncpg.Connection:
    try:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not configured")
        return await asyncpg.connect(DATABASE_URL)
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Database not available: {exc}")


async def _ensure_auth_schema(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_user_accounts (
            id           TEXT PRIMARY KEY,
            email        TEXT NOT NULL UNIQUE,
            username     TEXT,
            display_name TEXT,
            pw_hash      TEXT,
            account_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_app_user_accounts_email ON app_user_accounts(email)"
    )


def _decode_account(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def _sanitize_account(account: dict[str, Any], email: str) -> dict[str, Any]:
    """Strip any client-sent password fields before storing."""
    cleaned = dict(account)
    cleaned["email"] = email
    for key in ("_pwHash", "pwHash", "password", "password_hash"):
        cleaned.pop(key, None)
    return cleaned


def _safe_account_response(account: dict[str, Any], email: str) -> dict[str, Any]:
    """Return account dict with email set — never include password or hash."""
    resp = dict(account)
    resp["email"] = email
    for key in ("_pwHash", "pwHash", "password", "password_hash", "pw_hash"):
        resp.pop(key, None)
    return resp


async def _fetch_account_row(conn: asyncpg.Connection, email: str) -> asyncpg.Record | None:
    return await conn.fetchrow(
        "SELECT id, email, username, display_name, pw_hash, account_json FROM app_user_accounts WHERE email = $1",
        email,
    )


def _provider_name(account: dict[str, Any]) -> str | None:
    provider = account.get("provider")
    return provider if isinstance(provider, str) and provider else None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_account(body: RegisterRequest):
    """
    Create a new account. Password is bcrypt-hashed before storage.
    Returns the account JSON — never includes the hash.
    """
    conn = await _open_db_connection()
    try:
        await _ensure_auth_schema(conn)
        existing = await _fetch_account_row(conn, body.email)
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")

        pw_hash = _hash_password(body.password)
        account = _sanitize_account(body.account, body.email)

        await conn.execute(
            """
            INSERT INTO app_user_accounts (id, email, username, display_name, pw_hash, account_json)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            """,
            str(uuid.uuid4()),
            body.email,
            account.get("username"),
            account.get("displayName") or account.get("username"),
            pw_hash,
            json.dumps(account),
        )
        return {"status": "registered", "account": _safe_account_response(account, body.email)}
    finally:
        await conn.close()


@router.post("/login")
async def login_account(body: LoginRequest):
    """
    Authenticate with email + password. Uses timing-safe bcrypt verification.
    Returns account JSON — never includes password hash.
    """
    conn = await _open_db_connection()
    try:
        await _ensure_auth_schema(conn)
        row = await _fetch_account_row(conn, body.email)
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No account found for that email.")

        account      = _decode_account(row["account_json"])
        stored_hash  = row["pw_hash"]
        provider     = _provider_name(account)

        if not stored_hash:
            if provider:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"This account was created with {provider}. Please sign in via that provider.",
                )
            # No password stored yet — set it now (first-time migration)
            new_hash = _hash_password(body.password)
            await conn.execute(
                "UPDATE app_user_accounts SET pw_hash = $2, updated_at = NOW() WHERE email = $1",
                body.email, new_hash,
            )
        elif _is_bcrypt(stored_hash):
            if not _verify_password(body.password, stored_hash):
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect password.")
        else:
            # Legacy plaintext hash — migrate to bcrypt on successful login
            if stored_hash != body.password:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect password.")
            new_hash = _hash_password(body.password)
            await conn.execute(
                "UPDATE app_user_accounts SET pw_hash = $2, updated_at = NOW() WHERE email = $1",
                body.email, new_hash,
            )

        return {"status": "ok", "account": _safe_account_response(account, body.email)}
    finally:
        await conn.close()


@router.post("/sync")
async def sync_account(body: SyncRequest):
    """
    Upsert account snapshot (web ↔ Android). Never overwrites a bcrypt hash
    with a client-provided value. Password field is ignored in sync — use
    /register or /login to set passwords.
    """
    conn = await _open_db_connection()
    try:
        await _ensure_auth_schema(conn)
        account  = _sanitize_account(body.account, body.email)
        existing = await _fetch_account_row(conn, body.email)

        if existing:
            # Preserve existing bcrypt hash — never overwrite with client data
            await conn.execute(
                """
                UPDATE app_user_accounts
                SET username     = $2,
                    display_name = $3,
                    account_json = $4::jsonb,
                    updated_at   = NOW()
                WHERE email = $1
                """,
                body.email,
                account.get("username"),
                account.get("displayName") or account.get("username"),
                json.dumps(account),
            )
        else:
            await conn.execute(
                """
                INSERT INTO app_user_accounts (id, email, username, display_name, account_json)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                """,
                str(uuid.uuid4()),
                body.email,
                account.get("username"),
                account.get("displayName") or account.get("username"),
                json.dumps(account),
            )

        return {"status": "synced", "account": _safe_account_response(account, body.email)}
    finally:
        await conn.close()


@router.post("/lookup")
async def lookup_account(body: LookupRequest):
    """Get account metadata by email — never returns password hash."""
    conn = await _open_db_connection()
    try:
        await _ensure_auth_schema(conn)
        row = await _fetch_account_row(conn, body.email)
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No account found for that email.")

        account = _decode_account(row["account_json"])
        return {"status": "ok", "account": _safe_account_response(account, body.email)}
    finally:
        await conn.close()


@router.get("/me")
async def get_me(claims: dict = Depends(get_current_user)):
    """
    Return the profile for the authenticated Supabase user.
    Auto-creates a stub row in app_user_accounts on first call.
    Requires: Authorization: Bearer <supabase_access_token>
    """
    email        = claims.get("email") or ""
    supabase_uid = claims.get("supabase_uid", "")
    internal_id  = str(claims.get("id") or "")

    conn = await _open_db_connection()
    try:
        await _ensure_auth_schema(conn)

        # Upsert by supabase_uid (stored as id) or email — whichever is available
        await conn.execute(
            """
            INSERT INTO app_user_accounts (id, email, account_json)
            VALUES ($1, $2, $3::jsonb)
            ON CONFLICT (email) DO NOTHING
            """,
            internal_id or str(uuid.uuid4()),
            email,
            json.dumps({"email": email}),
        )

        row     = await _fetch_account_row(conn, email)
        account = _decode_account(row["account_json"]) if row else {"email": email}
        return {
            "status":  "ok",
            "account": _safe_account_response(account, email),
            "user_id": internal_id,
        }
    finally:
        await conn.close()
