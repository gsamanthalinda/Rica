from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScenarioResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    results_id: UUID
    scenario_id: UUID
    execution_number: int
    simulated_value: Decimal
    baseline_value: Decimal
    value_difference: Decimal
    percentage_difference: Decimal | None
    calculated_at: datetime
