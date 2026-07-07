import os
import sys
from uuid import uuid4

import fakeredis
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from app.security.audit_logger import AuditLogger
from app.security.encryption import (
    decrypt_drive_token,
    decrypt_embedding,
    derive_key,
    encrypt_drive_token,
    encrypt_embedding,
)
from app.security.rate_limiter import RateLimiter, parse_limit


def test_embedding_encryption_roundtrip() -> None:
    key = derive_key(b"master-secret", "user-1", "event-1")
    embedding = np.arange(512, dtype=np.float32)

    ciphertext = encrypt_embedding(embedding, key)
    decrypted = decrypt_embedding(ciphertext, key)

    assert ciphertext != embedding.tobytes()
    np.testing.assert_array_equal(decrypted, embedding)


def test_drive_token_encryption_roundtrip() -> None:
    token = "refresh-token-value"
    ciphertext = encrypt_drive_token(token, b"master-secret")

    assert ciphertext != token.encode("utf-8")
    assert decrypt_drive_token(ciphertext, b"master-secret") == token


def test_key_derivation_is_deterministic_and_scoped() -> None:
    first = derive_key(b"master-secret", "user-1", "event-1")
    second = derive_key(b"master-secret", "user-1", "event-1")
    other = derive_key(b"master-secret", "user-2", "event-1")

    assert first == second
    assert first != other
    assert len(first) == 32


def test_rate_limiter_sliding_window() -> None:
    redis_client = fakeredis.FakeRedis()
    limiter = RateLimiter(redis_client)

    assert limiter.check_rate_limit("rate:test", limit=2, window_seconds=60) is True
    assert limiter.check_rate_limit("rate:test", limit=2, window_seconds=60) is True
    assert limiter.check_rate_limit("rate:test", limit=2, window_seconds=60) is False


def test_parse_limit() -> None:
    assert parse_limit("5/minute") == (5, 60)
    assert parse_limit("10/15minute") == (10, 900)
    assert parse_limit("100/hour") == (100, 3600)


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class FakeDB:
    def __init__(self):
        self.rows = []
        self.commits = 0

    async def execute(self, _statement):
        previous = self.rows[-1].chain_hmac if self.rows else None
        return ScalarResult(previous)

    def add(self, row):
        self.rows.append(row)

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_audit_logger_creates_hmac_chain() -> None:
    db = FakeDB()
    redis_client = fakeredis.FakeRedis()
    logger = AuditLogger(db, redis_client)
    event_id = str(uuid4())

    await logger.log("scan", "user-1", event_id, "127.0.0.1", "success", 42)
    await logger.log("search", "user-1", event_id, "127.0.0.1", "success", 30)

    assert db.commits == 2
    assert len(db.rows) == 2
    assert db.rows[0].chain_hmac != db.rows[1].chain_hmac
    assert db.rows[0].user_id_hash != b"user-1"
