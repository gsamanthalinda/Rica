from sqlalchemy.orm import Session

from core.exceptions import AppError
from models import AccountStatus, OneTimeCode, OneTimeCodePurpose, User
from repositories import one_time_code_repository
from services import email_service, email_template, one_time_code_service, user_service


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked = local[:1] + "*"
    else:
        masked = f"{local[:2]}{'*' * (len(local) - 2)}"
    return f"{masked}@{domain}"


def _is_disabled(user: User) -> bool:
    status = user.account_status
    return getattr(status, "value", status) == AccountStatus.DISABLED.value


def _email_code(db: Session, user: User, code: str) -> None:
    plain = (
        f"Hello {user.first_name},\n\n"
        f"Your sign-in verification code is: {code}\n"
        f"The code expires in {one_time_code_service.CODE_TTL_MINUTES} minutes.\n\n"
        f"If you did not try to sign in, ignore this email and contact your "
        f"administrator."
    )
    html = email_template.render_email(
        title="Your RICA sign-in verification code",
        greeting=f"Hello {user.first_name},",
        paragraphs=[
            f"Your sign-in verification code is: {code}",
            f"The code expires in {one_time_code_service.CODE_TTL_MINUTES} minutes.",
        ],
        footer_lines=[
            "If you did not try to sign in, ignore this email and contact your administrator."
        ],
    )
    email_service.send_email(
        to=user.email,
        subject="Your RICA sign-in verification code",
        body=plain,
        html=html,
    )


def create_login_challenge(db: Session, user: User) -> OneTimeCode:
    one_time_code_repository.invalidate_all(
        db, user.user_id, OneTimeCodePurpose.LOGIN_MFA
    )
    code = one_time_code_service.generate_code()
    record = one_time_code_repository.create(
        db,
        user_id=user.user_id,
        purpose=OneTimeCodePurpose.LOGIN_MFA,
        code_hash=one_time_code_service.hash_code(code),
        expires_at=one_time_code_service.code_expires_at(),
    )
    _email_code(db, user, code)
    return record


def _get_challenge(db: Session, challenge_id: str) -> OneTimeCode:
    record = one_time_code_repository.get_by_id(
        db, challenge_id, OneTimeCodePurpose.LOGIN_MFA
    )
    if record is None:
        raise AppError("Invalid or expired verification code")
    if record.used_at is not None:
        raise AppError("This verification code has already been used")
    return record


def verify_login_code(db: Session, challenge_id: str, code: str) -> str:
    record = _get_challenge(db, challenge_id)
    if one_time_code_service.is_expired(record):
        raise AppError("Verification code has expired")
    if one_time_code_service.is_locked(record):
        raise AppError("Too many attempts. Request a new code.")
    if not one_time_code_service.matches(record, code):
        one_time_code_repository.increment_attempts(db, record)
        raise AppError("Invalid verification code")

    one_time_code_repository.mark_used(db, record)

    user = user_service.get_by_id(db, str(record.user_id))
    if user is None:
        raise AppError("User not found")
    if _is_disabled(user):
        raise user_service.AccountDisabledError()

    return user_service.create_access_token(user)


def resend_login_code(db: Session, challenge_id: str) -> OneTimeCode:
    record = _get_challenge(db, challenge_id)
    user = user_service.get_by_id(db, str(record.user_id))
    if user is None:
        raise AppError("User not found")
    if _is_disabled(user):
        raise user_service.AccountDisabledError()

    code = one_time_code_service.generate_code()
    one_time_code_repository.reset_code(
        db,
        record,
        one_time_code_service.hash_code(code),
        one_time_code_service.code_expires_at(),
    )
    _email_code(db, user, code)
    return record


def challenge_response(record: OneTimeCode, user: User) -> dict:
    return {
        "challenge_id": str(record.code_id),
        "expires_in": one_time_code_service.CODE_TTL_MINUTES * 60,
        "detail": f"A verification code was sent to {_mask_email(user.email)}.",
    }
