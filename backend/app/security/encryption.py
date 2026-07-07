import base64
import hashlib
import os
import time

import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes


def _normalize_master_key(master_key: bytes) -> bytes:
    if len(master_key) == 32:
        return master_key
    try:
        decoded = base64.urlsafe_b64decode(master_key)
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass
    return hashlib.sha256(master_key).digest()


def derive_key(master_key: bytes, user_id: str, event_id: str) -> bytes:
    """Derive a per-user, per-event AES-256 key."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=f"{user_id}:{event_id}".encode("utf-8"),
    )
    return hkdf.derive(_normalize_master_key(master_key))


def encrypt_embedding(embedding: np.ndarray, key: bytes) -> bytes:
    """Encrypt a 512-d float32 embedding with AES-256-GCM."""
    normalized_key = _normalize_master_key(key)
    nonce = os.urandom(12)
    plaintext = np.asarray(embedding, dtype=np.float32).reshape(512).tobytes()
    ciphertext = AESGCM(normalized_key).encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def decrypt_embedding(ciphertext: bytes, key: bytes) -> np.ndarray:
    """Decrypt an embedding encrypted by encrypt_embedding."""
    normalized_key = _normalize_master_key(key)
    nonce, encrypted = ciphertext[:12], ciphertext[12:]
    plaintext = AESGCM(normalized_key).decrypt(nonce, encrypted, None)
    return np.frombuffer(plaintext, dtype=np.float32).reshape(512)


def _drive_token_key(master_key: bytes) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"facefind:drive-token",
    )
    return hkdf.derive(_normalize_master_key(master_key))


def encrypt_drive_token(token: str, master_key: bytes) -> bytes:
    """Encrypt a Google Drive refresh token for server-side storage."""
    nonce = os.urandom(12)
    ciphertext = AESGCM(_drive_token_key(master_key)).encrypt(
        nonce,
        token.encode("utf-8"),
        None,
    )
    return nonce + ciphertext


def decrypt_drive_token(ciphertext: bytes, master_key: bytes) -> str:
    """Decrypt a Google Drive refresh token."""
    nonce, encrypted = ciphertext[:12], ciphertext[12:]
    plaintext = AESGCM(_drive_token_key(master_key)).decrypt(nonce, encrypted, None)
    return plaintext.decode("utf-8")


def _file_token_key(master_key: bytes) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"facefind:file-access-token",
    )
    return hkdf.derive(_normalize_master_key(master_key))


def create_file_access_token(
    file_id: str,
    user_id: str,
    master_key: bytes,
    expires_in_seconds: int = 900,
) -> str:
    """Create an opaque, tamper-proof token scoped to exactly one file, one
    user, and a short expiry window. If this token leaks (shared link,
    browser history, proxy log), it can only be used to fetch that single
    file, and only until it expires - never a reusable credential."""
    expiry = int(time.time()) + expires_in_seconds
    payload = f"{expiry}:{user_id}:{file_id}".encode("utf-8")
    nonce = os.urandom(12)
    ciphertext = AESGCM(_file_token_key(master_key)).encrypt(nonce, payload, None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("utf-8").rstrip("=")


def verify_file_access_token(token: str, master_key: bytes) -> tuple[str, str] | None:
    """Verify a file access token. Returns (file_id, user_id) if valid and
    unexpired, otherwise None."""
    try:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
        nonce, encrypted = raw[:12], raw[12:]
        plaintext = AESGCM(_file_token_key(master_key)).decrypt(nonce, encrypted, None)
        expiry_str, user_id, file_id = plaintext.decode("utf-8").split(":", 2)
    except Exception:
        return None

    if int(expiry_str) < int(time.time()):
        return None
    return file_id, user_id
