import hashlib
import hmac
import os
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import AuditLog

settings = get_settings()


class AuditLogger:
    """Tamper-evident audit logger using daily salt and HMAC chaining."""

    def __init__(self, db: AsyncSession, redis_client):
        self.db = db
        self.redis = redis_client
        self.master_key = settings.master_encryption_key.encode("utf-8")

    def _daily_salt_key(self) -> str:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"audit:daily_salt:{today}"

    def _daily_salt(self) -> bytes:
        key = self._daily_salt_key()
        salt = self.redis.get(key)
        if salt:
            return salt if isinstance(salt, bytes) else str(salt).encode("utf-8")

        salt = os.urandom(32)
        self.redis.setex(key, 24 * 60 * 60, salt)
        return salt

    def _hash_optional(self, value: str | None, salt: bytes) -> bytes | None:
        if value is None:
            return None
        return hashlib.sha256(value.encode("utf-8") + salt).digest()

    async def get_prev_chain_hmac(self) -> bytes:
        result = await self.db.execute(
            select(AuditLog.chain_hmac).order_by(desc(AuditLog.timestamp)).limit(1)
        )
        previous = result.scalar()
        return previous or (b"\x00" * 32)

    async def log(
        self,
        action: str,
        user_id: str | None,
        event_id: str | None,
        ip: str | None,
        outcome: str,
        latency_ms: int | None,
    ) -> None:
        salt = self._daily_salt()
        timestamp = datetime.utcnow()
        user_hash = self._hash_optional(user_id, salt)
        ip_hash = self._hash_optional(ip, salt)
        parsed_event_id = UUID(event_id) if event_id else None
        previous = await self.get_prev_chain_hmac()
        fields = b"|".join(
            [
                timestamp.isoformat().encode("utf-8"),
                action.encode("utf-8"),
                outcome.encode("utf-8"),
                str(parsed_event_id or "").encode("utf-8"),
                user_hash or b"",
                ip_hash or b"",
                str(latency_ms or "").encode("utf-8"),
            ]
        )
        chain_hmac = hmac.new(self.master_key, previous + fields, hashlib.sha256).digest()

        self.db.add(
            AuditLog(
                timestamp=timestamp,
                user_id_hash=user_hash,
                event_id=parsed_event_id,
                action=action,
                ip_hash=ip_hash,
                outcome=outcome,
                latency_ms=latency_ms,
                chain_hmac=chain_hmac,
            )
        )
        await self.db.commit()
