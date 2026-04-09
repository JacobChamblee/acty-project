"""
key_encryption.py — AES-256-GCM wrap/unwrap for BYOK API keys.

The server-side CACTUS_KEY_ENCRYPTION_KEY (32 bytes, base64-encoded) is loaded
from the environment. In production it lives in a k8s Secret, never in .env.

TEE note: In the production architecture, the decrypt() call below should be
forwarded to the AMD SEV-SNP TEE node (A3) via an mTLS gRPC call. Plaintext
BYOK keys must never reach shared GPU pool memory. Until the TEE node is live,
this module performs decryption in the API process — acceptable for homelab
pre-production phase, MUST be migrated before real user data is captured.
"""

from __future__ import annotations

import base64
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_KEY_ENV = "CACTUS_KEY_ENCRYPTION_KEY"
_NONCE_SIZE = 12  # 96-bit GCM nonce — standard for AES-GCM


def _load_master_key() -> bytes:
    raw = os.environ.get(_KEY_ENV, "")
    if not raw:
        raise EnvironmentError(
            f"{_KEY_ENV} is not set. "
            "Generate with: python3 -c \"import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())\""
        )
    key_bytes = base64.b64decode(raw)
    if len(key_bytes) != 32:
        raise ValueError(f"{_KEY_ENV} must decode to exactly 32 bytes (got {len(key_bytes)})")
    return key_bytes


def encrypt_api_key(plaintext_key: str) -> tuple[bytes, bytes]:
    """
    Encrypt a plaintext API key.

    Returns:
        (ciphertext: bytes, nonce: bytes) — both stored in DB.
        The nonce (key_iv) is randomly generated per encryption; safe to store.
    """
    master = _load_master_key()
    nonce = secrets.token_bytes(_NONCE_SIZE)
    aesgcm = AESGCM(master)
    ciphertext = aesgcm.encrypt(nonce, plaintext_key.encode(), None)
    return ciphertext, nonce


def decrypt_api_key(ciphertext: bytes, nonce: bytes) -> str:
    """
    Decrypt a stored API key ciphertext.

    Raises cryptography.exceptions.InvalidTag if tampered.
    The caller must treat the returned string as ephemeral — never log it.
    """
    master = _load_master_key()
    aesgcm = AESGCM(master)
    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext_bytes.decode()


def make_key_hint(plaintext_key: str) -> str:
    """Return '...XXXX' using only the last 4 characters — safe for UI display."""
    if len(plaintext_key) < 4:
        return "...????"
    return f"...{plaintext_key[-4:]}"
