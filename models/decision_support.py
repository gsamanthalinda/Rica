import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    JSON,
    String,
    Text,
    Uuid,
    func,
)

from database import Base


class ScenarioDecision(Base):
    __tablename__ = "scenario_decisions"

    id = Column(
        Uuid(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    scenario_id = Column(
        Uuid(as_uuid=False),
        ForeignKey("scenarios.scenario_id"),
        nullable=False,
        index=True,
    )

    scenario_result_id = Column(
        Uuid(as_uuid=False),
        ForeignKey("scenario_results.results_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    lifecycle_state = Column(String(20), nullable=False, default="CALCULATED")
    assessment_outcome = Column(
        String(32),
        nullable=False,
        default="INSUFFICIENT_INFORMATION",
    )
    recommendation = Column(String(40), nullable=False, default="REVIEW_REQUIRED")
    assessment_summary = Column(Text, nullable=False, default="")
    findings = Column(JSON, nullable=False, default=list)
    recommendations = Column(JSON, nullable=False, default=list)

    assessed_by = Column(
        String(100),
        nullable=False,
        default="SYSTEM",
        server_default="SYSTEM",
    )
    assessment_method = Column(
        String(40),
        nullable=False,
        default="RULE_BASED_V1",
        server_default="RULE_BASED_V1",
    )

    assessed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
