from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ScenarioBase(BaseModel):
    scenario_name: str = Field(min_length=1, max_length=150)
    assumed_quantity: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    assumed_grade: Decimal = Field(ge=0, le=1, max_digits=8, decimal_places=6)
    assumed_recovery: Decimal = Field(ge=0, le=1, max_digits=8, decimal_places=6)
    assumed_price: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    assumed_stage_id: int
    price_unit: str = Field(min_length=1, max_length=30)
    currency: str = Field(min_length=3, max_length=3)


class ScenarioCreate(ScenarioBase):
    batch_id: UUID
    baseline_calculation_id: UUID


class ScenarioUpdate(BaseModel):
    scenario_name: str | None = Field(default=None, min_length=1, max_length=150)
    assumed_quantity: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=6
    )
    assumed_grade: Decimal | None = Field(
        default=None, ge=0, le=1, max_digits=8, decimal_places=6
    )
    assumed_recovery: Decimal | None = Field(
        default=None, ge=0, le=1, max_digits=8, decimal_places=6
    )
    assumed_price: Decimal | None = Field(
        default=None, gt=0, max_digits=18, decimal_places=6
    )
    assumed_stage_id: int | None = None
    price_unit: str | None = Field(default=None, min_length=1, max_length=30)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class ScenarioResponse(ScenarioBase):
    model_config = ConfigDict(from_attributes=True)

    scenario_id: UUID
    batch_id: UUID
    baseline_calculation_id: UUID
    created_by: UUID


class ScenarioResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    results_id: UUID
    scenario_id: UUID
    execution_number: int
    simulated_value: Decimal
    baseline_value: Decimal
    value_difference: Decimal
    percentage_difference: Decimal | None
    calculated_at: object
