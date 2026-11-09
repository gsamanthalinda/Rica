from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from models.batch_history import BatchHistory
from models.mineral_batch import MineralBatch
from models.processing_stage import ProcessingStage


def _with_relations(db: Session):
    return db.query(BatchHistory).options(
        joinedload(BatchHistory.stage),
        joinedload(BatchHistory.recorder),
    )


def get_mineral_batch_by_id(
    db: Session,
    batch_id: UUID,
):
    return db.get(MineralBatch, batch_id)


def get_processing_stage_by_id(
    db: Session,
    stage_id: int,
):
    return db.get(ProcessingStage, stage_id)


def get_latest_stage_for_batch(
    db: Session,
    batch_id: UUID,
):
    return (
        db.query(ProcessingStage)
        .join(
            BatchHistory,
            BatchHistory.current_stage_id == ProcessingStage.stage_id,
        )
        .filter(
            BatchHistory.batch_id == batch_id,
        )
        .order_by(
            ProcessingStage.stage_order.desc(),
        )
        .first()
    )


def get_batch_history_by_id(
    db: Session,
    history_id: UUID,
):
    return (
        _with_relations(db)
        .filter(
            BatchHistory.history_id == history_id,
        )
        .first()
    )


def get_batch_history_by_batch(
    db: Session,
    batch_id: UUID,
    skip: int = 0,
    limit: int = 100,
):
    return (
        _with_relations(db)
        .join(
            ProcessingStage,
            BatchHistory.current_stage_id == ProcessingStage.stage_id,
        )
        .filter(
            BatchHistory.batch_id == batch_id,
        )
        .order_by(
            ProcessingStage.stage_order.asc(),
            BatchHistory.occurred_at.asc(),
            BatchHistory.history_id.asc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_batch_history_by_batch_and_stage(
    db: Session,
    batch_id: UUID,
    stage_id: int,
):
    return (
        db.query(BatchHistory)
        .filter(
            BatchHistory.batch_id == batch_id,
            BatchHistory.current_stage_id == stage_id,
        )
        .first()
    )


def create_batch_history(
    db: Session,
    history: BatchHistory,
):
    db.add(history)
    db.flush()
    db.refresh(history)
    return history


def update_batch_history(
    db: Session,
    history: BatchHistory,
):
    db.flush()
    db.refresh(history)
    return history


def delete_batch_history(
    db: Session,
    history: BatchHistory,
):
    db.delete(history)
    db.flush()


def update_mineral_batch(
    db: Session,
    batch: MineralBatch,
):
    db.flush()
    db.refresh(batch)
    return batch
