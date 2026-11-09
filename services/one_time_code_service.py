import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from models import OneTimeCode

CODE_LENGTH = 6
CODE_TTL_MINUTES = 15
MAX_ATTEMPTS = 5


def generate_code() -> str:
    return f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def code_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES)


def is_expired(record: OneTimeCode) -> bool:
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at < datetime.now(timezone.utc)


def matches(record: OneTimeCode, code: str) -> bool:
    return secrets.compare_digest(record.code_hash, hash_code(code))


def is_locked(record: OneTimeCode) -> bool:
    return (record.attempts or 0) >= MAX_ATTEMPTS
