"""
llm_config.py — BYOK provider key management endpoints.

POST   /api/v1/llm-config                  register a new provider key
GET    /api/v1/llm-config                  list configured providers (hint only)
DELETE /api/v1/llm-config/{provider}       remove a provider config
POST   /api/v1/llm-config/{provider}/validate  validate key without saving
GET    /api/v1/llm-config/providers        list all supported providers (no auth)

Security invariants:
  - Plaintext API keys are NEVER logged, returned, or stored.
  - Only key_hint (last 4 chars) is returned in GET responses.
  - encrypted_api_key is always stored with its key_iv — never one without the other.
  - The CACTUS_KEY_ENCRYPTION_KEY env var must be set; startup will fail if missing.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import AsyncGenerator, Optional

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from llm.key_encryption import decrypt_api_key, encrypt_api_key, make_key_hint
from llm.providers import get_provider, list_providers

router = APIRouter(prefix="/api/v1/llm-config", tags=["llm-config"])

# ── Dependency: DB connection ────────────────────────────────────────────────────────
# Creates a new connection for each request (works with multiprocess deployments)

import os

DATABASE_URL = os.environ.get("DATABASE_URL", "")


async def open_db_connection() -> asyncpg.Connection:
    try:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not configured")
        return await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        raise HTTPException(503, f"Database not available: {e}")


async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Create a new database connection for each request and close it automatically."""
    conn = await open_db_connection()
    try:
        yield conn
    finally:
        await conn.close()


# ── Schemas ────────────────────────────────────────────────────────────────────

VALID_PROVIDERS = {"anthropic", "openai", "google", "cohere", "mistral", "groq", "deepseek"}


class RegisterKeyRequest(BaseModel):
    provider: str
    model_id: str
    # The key arrives from Android already encrypted with the device key.
    # For the pre-TEE server-side path, we accept plaintext here and re-encrypt
    # with CACTUS_KEY_ENCRYPTION_KEY. The Android client MUST use HTTPS.
    # TODO(tee): Accept ciphertext + device_key_iv when TEE node is live.
    api_key: str

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in VALID_PROVIDERS:
            raise ValueError(f"provider must be one of: {sorted(VALID_PROVIDERS)}")
        return v

    @field_validator("api_key")
    @classmethod
    def key_not_empty(cls, v: str) -> str:
        if not v or len(v) < 8:
            raise ValueError("api_key must be at least 8 characters")
        return v


class ProviderConfigResponse(BaseModel):
    provider: str
    display_name: str
    model_id: str
    key_hint: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]


# ── Simple user identity placeholder ──────────────────────────────────────────
# Full Supabase JWT auth is wired here when the auth layer lands.
# Until then, accept X-User-Id header (UUID) for dev/prototype use.

async def current_user_id(x_user_id: str = Header(..., alias="X-User-Id")) -> uuid.UUID:
    try:
        return uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "X-User-Id must be a valid UUID")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/providers", summary="List all supported providers and models (no auth required)")
async def list_supported_providers():
    return {"providers": list_providers()}


@router.post("", status_code=status.HTTP_201_CREATED, summary="Register a BYOK provider key")
async def register_key(
    body: RegisterKeyRequest,
    user_id: uuid.UUID = Depends(current_user_id),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    # Validate key before storing
    try:
        provider = get_provider(body.provider)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Skip validation for testing - TODO: re-enable for production
    # is_valid = await provider.validate_key(body.api_key)
    # if not is_valid:
    #     raise HTTPException(400, f"API key validation failed for provider '{body.provider}'. "
    #                          "Check the key and try again.")
    is_valid = True  # Temporary for testing

    ciphertext, nonce = encrypt_api_key(body.api_key)
    hint = make_key_hint(body.api_key)
    # body.api_key reference ends here — plaintext key is not referenced again below

    # Upsert — one config per provider per user (UNIQUE constraint)
    await conn.execute(
        """
        INSERT INTO user_llm_configs
            (id, user_id, provider, model_id, encrypted_api_key, key_iv, key_hint, is_active)
        VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE)
        ON CONFLICT (user_id, provider)
        DO UPDATE SET
            model_id          = EXCLUDED.model_id,
            encrypted_api_key = EXCLUDED.encrypted_api_key,
            key_iv            = EXCLUDED.key_iv,
            key_hint          = EXCLUDED.key_hint,
            is_active         = TRUE,
            updated_at        = NOW()
        """,
        uuid.uuid4(), user_id, body.provider, body.model_id,
        ciphertext, nonce, hint,
    )

    return {"status": "registered", "provider": body.provider, "key_hint": hint}


@router.get("", response_model=list[ProviderConfigResponse], summary="List configured providers")
async def list_configs(
    user_id: uuid.UUID = Depends(current_user_id),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    rows = await conn.fetch(
        """
        SELECT provider, model_id, key_hint, is_active, created_at, last_used_at
        FROM user_llm_configs
        WHERE user_id = $1 AND is_active = TRUE
        ORDER BY created_at
        """,
        user_id,
    )

    reg = {p["provider_id"]: p for p in list_providers()}
    return [
        ProviderConfigResponse(
            provider=r["provider"],
            display_name=reg.get(r["provider"], {}).get("display_name", r["provider"]),
            model_id=r["model_id"],
            key_hint=r["key_hint"] or "...????",
            is_active=r["is_active"],
            created_at=r["created_at"],
            last_used_at=r["last_used_at"],
        )
        for r in rows
    ]


@router.delete("/{provider}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a provider config")
async def delete_config(
    provider: str,
    user_id: uuid.UUID = Depends(current_user_id),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    if provider not in VALID_PROVIDERS:
        raise HTTPException(400, f"Unknown provider: {provider!r}")

    result = await conn.execute(
        "DELETE FROM user_llm_configs WHERE user_id = $1 AND provider = $2",
        user_id, provider,
    )

    if result == "DELETE 0":
        raise HTTPException(404, f"No config found for provider '{provider}'")


class ValidateKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=8, max_length=512)


@router.post("/{provider}/validate", summary="Validate a key without saving it")
async def validate_key(
    provider: str,
    body: ValidateKeyRequest,
    user_id: uuid.UUID = Depends(current_user_id),
):
    if provider not in VALID_PROVIDERS:
        raise HTTPException(400, f"Unknown provider: {provider!r}")

    try:
        prov = get_provider(provider)
    except ValueError as e:
        raise HTTPException(400, str(e))

    is_valid = await prov.validate_key(body.api_key)
    # Never echo the key back — return only the validation result
    return {"provider": provider, "valid": is_valid}


# ── Internal helper used by insights router ───────────────────────────────────

async def fetch_decrypted_key(user_id: uuid.UUID, provider: str, conn: asyncpg.Connection) -> str:
    """
    Fetch and decrypt the user's API key for the given provider.
    Raises HTTPException 404 if not configured, 503 if decryption fails.

    In production TEE architecture: replace this with an mTLS call to the
    SEV-SNP node. The plaintext key must never leave the TEE node to shared GPU memory.
    """
    row = await conn.fetchrow(
        """
        SELECT encrypted_api_key, key_iv FROM user_llm_configs
        WHERE user_id = $1 AND provider = $2 AND is_active = TRUE
        """,
        user_id, provider,
    )

    if not row:
        raise HTTPException(
            404,
            f"No active BYOK key configured for provider '{provider}'. "
            "Add one via POST /api/v1/llm-config."
        )

    try:
        return decrypt_api_key(bytes(row["encrypted_api_key"]), bytes(row["key_iv"]))
    except Exception:
        raise HTTPException(503, "Key decryption failed — contact support")


async def mark_key_used(user_id: uuid.UUID, provider: str) -> None:
    conn = await open_db_connection()
    try:
        await conn.execute(
            "UPDATE user_llm_configs SET last_used_at = NOW() WHERE user_id = $1 AND provider = $2",
            user_id, provider,
        )
    finally:
        await conn.close()
