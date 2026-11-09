from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.scenario import Scenario
from models.scenario_results import ScenarioResult


class ScenarioRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, scenario: Scenario) -> Scenario:
        self.db.add(scenario)
        self.db.flush()
        return scenario

    def get_by_id(self, scenario_id: UUID) -> Scenario | None:
        return self.db.get(Scenario, scenario_id)

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Scenario]:
        statement = (
            select(Scenario).order_by(Scenario.scenario_name).offset(skip).limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def get_by_batch(self, batch_id: UUID) -> list[Scenario]:
        statement = (
            select(Scenario)
            .where(Scenario.batch_id == batch_id)
            .order_by(Scenario.scenario_name)
        )
        return list(self.db.scalars(statement).all())

    def update(self, scenario: Scenario) -> Scenario:
        self.db.flush()
        return scenario

    def delete(self, scenario: Scenario) -> None:
        self.db.delete(scenario)
        self.db.flush()

    def get_results(self, scenario_id: UUID) -> list[ScenarioResult]:
        statement = (
            select(ScenarioResult)
            .where(ScenarioResult.scenario_id == scenario_id)
            .order_by(ScenarioResult.execution_number)
        )
        return list(self.db.scalars(statement).all())

    def get_next_execution_number(self, scenario_id: UUID) -> int:
        statement = (
            select(ScenarioResult.execution_number)
            .where(ScenarioResult.scenario_id == scenario_id)
            .order_by(ScenarioResult.execution_number.desc())
            .limit(1)
        )

        last_number = self.db.scalar(statement)
        return (last_number or 0) + 1
