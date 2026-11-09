import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from core.auth import get_current_user
from database import get_db
from models import User
from schemas.batch_history import BatchHistoryRead
from services import batch_history_service as service


# Every route requires a valid logged-in user
router = APIRouter(
    prefix="/batch-history",
    tags=["Batch History"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/",
    response_model=BatchHistoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_batch_history_entry(
    batch_id: UUID = Form(...),
    current_stage_id: int = Form(...),
    occurred_at: datetime = Form(...),
    quantity_tonnes: Decimal | None = Form(None),
    grade: Decimal | None = Form(None),
    recovery: Decimal | None = Form(None),
    reason: str | None = Form(None),
    source_type: str | None = Form(None),
    source_location: str | None = Form(None),
    feed_quantity_tonnes: Decimal | None = Form(None),
    feed_grade: Decimal | None = Form(None),
    output_quantity_tonnes: Decimal | None = Form(None),
    output_grade: Decimal | None = Form(None),
    moisture: Decimal | None = Form(None),
    assay_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    fields = {
        "batch_id": batch_id,
        "current_stage_id": current_stage_id,
        "recorded_by": user.user_id,  # from the token, never from the client
        "occurred_at": occurred_at,
        "quantity_tonnes": quantity_tonnes,
        "grade": grade,
        "recovery": recovery,
        "reason": reason,
        "source_type": source_type,
        "source_location": source_location,
        "feed_quantity_tonnes": feed_quantity_tonnes,
        "feed_grade": feed_grade,
        "output_quantity_tonnes": output_quantity_tonnes,
        "output_grade": output_grade,
        "moisture": moisture,
    }
    payload = {key: value for key, value in fields.items() if value is not None}

    return service.create_batch_history_with_assay(
        db,
        user,
        json.dumps(payload, default=str),
        assay_file,
    )


@router.get("/batch/{batch_id}", response_model=list[BatchHistoryRead])
def get_batch_history_entries(
    batch_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return service.get_batch_history_by_batch(db, user, batch_id, skip, limit)


@router.get("/{history_id}", response_model=BatchHistoryRead)
def get_batch_history_entry(
    history_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return service.get_batch_history_by_id_or_404(db, user, history_id)


@router.put("/{history_id}", response_model=BatchHistoryRead)
def update_batch_history_entry(
    history_id: UUID,
    occurred_at: datetime = Form(...),
    quantity_tonnes: Decimal | None = Form(None),
    grade: Decimal | None = Form(None),
    recovery: Decimal | None = Form(None),
    reason: str | None = Form(None),
    source_type: str | None = Form(None),
    source_location: str | None = Form(None),
    feed_quantity_tonnes: Decimal | None = Form(None),
    feed_grade: Decimal | None = Form(None),
    output_quantity_tonnes: Decimal | None = Form(None),
    output_grade: Decimal | None = Form(None),
    moisture: Decimal | None = Form(None),
    assay_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    fields = {
        "occurred_at": occurred_at,
        "quantity_tonnes": quantity_tonnes,
        "grade": grade,
        "recovery": recovery,
        "reason": reason,
        "source_type": source_type,
        "source_location": source_location,
        "feed_quantity_tonnes": feed_quantity_tonnes,
        "feed_grade": feed_grade,
        "output_quantity_tonnes": output_quantity_tonnes,
        "output_grade": output_grade,
        "moisture": moisture,
    }
    payload = {key: value for key, value in fields.items() if value is not None}

    return service.update_batch_history_with_assay(
        db,
        user,
        history_id,
        json.dumps(payload, default=str),
        assay_file,
    )


@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_batch_history_entry(
    history_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service.delete_batch_history_or_404(db, user, history_id)
    return None


@router.get("/files/assay/{filename}")
def read_assay_document(
    filename: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return service.get_assay_document(db, user, filename)
