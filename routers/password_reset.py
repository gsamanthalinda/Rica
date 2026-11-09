from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from core.config import settings
from database import get_db
from middleware.rate_limit import limit_by_ip
from schemas.password_reset import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    ResetVerifyRequest,
    ResetVerifyResponse,
)
from services import password_reset_service

router = APIRouter(prefix="/auth", tags=["password-reset"])


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    dependencies=[
        Depends(limit_by_ip("forgot_password", settings.forgot_password_ip_limit))
    ],
)
def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ForgotPasswordResponse:
    result = password_reset_service.forgot_password(db, payload.email, background_tasks)
    return ForgotPasswordResponse(**result)


@router.post(
    "/reset/verify",
    response_model=ResetVerifyResponse,
    dependencies=[Depends(limit_by_ip("reset_verify", settings.reset_verify_ip_limit))],
)
def verify_reset_code(
    payload: ResetVerifyRequest, db: Session = Depends(get_db)
) -> ResetVerifyResponse:
    result = password_reset_service.verify_reset_code(db, payload.email, payload.code)
    return ResetVerifyResponse(**result)


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    dependencies=[
        Depends(limit_by_ip("reset_password", settings.reset_password_ip_limit))
    ],
)
def reset_password(
    payload: ResetPasswordRequest, db: Session = Depends(get_db)
) -> ResetPasswordResponse:
    result = password_reset_service.reset_password(
        db, payload.token, payload.new_password
    )
    return ResetPasswordResponse(**result)
