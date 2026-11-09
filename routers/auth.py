from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from core.auth import _bearer_scheme
from database import get_db
from schemas.auth import LoginRequest, LogoutResponse, TokenResponse
from services import email_mfa_service, user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
    response: Response = None,
) -> TokenResponse:
    user = user_service.authenticate(db, payload.email, payload.password)
    if getattr(user, "email_mfa_enabled", False):
        if response is not None:
            response.status_code = 202
        record = email_mfa_service.create_login_challenge(db, user)
        resp = email_mfa_service.challenge_response(record, user)
        return TokenResponse(
            challenge_id=resp["challenge_id"],
            expires_in=resp["expires_in"],
            detail=resp["detail"],
        )
    token = user_service.create_access_token(user)
    return TokenResponse(access_token=token)


@router.post("/logout", response_model=LogoutResponse)
def logout(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
) -> LogoutResponse:
    detail = user_service.logout(credentials.credentials if credentials else None)
    return LogoutResponse(detail=detail)
