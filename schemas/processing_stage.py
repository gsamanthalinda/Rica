from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SMALLINT_MAX = 32767

StageName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
StageOrder = Annotated[int, Field(gt=0, le=SMALLINT_MAX)]


class ProcessingStageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_name: StageName
    stage_order: StageOrder


class ProcessingStageUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_name: StageName | None = None
    stage_order: StageOrder | None = None

    @model_validator(mode="after")
    def check_fields(self) -> "ProcessingStageUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one of stage_name or stage_order")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ProcessingStageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stage_id: int
    stage_name: str
    stage_order: int
