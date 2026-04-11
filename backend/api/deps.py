"""
deps.py — FastAPI shared dependencies.

Provides:
  - get_current_user()  Validates Supabase JWT and returns the internal user
                        dict (id, supabase_uid, email). Creates the users row
                        on first login so every authenticated request is
                        guaranteed to have a DB-backed identity.
"""

from __future__ import annotations

import os

import asyncpg
from fastapi import Header, HTTPException, status
from jose import JWTError, jwt

SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")
DATABASE_URL        = os.environ.get("DATABASE_URL", "")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _verify_jwt(token: str) -> dict:
    """Validate a Supabase-issued JWT. Raises 401 on any failure."""
    if not SUPABASE_JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SUPABASE_JWT_SECRET is not configured on the server.",
        )
    try:
        return jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_exp": True},
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
        )


async def _ensure_user_exists(conn: asyncpg.Connection, supabase_uid: str, email: str | None) -> dict:
    """
    Return the users row for this Supabase UID, creating it on first login.
    Guarantees every authenticated request has an internal user record.
    """
    row = await conn.fetchrow(
        "SELECT id, supabase_uid, email_hint FROM users WHERE supabase_uid = $1",
        supabase_uid,
    )
    if row:
        return dict(row)

    # First login — create the users row
    email_hint = None
    if email and len(email) >= 8:
        local = email.split("@")[0]
        email_hint = (local[:4] + local[-4:])[:8] if len(local) >= 8 else local[:8]

    row = await conn.fetchrow(
        """
        INSERT INTO users (supabase_uid, email_hint)
        VALUES ($1, $2)
        ON CONFLICT (supabase_uid) DO UPDATE
            SET email_hint = EXCLUDED.email_hint
        RETURNING id, supabase_uid, email_hint
        """,
        supabase_uid,
        email_hint,
    )
    return dict(row)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_current_user(
    authorization: str | None = Header(default=None),
) -> dict:
    """
    FastAPI dependency: validates the Supabase JWT in the Authorization header,
    ensures a users row exists, and returns:
        {
            "id":           UUID (internal users.id),
            "supabase_uid": str (Supabase auth.uid()),
            "email_hint":   str | None,
            "email":        str | None,   # from JWT claims, not stored
        }

    Usage::

        @router.get("/sessions")
        async def list_sessions(user: dict = Depends(get_current_user)):
            user_id = user["id"]   # internal UUID for DB queries
            ...
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header (expected: Bearer <token>)",
        )

    token  = authorization.removeprefix("Bearer ").strip()
    claims = _verify_jwt(token)

    supabase_uid = claims.get("sub", "")
    email        = (claims.get("email") or "").lower() or None

    if not supabase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT is missing the 'sub' claim.",
        )

    if not DATABASE_URL:
        # No DB — return claims only (useful for health check endpoints)
        return {"id": None, "supabase_uid": supabase_uid, "email_hint": None, "email": email}

    conn = None
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        user = await _ensure_user_exists(conn, supabase_uid, email)
        return {**user, "email": email}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not resolve user identity: {exc}",
        )
    finally:
        if conn:
            await conn.close()
