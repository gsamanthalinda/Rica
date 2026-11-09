import enum
import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    LargeBinary,
    Numeric,
    SmallInteger,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import relationship

from database import Base


class SourceType(str, enum.Enum):
    SELF_EXTRACTED = "SELF_EXTRACTED"
    PURCHASED = "PURCHASED"


class BatchStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class MineralBatch(Base):
    __tablename__ = "mineral_batches"
    __table_args__ = (
        CheckConstraint("mineral_type = 'COPPER'", name="ck_batches_mineral_copper"),
        CheckConstraint("quantity_tonnes >= 0", name="ck_batches_quantity_nonneg"),
        CheckConstraint("grade >= 0 AND grade <= 1", name="ck_batches_grade_range"),
        CheckConstraint(
            "recovery IS NULL OR (recovery >= 0 AND recovery <= 1)",
            name="ck_batches_recovery                                                                                                                           =_range",
        ),
    )

    batch_id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    created_by = Column(Uuid, ForeignKey("users.user_id"), nullable=False)
    batch_code = Column(String(100), nullable=False, unique=True)
    mineral_type = Column(
        String(100), nullable=False, default="COPPER", server_default="COPPER"
    )
    source_type = Column(Enum(SourceType, name="source_type"), nullable=False)
    quantity_tonnes = Column(Numeric(18, 6), nullable=False)
    grade = Column(Numeric(8, 6), nullable=False)
    recovery = Column(Numeric(8, 6), nullable=True)
    stage_id = Column(
        SmallInteger, ForeignKey("processing_stages.stage_id"), nullable=False
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status = Column(
        Enum(BatchStatus, name="batch_status"),
        nullable=False,
        default=BatchStatus.ACTIVE,
        server_default=BatchStatus.ACTIVE.value,
    )

    assay_file_data = Column(LargeBinary, nullable=True)
    assay_original_filename = Column(String(255), nullable=True)

    creator = relationship("User", back_populates="batches")
    stage = relationship("ProcessingStage", back_populates="batches")
    history = relationship(
        "BatchHistory", back_populates="batch", order_by="BatchHistory.occurred_at"
    )
    value_calculations = relationship("ValueCalculation", back_populates="batch")
    scenarios = relationship("Scenario", back_populates="batch")
