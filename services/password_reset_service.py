import hashlib
import os
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from core.config import settings
from core.exceptions import AppError
from middleware.rate_limit import allow_email, enforce_email
from models import OneTimeCodePurpose, PasswordResetTokenPurpose
from repositories import one_time_code_repository, password_reset_repository
from services import email_service, email_template, one_time_code_service


class PersistedAppError(AppError):
    """Raised when an error response must preserve a database change."""


FORGOT_PASSWORD_MESSAGE = "If the email exists, a reset code has been sent"
RESET_TOKEN_TTL = timedelta(hours=1)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def forgot_password(
    db: Session,
    email: str,
    background_tasks: BackgroundTasks,
) -> dict:
    from services.user_service import get_by_email

    if not allow_email(
        "forgot_password",
        email,
        settings.forgot_password_email_limit,
    ):
        return {"message": FORGOT_PASSWORD_MESSAGE}

    user = get_by_email(db, email)
    if user is None:
        return {"message": FORGOT_PASSWORD_MESSAGE}

    one_time_code_repository.invalidate_all(
        db,
        user.user_id,
        OneTimeCodePurpose.RESET,
    )

    code = one_time_code_service.generate_code()

    one_time_code_repository.create(
        db,
        user_id=user.user_id,
        purpose=OneTimeCodePurpose.RESET,
        code_hash=one_time_code_service.hash_code(code),
        expires_at=one_time_code_service.code_expires_at(),
    )

    plain = (
        f"Hello {user.first_name},\n\n"
        f"Your password reset code is: {code}\n"
        f"The code expires in "
        f"{one_time_code_service.CODE_TTL_MINUTES} minutes.\n\n"
        "If you did not request a password reset, ignore this email."
    )

    html = email_template.render_email(
        title="Reset your password",
        greeting=f"Hello {user.first_name},",
        paragraphs=[
            f"Your password reset code is: {code}",
            (f"The code expires in {one_time_code_service.CODE_TTL_MINUTES} minutes."),
        ],
        footer_lines=["If you did not request a password reset, ignore this email."],
    )

    background_tasks.add_task(
        email_service.send_email,
        to=user.email,
        subject="Reset your password",
        body=plain,
        html=html,
    )

    return {"message": FORGOT_PASSWORD_MESSAGE}


def verify_reset_code(db: Session, email: str, code: str) -> dict:
    from services.user_service import get_by_email

    enforce_email(
        "reset_verify",
        email,
        settings.reset_verify_email_limit,
    )

    user = get_by_email(db, email)
    if user is None:
        raise AppError("Invalid or expired reset code")

    record = one_time_code_repository.get_latest_active(
        db,
        user.user_id,
        OneTimeCodePurpose.RESET,
    )

    if record is None:
        raise AppError("Invalid or expired reset code")

    if one_time_code_service.is_expired(record):
        raise AppError("Reset code has expired")

    if one_time_code_service.is_locked(record):
        raise AppError("Too many attempts. Request a new reset code.")

    if not one_time_code_service.matches(record, code):
        one_time_code_repository.increment_attempts(db, record)
        raise PersistedAppError("Invalid reset code")

    one_time_code_repository.mark_used(db, record)

    token = os.urandom(32).hex()

    password_reset_repository.create_token(
        db,
        user_id=user.user_id,
        token_hash=_hash_token(token),
        purpose=PasswordResetTokenPurpose.RESET,
        expires_at=_now() + RESET_TOKEN_TTL,
    )

    return {"token": token}


def reset_password(db: Session, token: str, new_password: str) -> dict:
    from services.user_service import get_by_id, hash_password

    token_hash = _hash_token(token)

    reset_token = password_reset_repository.get_token_by_hash(
        db,
        token_hash,
        PasswordResetTokenPurpose.RESET,
    )

    if reset_token is None:
        raise AppError("Invalid or expired reset token")

    if _as_utc(reset_token.expires_at) < _now():
        raise AppError("Reset token has expired")

    if reset_token.used:
        raise AppError("Reset token has already been used")

    user = get_by_id(db, reset_token.user_id)
    if user is None:
        raise AppError("Invalid or expired reset token")

    password_reset_repository.complete_password_reset(
        db,
        reset_token,
        user,
        password_hash=hash_password(new_password),
        changed_at=_now(),
    )

    return {"message": "Password has been reset successfully"}
