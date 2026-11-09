from uuid import UUID

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from database import get_db
from schemas.scenario_results import ScenarioResultResponse
from services import scenario_results as result_service

router = APIRouter(tags=["Scenario Results"])

ERRORS_404 = {404: {"description": "Scenario or result not found"}}


@router.get(
    "/scenario-results/{results_id}",
    response_model=ScenarioResultResponse,
    responses=ERRORS_404,
)
def get_scenario_result(
    results_id: UUID, db: Session = Depends(get_db)
) -> ScenarioResultResponse:
    return result_service.get_result(db, results_id)


@router.get(
    "/scenarios/{scenario_id}/results",
    response_model=list[ScenarioResultResponse],
    responses=ERRORS_404,
)
def list_scenario_results(
    scenario_id: UUID, db: Session = Depends(get_db)
) -> list[ScenarioResultResponse]:
    return result_service.list_results(db, scenario_id)


@router.get(
    "/scenarios/{scenario_id}/results/{execution_number}",
    response_model=ScenarioResultResponse,
    responses=ERRORS_404,
)
def get_scenario_execution(
    scenario_id: UUID,
    execution_number: int = Path(gt=0),
    db: Session = Depends(get_db),
) -> ScenarioResultResponse:
    return result_service.get_execution(db, scenario_id, execution_number)
