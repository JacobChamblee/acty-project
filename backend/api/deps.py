"""
deps.py — FastAPI shared dependencies.

Provides get_current_user(), which verifies a Supabase-issued JWT from
the Authorization: Bearer <token> header and returns the decoded claims.
"""

from __future__ import annotations

import os

from fastapi import Header, HTTPException, status
from jose import JWTError, jwt

SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """
    Dependency that validates a Supabase JWT and returns its claims.

    Usage::

        @router.get("/me")
        async def me(claims: dict = Depends(get_current_user)):
            return {"user_id": claims["sub"], "email": claims.get("email")}
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header (expected: Bearer <token>)",
        )

    token = authorization.removeprefix("Bearer ").strip()

    if not SUPABASE_JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SUPABASE_JWT_SECRET is not configured on the server.",
        )

    try:
        claims = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_exp": True},
        )
        return claims
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
        )
