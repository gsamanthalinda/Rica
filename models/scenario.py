import uuid

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Column,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Uuid,
)
from sqlalchemy.orm import relationship

from database import Base


class Scenario(Base):
    __tablename__ = "scenarios"
    __table_args__ = (
        CheckConstraint("assumed_quantity >= 0", name="ck_scenarios_quantity_nonneg"),
        CheckConstraint(
            "assumed_grade >= 0 AND assumed_grade <= 1", name="ck_scenarios_grade_range"
        ),
        CheckConstraint(
            "assumed_recovery >= 0 AND assumed_recovery <= 1",
            name="ck_scenarios_recovery_range",
        ),
        CheckConstraint("assumed_price > 0", name="ck_scenarios_price_positive"),
    )

    scenario_id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    batch_id = Column(Uuid, ForeignKey("mineral_batches.batch_id"), nullable=False)
    baseline_calculation_id = Column(
        Uuid, ForeignKey("value_calculations.calculation_id"), nullable=False
    )
    created_by = Column(Uuid, ForeignKey("users.user_id"), nullable=False)
    scenario_name = Column(String(150), nullable=False)
    assumed_quantity = Column(Numeric(18, 6), nullable=False)
    assumed_grade = Column(Numeric(8, 6), nullable=False)
    assumed_recovery = Column(Numeric(8, 6), nullable=False)
    assumed_price = Column(Numeric(18, 6), nullable=False)
    assumed_stage_id = Column(
        SmallInteger, ForeignKey("processing_stages.stage_id"), nullable=False
    )
    price_unit = Column(String(30), nullable=False)
    currency = Column(CHAR(3), nullable=False)

    batch = relationship("MineralBatch", back_populates="scenarios")
    baseline_calculation = relationship(
        "ValueCalculation", back_populates="baseline_for_scenarios"
    )
    creator = relationship("User", back_populates="scenarios")
    assumed_stage = relationship("ProcessingStage", back_populates="scenarios")
    results = relationship(
        "ScenarioResult",
        back_populates="scenario",
        order_by="ScenarioResult.execution_number",
    )
