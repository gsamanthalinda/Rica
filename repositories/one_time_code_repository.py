import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import OneTimeCode, OneTimeCodePurpose


def create(
    db: Session,
    user_id,
    purpose: OneTimeCodePurpose,
    code_hash: str,
    expires_at: datetime,
) -> OneTimeCode:
    obj = OneTimeCode(
        user_id=user_id,
        purpose=purpose,
        code_hash=code_hash,
        expires_at=expires_at,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_by_id(db: Session, code_id, purpose: OneTimeCodePurpose) -> OneTimeCode | None:
    try:
        uid = uuid.UUID(str(code_id))
    except (ValueError, TypeError, AttributeError):
        return None
    return (
        db.query(OneTimeCode)
        .filter(OneTimeCode.code_id == uid, OneTimeCode.purpose == purpose)
        .first()
    )


def get_latest_active(
    db: Session, user_id, purpose: OneTimeCodePurpose
) -> OneTimeCode | None:
    return (
        db.query(OneTimeCode)
        .filter(
            OneTimeCode.user_id == user_id,
            OneTimeCode.purpose == purpose,
            OneTimeCode.used_at.is_(None),
        )
        .order_by(OneTimeCode.created_at.desc())
        .first()
    )


def get_active_by_hash(
    db: Session, purpose: OneTimeCodePurpose, code_hash: str
) -> list[OneTimeCode]:
    return (
        db.query(OneTimeCode)
        .filter(
            OneTimeCode.purpose == purpose,
            OneTimeCode.code_hash == code_hash,
            OneTimeCode.used_at.is_(None),
        )
        .all()
    )


def mark_used(db: Session, code: OneTimeCode) -> OneTimeCode:
    code.used_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(code)
    return code


def invalidate_all(db: Session, user_id, purpose: OneTimeCodePurpose) -> int:
    codes = (
        db.query(OneTimeCode)
        .filter(
            OneTimeCode.user_id == user_id,
            OneTimeCode.purpose == purpose,
            OneTimeCode.used_at.is_(None),
        )
        .all()
    )
    now = datetime.now(timezone.utc)
    for code in codes:
        code.used_at = now
    if codes:
        db.commit()
    return len(codes)


def increment_attempts(db: Session, code: OneTimeCode) -> OneTimeCode:
    code.attempts = (code.attempts or 0) + 1
    db.commit()
    db.refresh(code)
    return code


def reset_code(
    db: Session, code: OneTimeCode, code_hash: str, expires_at: datetime
) -> OneTimeCode:
    code.code_hash = code_hash
    code.expires_at = expires_at
    code.attempts = 0
    code.used_at = None
    db.commit()
    db.refresh(code)
    return code
