from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.exceptions import ConflictError, NotFoundError
from models import ProcessingStage
from repositories import processing_stage as stage_repo
from schemas.processing_stage import ProcessingStageCreate, ProcessingStageUpdate


def get_stage(db: Session, stage_id: int) -> ProcessingStage:
    stage = stage_repo.get_by_id(db, stage_id)
    if stage is None:
        raise NotFoundError(f"Processing stage {stage_id} not found")
    return stage


def list_stages(db: Session) -> list[ProcessingStage]:
    return stage_repo.list_all(db)


def _check_unique(
    db: Session,
    *,
    stage_name: str | None,
    stage_order: int | None,
    exclude_id: int | None = None,
) -> None:
    if stage_name is not None:
        existing = stage_repo.get_by_name(db, stage_name)
        if existing is not None and existing.stage_id != exclude_id:
            raise ConflictError(f"A stage named '{stage_name}' already exists")
    if stage_order is not None:
        existing = stage_repo.get_by_order(db, stage_order)
        if existing is not None and existing.stage_id != exclude_id:
            raise ConflictError(f"Stage order {stage_order} is already in use")


def _commit(db: Session, conflict_message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(conflict_message) from exc


def create_stage(db: Session, data: ProcessingStageCreate) -> ProcessingStage:
    _check_unique(db, stage_name=data.stage_name, stage_order=data.stage_order)
    stage = stage_repo.add(
        db, ProcessingStage(stage_name=data.stage_name, stage_order=data.stage_order)
    )
    _commit(db, "Stage name or stage order is already in use")
    db.refresh(stage)
    return stage


def update_stage(
    db: Session, stage_id: int, data: ProcessingStageUpdate
) -> ProcessingStage:
    stage = get_stage(db, stage_id)
    changes = data.model_dump(exclude_unset=True)
    _check_unique(
        db,
        stage_name=changes.get("stage_name"),
        stage_order=changes.get("stage_order"),
        exclude_id=stage_id,
    )
    for field, value in changes.items():
        setattr(stage, field, value)
    _commit(db, "Stage name or stage order is already in use")
    db.refresh(stage)
    return stage


def delete_stage(db: Session, stage_id: int) -> None:
    get_stage(db, stage_id)
    try:
        stage_repo.delete_by_id(db, stage_id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            f"Processing stage {stage_id} is in use by batches, batch history, "
            "value calculations or scenarios and cannot be deleted"
        ) from exc
