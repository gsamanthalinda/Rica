from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.auth import get_current_user
from database import get_db
from models import User
from schemas.mfa import (
    MFADisableRequest,
    MFALoginRequest,
    MFALoginResponse,
    MFASetupResponse,
    MFAVerifyRequest,
    MFAVerifyResponse,
)
from services import mfa_service

router = APIRouter(prefix="/auth/mfa", tags=["mfa"])


@router.post("/setup", response_model=MFASetupResponse)
def setup_mfa(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MFASetupResponse:
    result = mfa_service.setup_mfa(db, current_user)
    return MFASetupResponse(**result)


@router.post("/verify", response_model=MFAVerifyResponse)
def verify_mfa(
    payload: MFAVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MFAVerifyResponse:
    user = mfa_service.verify_mfa(db, current_user, payload.token, payload.code)
    return MFAVerifyResponse(
        mfa_enabled=user.mfa_enabled, message="MFA enabled successfully"
    )


@router.post("/disable", response_model=MFAVerifyResponse)
def disable_mfa(
    payload: MFADisableRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MFAVerifyResponse:
    user = mfa_service.disable_mfa(db, current_user, payload.code)
    return MFAVerifyResponse(
        mfa_enabled=user.mfa_enabled, message="MFA disabled successfully"
    )


@router.post("/login", response_model=MFALoginResponse)
def mfa_login(
    payload: MFALoginRequest, db: Session = Depends(get_db)
) -> MFALoginResponse:
    token = mfa_service.mfa_login(db, payload.email, payload.password, payload.code)
    return MFALoginResponse(access_token=token)
