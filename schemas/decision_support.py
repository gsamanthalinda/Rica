from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AssessmentContext(BaseModel):
    """Optional operational facts. Anything left out is treated as an
    unverified, ideal assumption and is disclosed in the assessment."""

    ore_type: (
        Literal[
            "SULPHIDE",
            "MIXED",
            "OXIDE",
            "NON_PRIMARY_SULPHIDE",
            "UNDERGROUND_SULPHIDE",
        ]
        | None
    ) = None
    mining_method: Literal["OPEN_PIT", "UNDERGROUND"] | None = None

    technical_recovery_min: float | None = Field(default=None, ge=0, le=1)
    technical_recovery_max: float | None = Field(default=None, ge=0, le=1)

    required_capacity_tonnes: float | None = Field(default=None, ge=0)
    available_capacity_tonnes: float | None = Field(default=None, ge=0)

    regulatory_status: (
        Literal[
            "CONFIRMED",
            "NOT_CONFIRMED",
            "NOT_APPLICABLE",
        ]
        | None
    ) = None

    infrastructure_status: (
        Literal[
            "AVAILABLE",
            "LIMITED",
            "UNAVAILABLE",
        ]
        | None
    ) = None

    operation_specific_technical_evidence: bool | None = None
    cost_data_complete: bool | None = None
    downside_price: float | None = Field(default=None, gt=0)


class AssessScenarioRequest(BaseModel):
    assessed_by: UUID
    context: AssessmentContext = Field(default_factory=AssessmentContext)


class AssessmentFinding(BaseModel):
    rule_code: str
    category: str
    outcome: Literal[
        "PASS",
        "WARNING",
        "FAIL",
        "NOT_ASSESSED",
    ]
    severity: Literal["INFO", "WARNING", "BLOCKER"]
    message: str
    actual_value: Any | None = None
    expected_value: Any | None = None


class ScenarioDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scenario_result_id: str

    lifecycle_state: Literal[
        "CALCULATED",
        "ASSESSED",
        "BLOCKED",
    ]

    assessment_outcome: Literal[
        "VIABLE",
        "CONDITIONALLY_VIABLE",
        "NOT_VIABLE",
        "INSUFFICIENT_INFORMATION",
    ]

    recommendation: Literal[
        "PROCEED",
        "PROCEED_AFTER_VALIDATION",
        "REVISE_SCENARIO",
        "REVIEW_REQUIRED",
    ]

    assessment_summary: str
    findings: list[dict[str, Any]]
    recommendations: list[str]

    assessed_by: str
    assessment_method: str

    assessed_at: datetime | None
    created_at: datetime
    updated_at: datetime
