import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import relationship

from database import Base


class BatchHistory(Base):
    __tablename__ = "batch_history"

    __table_args__ = (
        CheckConstraint(
            "quantity_tonnes IS NULL OR quantity_tonnes >= 0",
            name="ck_history_quantity_nonneg",
        ),
        CheckConstraint(
            "grade IS NULL OR (grade >= 0 AND grade <= 1)",
            name="ck_history_grade_range",
        ),
        CheckConstraint(
            "recovery IS NULL OR (recovery >= 0 AND recovery <= 1)",
            name="ck_history_recovery_range",
        ),
        UniqueConstraint(
            "batch_id",
            "current_stage_id",
            name="uq_batch_history_batch_stage",
        ),
    )

    history_id = Column(Uuid, primary_key=True, default=uuid.uuid4)

    batch_id = Column(
        Uuid,
        ForeignKey("mineral_batches.batch_id"),
        nullable=False,
    )
    current_stage_id = Column(
        SmallInteger,
        ForeignKey("processing_stages.stage_id"),
        nullable=False,
    )
    recorded_by = Column(
        Uuid,
        ForeignKey("users.user_id"),
        nullable=False,
    )

    quantity_tonnes = Column(Numeric(18, 6), nullable=True)
    grade = Column(Numeric(8, 6), nullable=True)
    recovery = Column(Numeric(8, 6), nullable=True)
    reason = Column(Text, nullable=True)
    source_type = Column(String(100), nullable=True)
    source_location = Column(String(255), nullable=True)

    feed_quantity_tonnes = Column(Numeric(18, 6), nullable=True)
    feed_grade = Column(Numeric(8, 6), nullable=True)

    output_quantity_tonnes = Column(Numeric(18, 6), nullable=True)
    output_grade = Column(Numeric(8, 6), nullable=True)

    moisture = Column(Numeric(8, 6), nullable=True)
    assay_document_url = Column(Text, nullable=True)

    occurred_at = Column(DateTime(timezone=True), nullable=False)
    recorded_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    batch = relationship("MineralBatch", back_populates="history")
    stage = relationship(
        "ProcessingStage",
        back_populates="history_records",
    )
    recorder = relationship("User", back_populates="history_events")
    value_calculations = relationship(
        "ValueCalculation",
        back_populates="batch_history",
    )
