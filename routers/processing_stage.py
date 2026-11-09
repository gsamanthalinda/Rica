from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.processing_stage import (
    SMALLINT_MAX,
    ProcessingStageCreate,
    ProcessingStageResponse,
    ProcessingStageUpdate,
)
from services import processing_stage as stage_service

router = APIRouter(prefix="/processing-stages", tags=["Processing Stages"])

StageId = Path(gt=0, le=SMALLINT_MAX)

ERRORS_404 = {404: {"description": "Processing stage not found"}}
ERRORS_409 = {409: {"description": "Duplicate name/order, or stage in use"}}


@router.post(
    "",
    response_model=ProcessingStageResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS_409,
)
def create_processing_stage(
    data: ProcessingStageCreate, db: Session = Depends(get_db)
) -> ProcessingStageResponse:
    return stage_service.create_stage(db, data)


@router.get("", response_model=list[ProcessingStageResponse])
def list_processing_stages(
    db: Session = Depends(get_db),
) -> list[ProcessingStageResponse]:
    return stage_service.list_stages(db)


@router.get("/{stage_id}", response_model=ProcessingStageResponse, responses=ERRORS_404)
def get_processing_stage(
    stage_id: int = StageId, db: Session = Depends(get_db)
) -> ProcessingStageResponse:
    return stage_service.get_stage(db, stage_id)


@router.patch(
    "/{stage_id}",
    response_model=ProcessingStageResponse,
    responses={**ERRORS_404, **ERRORS_409},
)
def update_processing_stage(
    data: ProcessingStageUpdate,
    stage_id: int = StageId,
    db: Session = Depends(get_db),
) -> ProcessingStageResponse:
    return stage_service.update_stage(db, stage_id, data)


@router.delete(
    "/{stage_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**ERRORS_404, **ERRORS_409},
)
def delete_processing_stage(
    stage_id: int = StageId, db: Session = Depends(get_db)
) -> None:
    stage_service.delete_stage(db, stage_id)
