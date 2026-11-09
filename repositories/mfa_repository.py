from datetime import datetime

from sqlalchemy.orm import Session

from models import MFAToken, MFATokenPurpose


def create_token(
    db: Session,
    user_id,
    secret_encrypted: str,
    purpose: MFATokenPurpose,
    token: str,
    expires_at: datetime,
) -> MFAToken:
    obj = MFAToken(
        user_id=user_id,
        secret_encrypted=secret_encrypted,
        purpose=purpose,
        token=token,
        expires_at=expires_at,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_token_by_user_and_token(
    db: Session,
    user_id,
    token: str,
    purpose: MFATokenPurpose,
) -> MFAToken | None:
    return (
        db.query(MFAToken)
        .filter(
            MFAToken.user_id == user_id,
            MFAToken.token == token,
            MFAToken.purpose == purpose,
        )
        .first()
    )


def mark_used(db: Session, mfa_token: MFAToken) -> MFAToken:
    mfa_token.used = datetime.utcnow()
    db.commit()
    db.refresh(mfa_token)
    return mfa_token
