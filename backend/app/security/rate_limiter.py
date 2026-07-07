import time
from collections.abc import Callable

import redis
from fastapi import Depends, HTTPException, Request

from app.config import get_settings
from app.db.models import User
from app.dependencies import get_current_user

settings = get_settings()


class RateLimiter:
    """Redis sorted-set sliding-window rate limiter."""

    def __init__(self, redis_client=None):
        self.redis = redis_client or redis.from_url(settings.redis_url)

    def check_rate_limit(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        member = f"{now:.6f}"
        pipeline = self.redis.pipeline()
        pipeline.zremrangebyscore(key, 0, now - window_seconds)
        pipeline.zadd(key, {member: now})
        pipeline.zcard(key)
        pipeline.expire(key, window_seconds)
        results = pipeline.execute()
        return int(results[2]) <= limit


def parse_limit(limit_value: str) -> tuple[int, int]:
    count, period = limit_value.split("/", 1)
    period = period.lower()
    if period == "minute":
        return int(count), 60
    if period.endswith("minute"):
        return int(count), int(period.removesuffix("minute")) * 60
    if period == "hour":
        return int(count), 3600
    if period.endswith("hour"):
        return int(count), int(period.removesuffix("hour")) * 3600
    raise ValueError(f"Unsupported rate limit period: {period}")


def _limit_dependency(
    limit_setting: str,
    key_factory: Callable[[Request, User | None], str],
    require_user: bool,
):
    limit, window_seconds = parse_limit(limit_setting)

    async def dependency(
        request: Request,
        user: User | None = Depends(get_current_user) if require_user else None,
    ) -> None:
        limiter = RateLimiter()
        key = key_factory(request, user)
        if not limiter.check_rate_limit(key, limit, window_seconds):
            raise HTTPException(
                status_code=429,
                detail="Too many requests",
                headers={"Retry-After": str(window_seconds)},
            )

    return dependency


def rate_limit_scan():
    return _limit_dependency(
        settings.rate_limit_scan,
        lambda _request, user: f"rate:scan:{user.user_id if user else 'anonymous'}",
        require_user=True,
    )


def rate_limit_search():
    return _limit_dependency(
        settings.rate_limit_search,
        lambda _request, user: f"rate:search:{user.user_id if user else 'anonymous'}",
        require_user=True,
    )


def rate_limit_login():
    return _limit_dependency(
        settings.rate_limit_login,
        lambda request, _user: f"rate:login:{request.client.host if request.client else 'unknown'}",
        require_user=False,
    )
