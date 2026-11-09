import datetime
import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from core.config import settings
from database import get_db
from models import User
from services import user_service

_bearer_scheme = HTTPBearer(auto_error=False)

_blacklist: dict[str, datetime] = {}


def _cleanup_blacklist():
    now = datetime.datetime.now(datetime.timezone.utc)
    expired = [jti for jti, exp in _blacklist.items() if exp < now]
    for jti in expired:
        del _blacklist[jti]


def blacklist_jti(jti: str, expires_at: datetime) -> None:
    _cleanup_blacklist()
    _blacklist[jti] = expires_at


def is_blacklisted(jti: str) -> bool:
    _cleanup_blacklist()
    return jti in _blacklist


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


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_verification_key,
            algorithms=[settings.jwt_algorithm],
        )
        if is_blacklisted(payload.get("jti", "")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )
    payload = decode_token(credentials.credentials)
    user = user_service.get_by_id(db, payload["user_id"])
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if user.account_status.value == "DISABLED":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled",
        )
    return user
