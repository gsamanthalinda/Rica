from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import PasswordResetToken, PasswordResetTokenPurpose, User


def create_token(
    db: Session,
    user_id,
    token_hash: str,
    purpose: PasswordResetTokenPurpose,
    expires_at: datetime,
) -> PasswordResetToken:
    obj = PasswordResetToken(
        user_id=user_id,
        token_hash=token_hash,
        purpose=purpose,
        expires_at=expires_at,
    )
    db.add(obj)
    db.flush()
    db.refresh(obj)
    return obj


def get_token_by_hash(
    db: Session,
    token_hash: str,
    purpose: PasswordResetTokenPurpose,
) -> PasswordResetToken | None:
    return (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.purpose == purpose,
        )
        .first()
    )


def mark_used(db: Session, token: PasswordResetToken) -> PasswordResetToken:
    token.used = datetime.now(timezone.utc)
    db.flush()
    db.refresh(token)
    return token


def complete_password_reset(
    db: Session,
    reset_token: PasswordResetToken,
    user: User,
    password_hash: str,
    changed_at: datetime,
) -> None:
    reset_token.used = datetime.now(timezone.utc)  # see note on `used` type
    user.password_hash = password_hash
    user.password_changed_at = changed_at
    db.flush()
