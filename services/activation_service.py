from sqlalchemy.orm import Session

from core.config import settings
from core.exceptions import AppError
from models import AccountStatus, OneTimeCodePurpose, User
from repositories import one_time_code_repository, user_repository
from services import email_service, email_template, one_time_code_service, user_service

GENERIC_MESSAGE = (
    "If the account exists and is awaiting activation, a code has been sent to "
    "that email address."
)


def _is_pending(user: User) -> bool:
    status = user.account_status
    return getattr(status, "value", status) == AccountStatus.PENDING.value


def send_activation_code(db: Session, user: User) -> str:
    one_time_code_repository.invalidate_all(
        db, user.user_id, OneTimeCodePurpose.ACTIVATION
    )
    code = one_time_code_service.generate_code()
    one_time_code_repository.create(
        db,
        user_id=user.user_id,
        purpose=OneTimeCodePurpose.ACTIVATION,
        code_hash=one_time_code_service.hash_code(code),
        expires_at=one_time_code_service.code_expires_at(),
    )
    plain = (
        f"Hello {user.first_name},\n\n"
        f"Your account activation code is: {code}\n"
        f"The code expires in {one_time_code_service.CODE_TTL_MINUTES} minutes.\n\n"
        f"Open {settings.frontend_url}/activate to set your password.\n\n"
        f"If you did not request this, please ignore this email."
    )
    html = email_template.render_email(
        title="Activate your RICA account",
        greeting=f"Hello {user.first_name},",
        paragraphs=[
            f"Your account activation code is: {code}",
            f"The code expires in {one_time_code_service.CODE_TTL_MINUTES} minutes.",
            f"Open {settings.frontend_url}/activate to set your password.",
        ],
        button_text="Activate Account",
        button_url=f"{settings.frontend_url}/activate",
        footer_lines=["If you did not request this, please ignore this email."],
    )
    email_service.send_email(
        to=user.email,
        subject="Activate your RICA account",
        body=plain,
        html=html,
    )
    return code


def request_activation_code(db: Session, email: str) -> dict:
    user = user_service.get_by_email(db, email)
    if user is None or not _is_pending(user):
        return {"message": GENERIC_MESSAGE, "sent": False}
    send_activation_code(db, user)
    return {"message": GENERIC_MESSAGE, "sent": True}


def activate(db: Session, code: str, password: str, email: str | None = None) -> User:
    if email:
        return _activate_with_email(db, email, code, password)
    return _activate_with_code(db, code, password)


def _activate_record(db: Session, record, user, password: str) -> User:
    one_time_code_repository.mark_used(db, record)
    return user_service.activate(db, user, password)


def _activate_with_email(db: Session, email: str, code: str, password: str) -> User:
    user = user_service.get_by_email(db, email)
    if user is None or not _is_pending(user):
        raise AppError("Invalid or expired activation code")

    record = one_time_code_repository.get_latest_active(
        db, user.user_id, OneTimeCodePurpose.ACTIVATION
    )
    if record is None:
        raise AppError("Invalid or expired activation code")
    if one_time_code_service.is_expired(record):
        raise AppError("Activation code has expired")
    if one_time_code_service.is_locked(record):
        raise AppError("Too many attempts. Request a new activation code.")
    if not one_time_code_service.matches(record, code):
        one_time_code_repository.increment_attempts(db, record)
        raise AppError("Invalid activation code")

    return _activate_record(db, record, user, password)


def _activate_with_code(db: Session, code: str, password: str) -> User:
    records = one_time_code_repository.get_active_by_hash(
        db, OneTimeCodePurpose.ACTIVATION, one_time_code_service.hash_code(code)
    )

    candidates = []
    for record in records:
        user = user_repository.get_by_id(db, record.user_id)
        if user is None or not _is_pending(user):
            continue
        candidates.append((record, user))

    if not candidates:
        raise AppError("Invalid or expired activation code")
    if len(candidates) > 1:
        raise AppError(
            "This activation code matches more than one account. "
            "Contact your administrator."
        )

    record, user = candidates[0]
    if one_time_code_service.is_expired(record):
        raise AppError("Activation code has expired")
    if one_time_code_service.is_locked(record):
        raise AppError("Too many attempts. Request a new activation code.")

    return _activate_record(db, record, user, password)
