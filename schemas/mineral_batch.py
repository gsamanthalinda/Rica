import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from models.mineral_batch import BatchStatus, SourceType


class MineralBatchCreate(BaseModel):
    mineral_type: str = Field(default="COPPER", max_length=100)
    source_type: SourceType
    stage_id: int
    quantity_tonnes: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    grade: Decimal = Field(ge=0, le=1, max_digits=8, decimal_places=6)
    recovery: Decimal | None = Field(
        default=None, ge=0, le=1, max_digits=8, decimal_places=6
    )


class MineralBatchUpdate(BaseModel):
    source_type: SourceType | None = None
    quantity_tonnes: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=6
    )
    grade: Decimal | None = Field(
        default=None, ge=0, le=1, max_digits=8, decimal_places=6
    )
    recovery: Decimal | None = Field(
        default=None, ge=0, le=1, max_digits=8, decimal_places=6
    )
    status: BatchStatus | None = None


class MineralBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    batch_id: uuid.UUID
    created_by: uuid.UUID
    batch_code: str
    mineral_type: str
    source_type: SourceType
    quantity_tonnes: Decimal
    grade: Decimal
    recovery: Decimal | None
    created_at: datetime
    status: BatchStatus
    assay_original_filename: str | None = None
