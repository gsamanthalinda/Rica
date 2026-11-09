import os
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pyotp
import qrcode
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from core.config import settings
from core.exceptions import AppError
from models import MFATokenPurpose, User
from repositories import mfa_repository
from services import email_service


def _fernet() -> Fernet:
    return Fernet(settings.mfa_encryption_key.encode())


def _encrypt(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def _decrypt(encrypted: str) -> str:
    return _fernet().decrypt(encrypted.encode()).decode()


def generate_secret() -> str:
    return pyotp.random_base32()


def generate_qr_code(secret: str, email: str) -> str:
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(email, issuer_name="RICA")
    img = qrcode.make(uri)
    buf = BytesIO()
    img.save(buf, format="PNG")
    import base64

    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def verify_code(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=2)


def setup_mfa(db: Session, user: User) -> dict:
    if user.mfa_enabled:
        raise AppError("MFA is already enabled")

    secret = generate_secret()
    encrypted = _encrypt(secret)

    token = os.urandom(32).hex()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    mfa_repository.create_token(
        db,
        user_id=user.user_id,
        secret_encrypted=encrypted,
        purpose=MFATokenPurpose.SETUP,
        token=token,
        expires_at=expires_at,
    )

    email_service.send_email(
        to=user.email,
        subject="MFA setup code",
        body=f"Your MFA setup code is: {token}\nYour secret is: {secret}",
    )

    return {
        "secret": secret,
        "qr_code_url": generate_qr_code(secret, user.email),
        "token": token,
    }


def verify_mfa(db: Session, user: User, token: str, code: str) -> User:
    mfa_token = mfa_repository.get_token_by_user_and_token(
        db, user.user_id, token, MFATokenPurpose.SETUP
    )
    if mfa_token is None:
        raise AppError("Invalid or expired MFA setup token")
    now = datetime.now(timezone.utc)
    expires_at = mfa_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise AppError("MFA setup token has expired")
    if mfa_token.used:
        raise AppError("MFA setup token has already been used")

    secret = _decrypt(mfa_token.secret_encrypted)
    if not verify_code(secret, code):
        raise AppError("Invalid verification code")

    mfa_repository.mark_used(db, mfa_token)
    user.mfa_enabled = True
    user.mfa_secret_encrypted = mfa_token.secret_encrypted
    db.commit()
    db.refresh(user)
    return user


def disable_mfa(db: Session, user: User, code: str) -> User:
    if not user.mfa_enabled:
        raise AppError("MFA is not enabled")

    if not user.mfa_secret_encrypted:
        raise AppError("MFA secret not found")

    secret = _decrypt(user.mfa_secret_encrypted)
    if not verify_code(secret, code):
        raise AppError("Invalid verification code")

    user.mfa_enabled = False
    user.mfa_secret_encrypted = None
    db.commit()
    db.refresh(user)
    return user


def mfa_login(db: Session, email: str, password: str, code: str) -> str:
    from services.user_service import authenticate, create_access_token

    user = authenticate(db, email, password)

    if not user.mfa_enabled:
        raise AppError("MFA is not enabled for this user")

    if not user.mfa_secret_encrypted:
        raise AppError("MFA secret not found")

    secret = _decrypt(user.mfa_secret_encrypted)
    if not verify_code(secret, code):
        raise AppError("Invalid MFA code")

    return create_access_token(user)
