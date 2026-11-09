from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user
from database import get_transactional_db
from models.user import User
from schemas.decision_support import AssessmentContext, ScenarioDecisionRead
from services.decision_support_service import DecisionService

router = APIRouter(
    prefix="/decision_support",
    tags=["Decision_support"],
    dependencies=[Depends(get_current_user)],
)


class AssessBody(BaseModel):
    """Request body: who is assessing comes from the login, not the client."""

    context: AssessmentContext | None = None


@router.post(
    "/assess",
    response_model=ScenarioDecisionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Assess (or reassess) an existing scenario result",
)
def assess_scenario(
    scenario_result_id: UUID,
    payload: AssessBody | None = None,
    db: Session = Depends(get_transactional_db),
    user: User = Depends(get_current_user),
):
    return DecisionService(db).assess(
        result_id=scenario_result_id,
        user=user,
        context=payload.context if payload else None,
    )


@router.get("/{decision_id}", response_model=ScenarioDecisionRead)
def get_decision(
    decision_id: UUID,
    db: Session = Depends(get_transactional_db),
    user: User = Depends(get_current_user),
):
    return DecisionService(db).get(decision_id, user)


@router.get(
    "/scenario/{scenario_id}",
    response_model=list[ScenarioDecisionRead],
)
def list_scenario_decisions(
    scenario_id: UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_transactional_db),
    user: User = Depends(get_current_user),
):
    return DecisionService(db).list_for_scenario(scenario_id, user, limit, offset)


@router.delete("/{decision_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_decision(
    decision_id: UUID,
    db: Session = Depends(get_transactional_db),
    user: User = Depends(get_current_user),
):
    DecisionService(db).delete(decision_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
