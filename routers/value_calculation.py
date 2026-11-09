from datetime import date

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from core.auth import get_current_user
from database import get_db
from models import User
from services.value_calculation_service import ValueCalculationService
from schemas.value_calculation import ValueCalculationResponse, ValueTableResponse

router = APIRouter(tags=["value_calculation"])


@router.post(
    "/batches/{batch_id}/calculate",
    response_model=ValueCalculationResponse,
    status_code=status.HTTP_201_CREATED,
)
def calculate_batch_value(
    batch_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ValueCalculationService(db)
    return service.calculate_batch_value(batch_id=batch_id, current_user=current_user)


@router.get("/batches/{batch_id}/values", response_model=List[ValueCalculationResponse])
def get_values_for_batch(
    batch_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ValueCalculationService(db)
    return service.get_calculations_by_batch(batch_id, current_user=current_user)


@router.get("/batches/{batch_id}/value-table", response_model=ValueTableResponse)
def get_value_table(
    batch_id: UUID = Path(...),
    price_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ValueCalculationService(db)
    return service.get_value_table(
        batch_id, current_user=current_user, price_date=price_date
    )


@router.get(
    "/history/{history_id}/values", response_model=List[ValueCalculationResponse]
)
def get_values_for_history(
    history_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ValueCalculationService(db)
    return service.get_calculations_by_batch_history(
        history_id, current_user=current_user
    )
