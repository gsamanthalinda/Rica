from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.user import User
from models.decision_support import ScenarioDecision
from repositories.decision_repository import ScenarioDecisionRepository
from schemas.decision_support import AssessmentContext
from services.decision_rules import ASSESSMENT_METHOD, evaluate_scenario
from services.mineral_batch import _authorize
from services.scenario_service import SCENARIO_ROLES, ScenarioService, service_call


MAX_PAGE_SIZE = 500


class DecisionService:
    """Orchestrates scenario assessments."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = ScenarioDecisionRepository(db)

    def _load_authorized_result(self, user: User, result_id: UUID, not_found: str):
        result = self.repo.get_result(result_id)

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=not_found,
            )

        try:
            scenario = service_call(
                lambda: ScenarioService(self.db).get_scenario(user, result.scenario_id)
            )
        except HTTPException as exc:
            if exc.status_code == status.HTTP_404_NOT_FOUND:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=not_found,
                ) from exc
            raise

        return result, scenario

    def assess(
        self,
        result_id: UUID,
        user: User,
        context: AssessmentContext | None = None,
    ) -> ScenarioDecision:
        _authorize(user, SCENARIO_ROLES)

        result, scenario = self._load_authorized_result(
            user,
            result_id,
            "Scenario result not found.",
        )

        rules_input = self._rules_input(scenario)
        evaluation = evaluate_scenario(
            rules_input,
            result,
            context=context.model_dump(exclude_none=True) if context else None,
            stage_name=(
                scenario.assumed_stage.stage_name if scenario.assumed_stage else None
            ),
        )

        decision = self.repo.get_by_result_id(result_id)

        if decision is None:
            decision = ScenarioDecision(
                scenario_id=str(scenario.scenario_id),
                scenario_result_id=str(result_id),
            )

        self._apply(
            decision,
            evaluation,
            str(user.user_id),
        )

        return self.repo.save(decision)

    def get(self, decision_id: UUID, user: User) -> ScenarioDecision:
        _authorize(user, SCENARIO_ROLES)

        decision = self.repo.get_by_id(decision_id)

        if decision is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scenario decision not found.",
            )

        self._load_authorized_result(
            user,
            UUID(str(decision.scenario_result_id)),
            "Scenario decision not found.",
        )

        return decision

    def list_for_scenario(
        self,
        scenario_id: UUID,
        user: User,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ScenarioDecision]:
        _authorize(user, SCENARIO_ROLES)

        if limit < 1:
            raise HTTPException(
                status_code=422,
                detail="Limit must be at least 1.",
            )

        if offset < 0:
            raise HTTPException(
                status_code=422,
                detail="Offset cannot be negative.",
            )

        service_call(lambda: ScenarioService(self.db).get_scenario(user, scenario_id))

        return self.repo.list_for_scenario(
            scenario_id,
            limit=min(limit, MAX_PAGE_SIZE),
            offset=offset,
        )

    def delete(self, decision_id: UUID, user: User) -> None:
        decision = self.get(decision_id, user)
        self.repo.delete(decision)

    @staticmethod
    def _rules_input(scenario) -> SimpleNamespace:
        """Convert scenario values to the units expected by the rules.

        Grade is stored as a fraction (e.g. 0.075) but the rules
        expect a percentage (e.g. 7.5).
        """
        grade = scenario.assumed_grade

        return SimpleNamespace(
            assumed_quantity=scenario.assumed_quantity,
            assumed_grade=(None if grade is None else Decimal(str(grade)) * 100),
            assumed_recovery=scenario.assumed_recovery,
            assumed_price=scenario.assumed_price,
            assumed_stage_id=scenario.assumed_stage_id,
        )

    @staticmethod
    def _apply(
        decision: ScenarioDecision,
        evaluation: dict,
        assessed_by: str,
    ) -> None:
        decision.lifecycle_state = (
            "BLOCKED" if evaluation.get("has_hard_blocker", False) else "ASSESSED"
        )

        decision.assessment_outcome = evaluation["assessment_outcome"]
        decision.recommendation = evaluation["recommendation"]
        decision.assessment_summary = evaluation["assessment_summary"]
        decision.findings = evaluation["findings"]
        decision.recommendations = evaluation["recommendations"]
        decision.assessed_by = assessed_by
        decision.assessment_method = ASSESSMENT_METHOD
        decision.assessed_at = datetime.now(timezone.utc)
