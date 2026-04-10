"""
auth.py - lightweight shared account endpoints for web and Android.

This is a prototype bridge until Supabase auth lands. It stores account
snapshots in PostgreSQL so the web app and Android app can recognize the same
email/password account instead of each keeping an isolated local registry.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from api.deps import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

DATABASE_URL = os.environ.get("DATABASE_URL", "")


class AuthPayload(BaseModel):
    email: str
    password_hash: str | None = Field(default=None, min_length=0, max_length=256)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("A valid email is required.")
        return normalized


class RegisterRequest(AuthPayload):
    account: dict[str, Any]


class SyncRequest(AuthPayload):
    account: dict[str, Any]


class LoginRequest(AuthPayload):
    password_hash: str = Field(..., min_length=1, max_length=256)


class LookupRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("A valid email is required.")
        return normalized


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
        """
        CREATE INDEX IF NOT EXISTS idx_app_user_accounts_email
        ON app_user_accounts(email)
        """
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
    cleaned = dict(account)
    cleaned["email"] = email
    cleaned.pop("_pwHash", None)
    cleaned.pop("pwHash", None)
    return cleaned


def _normalize_response_account(account: dict[str, Any], email: str, pw_hash: str | None) -> dict[str, Any]:
    normalized = dict(account)
    normalized["email"] = email
    if pw_hash:
        normalized["_pwHash"] = pw_hash
        normalized["pwHash"] = pw_hash
    return normalized


async def _fetch_account_row(conn: asyncpg.Connection, email: str) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        SELECT id, email, username, display_name, pw_hash, account_json
        FROM app_user_accounts
        WHERE email = $1
        """,
        email,
    )


def _provider_name(account: dict[str, Any]) -> str | None:
    provider = account.get("provider")
    return provider if isinstance(provider, str) and provider else None


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_account(body: RegisterRequest):
    conn = await _open_db_connection()
    try:
        await _ensure_auth_schema(conn)
        existing = await _fetch_account_row(conn, body.email)
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")

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
            body.password_hash,
            json.dumps(account),
        )
        return {
            "status": "registered",
            "account": _normalize_response_account(account, body.email, body.password_hash),
            "password_hash": body.password_hash,
        }
    finally:
        await conn.close()


@router.post("/sync")
async def sync_account(body: SyncRequest):
    conn = await _open_db_connection()
    try:
        await _ensure_auth_schema(conn)
        account = _sanitize_account(body.account, body.email)
        existing = await _fetch_account_row(conn, body.email)
        existing_pw_hash = existing["pw_hash"] if existing else None
        pw_hash = body.password_hash or existing_pw_hash

        if existing:
            await conn.execute(
                """
                UPDATE app_user_accounts
                SET username = $2,
                    display_name = $3,
                    pw_hash = $4,
                    account_json = $5::jsonb,
                    updated_at = NOW()
                WHERE email = $1
                """,
                body.email,
                account.get("username"),
                account.get("displayName") or account.get("username"),
                pw_hash,
                json.dumps(account),
            )
        else:
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

        return {
            "status": "synced",
            "account": _normalize_response_account(account, body.email, pw_hash),
            "password_hash": pw_hash,
        }
    finally:
        await conn.close()


@router.post("/login")
async def login_account(body: LoginRequest):
    conn = await _open_db_connection()
    try:
        await _ensure_auth_schema(conn)
        row = await _fetch_account_row(conn, body.email)
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No account found for that email.")

        account = _decode_account(row["account_json"])
        stored_pw_hash = row["pw_hash"]
        provider = _provider_name(account)

        if not stored_pw_hash:
            if provider:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"This account was created with {provider}. Please use that sign-in method on web.",
                )
            stored_pw_hash = body.password_hash
            await conn.execute(
                """
                UPDATE app_user_accounts
                SET pw_hash = $2, updated_at = NOW()
                WHERE email = $1
                """,
                body.email,
                stored_pw_hash,
            )
        elif stored_pw_hash != body.password_hash:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect password.")

        return {
            "status": "ok",
            "account": _normalize_response_account(account, body.email, stored_pw_hash),
            "password_hash": stored_pw_hash,
        }
    finally:
        await conn.close()


@router.post("/lookup")
async def lookup_account(body: LookupRequest):
    conn = await _open_db_connection()
    try:
        await _ensure_auth_schema(conn)
        row = await _fetch_account_row(conn, body.email)
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No account found for that email.")

        account = _decode_account(row["account_json"])
        stored_pw_hash = row["pw_hash"]
        return {
            "status": "ok",
            "account": _normalize_response_account(account, body.email, stored_pw_hash),
            "password_hash": stored_pw_hash,
        }
    finally:
        await conn.close()


@router.get("/me")
async def get_me(claims: dict = Depends(get_current_user)):
    """
    Return the profile for the authenticated Supabase user.
    Creates a stub row in app_user_accounts on first call (upsert by sub).
    Requires: Authorization: Bearer <supabase_access_token>
    """
    email = (claims.get("email") or "").lower()
    sub   = claims.get("sub", str(uuid.uuid4()))

    conn = await _open_db_connection()
    try:
        await _ensure_auth_schema(conn)

        # Upsert — on first login create a minimal row; never overwrite existing data
        await conn.execute(
            """
            INSERT INTO app_user_accounts (id, email, account_json)
            VALUES ($1, $2, $3::jsonb)
            ON CONFLICT (email) DO NOTHING
            """,
            sub,
            email,
            json.dumps({"email": email}),
        )

        row = await _fetch_account_row(conn, email)
        account = _decode_account(row["account_json"]) if row else {"email": email}
        return {"status": "ok", "account": _normalize_response_account(account, email, None)}
    finally:
        await conn.close()
