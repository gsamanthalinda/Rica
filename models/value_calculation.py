import uuid

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import relationship

from database import Base


class ValueCalculation(Base):
    __tablename__ = "value_calculations"
    __table_args__ = (
        CheckConstraint("reference_price > 0", name="ck_valcalc_price_positive"),
        CheckConstraint(
            "contained_metal_tonnes >= 0", name="ck_valcalc_contained_nonneg"
        ),
        CheckConstraint(
            "recoverable_metal_tonnes >= 0", name="ck_valcalc_recoverable_nonneg"
        ),
        CheckConstraint("calculated_value >= 0", name="ck_valcalc_value_nonneg"),
        CheckConstraint("quantity >= 0", name="ck_valcalc_quantity_nonneg"),
        CheckConstraint("grade >= 0 AND grade <= 1", name="ck_valcalc_grade_range"),
        CheckConstraint(
            "recovery IS NULL OR (recovery >= 0 AND recovery <= 1)",
            name="ck_valcalc_recovery_range",
        ),
    )

    calculation_id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    batch_id = Column(Uuid, ForeignKey("mineral_batches.batch_id"), nullable=False)
    batch_history_id = Column(
        Uuid, ForeignKey("batch_history.history_id"), nullable=False
    )
    stage_id = Column(
        SmallInteger, ForeignKey("processing_stages.stage_id"), nullable=False
    )

    quantity = Column(Numeric(18, 6), nullable=False)
    quantity_unit = Column(String(20), nullable=False, default="tonnes")
    grade = Column(Numeric(8, 6), nullable=False)
    recovery = Column(Numeric(8, 6), nullable=True)

    reference_price = Column(Numeric(18, 6), nullable=False)
    current_price = Column(Numeric(18, 6), nullable=True)
    price_unit = Column(String(30), nullable=False)
    currency = Column(CHAR(3), nullable=False)
    price_source = Column(String(150), nullable=False)
    price_date = Column(Date, nullable=False)

    contained_metal_tonnes = Column(Numeric(18, 6), nullable=False)
    recoverable_metal_tonnes = Column(Numeric(18, 6), nullable=False)
    calculated_value = Column(Numeric(24, 6), nullable=False)

    calculated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    calculated_by = Column(Uuid, ForeignKey("users.user_id"), nullable=False)

    batch = relationship("MineralBatch", back_populates="value_calculations")
    batch_history = relationship("BatchHistory", back_populates="value_calculations")
    stage = relationship("ProcessingStage", back_populates="value_calculations")
    calculator = relationship("User", back_populates="value_calculations")
    baseline_for_scenarios = relationship(
        "Scenario", back_populates="baseline_calculation"
    )
