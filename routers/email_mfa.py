from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas.email_mfa import (
    ResendCodeRequest,
    ResendCodeResponse,
    VerifyLoginRequest,
)
from services import email_mfa_service

router = APIRouter(prefix="/auth/mfa", tags=["email-mfa"])


@router.post("/verify-login")
def verify_login(payload: VerifyLoginRequest, db: Session = Depends(get_db)):
    token = email_mfa_service.verify_login_code(db, payload.challenge_id, payload.code)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/resend", response_model=ResendCodeResponse)
def resend(payload: ResendCodeRequest, db: Session = Depends(get_db)):
    record = email_mfa_service.resend_login_code(db, payload.challenge_id)
    return ResendCodeResponse(
        challenge_id=str(record.code_id),
        expires_in=email_mfa_service.one_time_code_service.CODE_TTL_MINUTES * 60
        if False
        else 300,
        message="A new verification code has been sent.",
    )
