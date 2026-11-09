from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas.activation import (
    ActivationCodeRequest,
    ActivationCodeResponse,
    ActivationRequest,
    ActivationResponse,
)
from services import activation_service
from services.one_time_code_service import CODE_TTL_MINUTES

router = APIRouter(prefix="/auth/activate", tags=["activation"])


@router.post("/send-code", response_model=ActivationCodeResponse)
def send_activation_code(
    payload: ActivationCodeRequest,
    db: Session = Depends(get_db),
) -> ActivationCodeResponse:
    result = activation_service.request_activation_code(db, payload.email)
    return ActivationCodeResponse(
        message=result["message"], expires_in=CODE_TTL_MINUTES * 60
    )


@router.post("/resend", response_model=ActivationCodeResponse)
def resend_activation_code(
    payload: ActivationCodeRequest,
    db: Session = Depends(get_db),
) -> ActivationCodeResponse:
    result = activation_service.request_activation_code(db, payload.email)
    return ActivationCodeResponse(
        message=result["message"], expires_in=CODE_TTL_MINUTES * 60
    )


@router.post("", response_model=ActivationResponse)
def activate(
    payload: ActivationRequest,
    db: Session = Depends(get_db),
) -> ActivationResponse:
    activation_service.activate(db, payload.code, payload.password, payload.email)
    return ActivationResponse(message="Account activated. You can now sign in.")
