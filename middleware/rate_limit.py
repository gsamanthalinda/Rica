import logging
import os
import threading
import time
from hashlib import sha256
from typing import Callable

from fastapi import FastAPI, HTTPException, Request, status

from core.config import settings

logger = logging.getLogger(__name__)


def add_rate_limiting(app: FastAPI):
    if os.getenv("TESTING") == "1":
        return

    from core.config import settings

    _store: dict[str, list[float]] = {}

    def _cleanup(key: str, window: float):
        now = time.time()
        _store[key] = [t for t in _store.get(key, []) if now - t < window]

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next: Callable):
        if request.url.path == "/auth/login":
            client_ip = request.client.host if request.client else "unknown"
            key = f"login:{client_ip}"
            max_attempts = getattr(settings, "login_max_attempts", 5)
            window = getattr(settings, "login_window_seconds", 900)

            _cleanup(key, window)
            attempts = _store.get(key, [])
            if len(attempts) >= max_attempts:
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Too many login attempts. Please try again later."
                    },
                )
            attempts.append(time.time())
            _store[key] = attempts

        return await call_next(request)


class _MemoryStore:
    def __init__(self):
        self._data: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, window: int) -> tuple[int, int]:
        now = time.monotonic()
        with self._lock:
            if len(self._data) > 10000:
                self._data = {k: v for k, v in self._data.items() if v[0] > now}
            expires, count = self._data.get(key, (0.0, 0))
            if expires <= now:
                expires, count = now + window, 0
            count += 1
            self._data[key] = (expires, count)
            return count, max(1, int(expires - now))


class _RedisStore:
    def __init__(self, url: str):
        import redis

        self._client = redis.Redis.from_url(
            url, socket_connect_timeout=1, socket_timeout=1
        )

    def hit(self, key: str, window: int) -> tuple[int, int]:
        pipe = self._client.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        count, ttl = pipe.execute()
        if ttl is None or int(ttl) < 0:
            self._client.expire(key, window)
            ttl = window
        return int(count), int(ttl)


_memory_store = _MemoryStore()
_redis_store: _RedisStore | None = None


def _get_redis_store() -> _RedisStore | None:
    global _redis_store
    if _redis_store is None and settings.redis_url:
        try:
            _redis_store = _RedisStore(settings.redis_url)
        except Exception:
            logger.exception("Redis rate limiter unavailable; using in-memory counter")
    return _redis_store


def _hit(key: str) -> tuple[int, int]:
    window = settings.password_reset_window_seconds
    store = _get_redis_store()
    if store is not None:
        try:
            return store.hit(key, window)
        except Exception:
            logger.warning("Redis rate limit call failed; using in-memory counter")
    return _memory_store.hit(key, window)


def _disabled() -> bool:
    return os.getenv("TESTING") == "1"


def _too_many(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests. Please try again later.",
        headers={"Retry-After": str(retry_after)},
    )


def client_ip(request: Request) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        parts = [part.strip() for part in forwarded.split(",") if part.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else "unknown"


def _email_key(name: str, email: str) -> str:
    digest = sha256(email.strip().lower().encode()).hexdigest()
    return f"rl:{name}:email:{digest}"


def limit_by_ip(name: str, limit: int) -> Callable[[Request], None]:
    def dependency(request: Request) -> None:
        if _disabled():
            return
        count, retry_after = _hit(f"rl:{name}:ip:{client_ip(request)}")
        if count > limit:
            raise _too_many(retry_after)

    return dependency


def allow_email(name: str, email: str, limit: int) -> bool:
    if _disabled():
        return True
    count, _ = _hit(_email_key(name, email))
    return count <= limit


def enforce_email(name: str, email: str, limit: int) -> None:
    if _disabled():
        return
    count, retry_after = _hit(_email_key(name, email))
    if count > limit:
        raise _too_many(retry_after)
