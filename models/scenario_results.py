import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import relationship

from database import Base


class ScenarioResult(Base):
    __tablename__ = "scenario_results"
    __table_args__ = (
        UniqueConstraint(
            "scenario_id", "execution_number", name="uq_results_scenario_execution"
        ),
        CheckConstraint("execution_number > 0", name="ck_results_execution_positive"),
        CheckConstraint("simulated_value >= 0", name="ck_results_simulated_nonneg"),
        CheckConstraint("baseline_value >= 0", name="ck_results_baseline_nonneg"),
    )

    results_id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    scenario_id = Column(Uuid, ForeignKey("scenarios.scenario_id"), nullable=False)
    execution_number = Column(Integer, nullable=False)
    simulated_value = Column(Numeric(24, 6), nullable=False)
    baseline_value = Column(Numeric(24, 6), nullable=False)
    value_difference = Column(Numeric(24, 6), nullable=False)
    percentage_difference = Column(Numeric(12, 6), nullable=True)
    calculated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    scenario = relationship("Scenario", back_populates="results")
