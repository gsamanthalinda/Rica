import hashlib
import datetime
from datetime import timezone
import os
import uuid

import jwt
from sqlalchemy.orm import Session

from core.config import settings
from core.exceptions import AppError
from models import AccountStatus, User, UserRole
from repositories import user_repository


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    return f"{salt}${hashlib.sha256((salt + password).encode()).hexdigest()}"


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    salt, hash_value = password_hash.split("$", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == hash_value


def create_access_token(user: User) -> str:
    payload = {
        "user_id": str(user.user_id),
        "email": user.email,
        "role": user.role.value,
        "jti": str(uuid.uuid4()),
        "exp": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(
        payload, settings.jwt_signing_key, algorithm=settings.jwt_algorithm
    )


def get_by_email(db: Session, email: str) -> User | None:
    return user_repository.get_by_email(db, email)


def logout(credentials: str | None) -> str:
    from core.auth import blacklist_jti, decode_token

    if credentials is None:
        raise InvalidCredentialsError("Missing or invalid authorization header")
    payload = decode_token(credentials)
    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti and exp:
        expires_at = datetime.datetime.fromtimestamp(exp, tz=timezone.utc)
        blacklist_jti(jti, expires_at)
    return "Successfully logged out"


def authenticate(db: Session, email: str, password: str) -> User:
    user = user_repository.get_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError()
    if _status_value(user) == AccountStatus.DISABLED.value:
        raise AccountDisabledError()
    return user


def _status_value(user: User) -> str:
    status = user.account_status
    return getattr(status, "value", status)


class DuplicateEmailError(AppError):
    status_code = 409

    def __init__(self, detail: str) -> None:
        super().__init__(detail)


class UserNotFoundError(AppError):
    status_code = 404

    def __init__(self, detail: str) -> None:
        super().__init__(detail)


class InvalidCredentialsError(AppError):
    status_code = 401

    def __init__(self, detail: str = "Invalid email or password") -> None:
        super().__init__(detail)


class AccountDisabledError(AppError):
    status_code = 401

    def __init__(self, detail: str = "Account is disabled") -> None:
        super().__init__(detail)


def create(
    db: Session,
    email: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
    role: UserRole = UserRole.OPERATIONS_MANAGER,
    company_name: str | None = None,
) -> User:
    if user_repository.get_by_email(db, email) is not None:
        raise DuplicateEmailError(f"User with email {email} already exists")
    user = user_repository.create(
        db,
        email=email,
        password_hash=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        role=role,
        account_status=AccountStatus.PENDING,
        company_name=company_name,
    )
    user.email_mfa_enabled = True
    db.commit()
    db.refresh(user)
    from services import activation_service

    activation_service.send_activation_code(db, user)
    return user


def activate(db: Session, user: User, password: str) -> User:
    now = datetime.datetime.now(datetime.timezone.utc)
    user.password_hash = hash_password(password)
    user.password_changed_at = now
    user.activated_at = now
    user.account_status = AccountStatus.ACTIVE
    db.commit()
    db.refresh(user)
    return user


def get_by_id(db: Session, user_id: str) -> User:
    user = user_repository.get_by_id(db, user_id)
    if user is None:
        raise UserNotFoundError(f"User {user_id} not found")
    return user


def list(db: Session) -> list[User]:
    return user_repository.list(db)


def update(
    db: Session,
    user_id: str,
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    role: UserRole | None = None,
    company_name: str | None = None,
) -> User:
    user = user_repository.update(
        db,
        user_id=user_id,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=role,
        company_name=company_name,
    )
    if user is None:
        raise UserNotFoundError(f"User {user_id} not found")
    return user


def disable(db: Session, user_id: str) -> User:
    user = user_repository.set_status(db, user_id, AccountStatus.DISABLED)
    if user is None:
        raise UserNotFoundError(f"User {user_id} not found")
    return user
