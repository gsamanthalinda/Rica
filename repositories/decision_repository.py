from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from models.decision_support import ScenarioDecision
from models.scenario import Scenario
from models.scenario_results import ScenarioResult


class ScenarioDecisionRepository:
    """All database access for decision support. Queries and flushes only: no
    business rules, no exception handling, no commit/rollback (the session
    dependency owns the transaction)."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, decision_id: UUID) -> ScenarioDecision | None:
        return (
            self.db.query(ScenarioDecision)
            .filter(ScenarioDecision.id == str(decision_id))
            .first()
        )

    def get_by_result_id(self, result_id: UUID) -> ScenarioDecision | None:
        return (
            self.db.query(ScenarioDecision)
            .filter(ScenarioDecision.scenario_result_id == str(result_id))
            .first()
        )

    def list_for_scenario(
        self, scenario_id: UUID, limit: int, offset: int
    ) -> list[ScenarioDecision]:
        # A decision belongs to a scenario through its result.
        return (
            self.db.query(ScenarioDecision)
            .join(
                ScenarioResult,
                ScenarioResult.results_id == ScenarioDecision.scenario_result_id,
            )
            .filter(ScenarioResult.scenario_id == scenario_id)
            .order_by(ScenarioDecision.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def save(self, decision: ScenarioDecision) -> ScenarioDecision:

        self.db.add(decision)
        self.db.flush()
        self.db.refresh(decision)
        return decision

    def delete(self, decision: ScenarioDecision) -> None:
        self.db.delete(decision)
        self.db.flush()

    def get_result(self, result_id: UUID) -> ScenarioResult | None:
        return (
            self.db.query(ScenarioResult)
            .filter(ScenarioResult.results_id == result_id)
            .first()
        )

    def get_scenario_for_assessment(self, scenario_id) -> Scenario | None:

        return (
            self.db.query(Scenario)
            .options(
                joinedload(Scenario.assumed_stage),
                joinedload(Scenario.baseline_calculation),
                joinedload(Scenario.batch),
            )
            .filter(Scenario.scenario_id == scenario_id)
            .first()
        )
