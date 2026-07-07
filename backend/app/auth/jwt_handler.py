import secrets
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import redis
from app.config import get_settings

settings = get_settings()


def create_access_token(user_id: str, event_id: str, scope: str) -> str:
    """Create JWT token with RS256 signature"""
    with open(settings.jwt_private_key_path, "r") as f:
        private_key = f.read()

    payload = {
        "sub": user_id,
        "event_id": event_id,
        "scope": scope,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes),
        "jti": secrets.token_urlsafe(32),
    }

    return jwt.encode(payload, private_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Verify JWT signature and return payload"""
    with open(settings.jwt_public_key_path, "r") as f:
        public_key = f.read()

    try:
        payload = jwt.decode(token, public_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}")


def revoke_token(jti: str, ttl_seconds: int) -> None:
    """Add token JTI to blocklist with TTL"""
    r = redis.from_url(settings.redis_url)
    r.setex(f"blocklist:{jti}", ttl_seconds, "1")


def is_token_revoked(jti: str) -> bool:
    """Check if token is in blocklist"""
    r = redis.from_url(settings.redis_url)
    return r.exists(f"blocklist:{jti}") > 0
