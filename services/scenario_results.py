from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions import NotFoundError
from models import Scenario, ScenarioResult
from repositories import scenario_results as result_repo


def get_result(db: Session, results_id: UUID) -> ScenarioResult:
    result = result_repo.get_by_id(db, results_id)
    if result is None:
        raise NotFoundError(f"Scenario result {results_id} not found")
    return result


def list_results(db: Session, scenario_id: UUID) -> list[ScenarioResult]:
    if db.get(Scenario, scenario_id) is None:
        raise NotFoundError(f"Scenario {scenario_id} not found")
    return result_repo.list_for_scenario(db, scenario_id)


def get_execution(
    db: Session, scenario_id: UUID, execution_number: int
) -> ScenarioResult:
    result = result_repo.get_by_execution(db, scenario_id, execution_number)
    if result is None:
        raise NotFoundError(
            f"Execution {execution_number} of scenario {scenario_id} not found"
        )
    return result


def scenario_has_results(db: Session, scenario_id: UUID) -> bool:
    return result_repo.exists_for_scenario(db, scenario_id)
