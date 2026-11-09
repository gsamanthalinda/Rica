from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from models import ProcessingStage


def get_by_id(db: Session, stage_id: int) -> ProcessingStage | None:
    return db.get(ProcessingStage, stage_id)


def get_by_name(db: Session, stage_name: str) -> ProcessingStage | None:
    return db.scalar(
        select(ProcessingStage).where(ProcessingStage.stage_name == stage_name)
    )


def get_by_order(db: Session, stage_order: int) -> ProcessingStage | None:
    return db.scalar(
        select(ProcessingStage).where(ProcessingStage.stage_order == stage_order)
    )


def list_all(db: Session) -> list[ProcessingStage]:
    return list(
        db.scalars(select(ProcessingStage).order_by(ProcessingStage.stage_order))
    )


def add(db: Session, stage: ProcessingStage) -> ProcessingStage:
    db.add(stage)
    db.flush()
    return stage


def delete_by_id(db: Session, stage_id: int) -> int:
    result = db.execute(
        delete(ProcessingStage).where(ProcessingStage.stage_id == stage_id)
    )
    return result.rowcount
