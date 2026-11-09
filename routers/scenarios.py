from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from core.auth import get_current_user
from database import get_db
from models.user import User
from services.scenario_service import ScenarioService, service_call
from schemas.scenario import (
    ScenarioCreate,
    ScenarioUpdate,
    ScenarioResponse,
    ScenarioResultResponse,
)

router = APIRouter(
    prefix="/scenarios",
    tags=["Scenarios"],
    dependencies=[Depends(get_current_user)],
)


@router.post("/", response_model=ScenarioResponse, status_code=201)
def create_scenario(
    data: ScenarioCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return service_call(
        lambda: ScenarioService(db).create_scenario(user, **data.model_dump())
    )


@router.get("/", response_model=list[ScenarioResponse])
def list_scenarios(
    batch_id: UUID | None = None,
    created_by: UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return ScenarioService(db).list_scenarios(
        user, batch_id=batch_id, created_by=created_by
    )


@router.get("/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(
    scenario_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return service_call(lambda: ScenarioService(db).get_scenario(user, scenario_id))


@router.put("/{scenario_id}", response_model=ScenarioResponse)
def update_scenario(
    scenario_id: UUID,
    data: ScenarioUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return service_call(
        lambda: ScenarioService(db).update_scenario(user, scenario_id, data)
    )


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    scenario_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service_call(lambda: ScenarioService(db).delete_scenario(user, scenario_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{scenario_id}/execute", response_model=ScenarioResultResponse, status_code=201
)
def execute_scenario(
    scenario_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return service_call(lambda: ScenarioService(db).execute_scenario(user, scenario_id))
