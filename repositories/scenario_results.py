from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import ScenarioResult


def get_by_id(db: Session, results_id: UUID) -> ScenarioResult | None:
    return db.get(ScenarioResult, results_id)


def list_for_scenario(db: Session, scenario_id: UUID) -> list[ScenarioResult]:
    return list(
        db.scalars(
            select(ScenarioResult)
            .where(ScenarioResult.scenario_id == scenario_id)
            .order_by(ScenarioResult.execution_number)
        )
    )


def get_by_execution(
    db: Session, scenario_id: UUID, execution_number: int
) -> ScenarioResult | None:
    return db.scalar(
        select(ScenarioResult).where(
            ScenarioResult.scenario_id == scenario_id,
            ScenarioResult.execution_number == execution_number,
        )
    )


def exists_for_scenario(db: Session, scenario_id: UUID) -> bool:
    return (
        db.scalar(
            select(ScenarioResult.results_id)
            .where(ScenarioResult.scenario_id == scenario_id)
            .limit(1)
        )
        is not None
    )
