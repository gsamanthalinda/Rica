from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StageFields(BaseModel):
    occurred_at: datetime
    quantity_tonnes: Decimal | None = Field(default=None, ge=0)
    grade: Decimal | None = Field(default=None, ge=0, le=1)
    recovery: Decimal | None = Field(default=None, ge=0, le=1)
    reason: str | None = None

    source_type: str | None = None
    source_location: str | None = None
    feed_quantity_tonnes: Decimal | None = Field(default=None, ge=0)
    feed_grade: Decimal | None = Field(default=None, ge=0, le=1)
    output_quantity_tonnes: Decimal | None = Field(default=None, ge=0)
    output_grade: Decimal | None = Field(default=None, ge=0, le=1)
    moisture: Decimal | None = Field(default=None, ge=0, le=1)
    assay_document_url: str | None = None


class BatchHistoryCreate(StageFields):
    batch_id: UUID
    current_stage_id: int
    recorded_by: UUID


class BatchHistoryUpdate(StageFields):
    pass


class StageInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stage_name: str
    stage_order: int


class RecorderInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_name: str | None = None


class BatchHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    history_id: UUID
    batch_id: UUID
    current_stage_id: int
    recorded_by: UUID

    stage: StageInfo | None = Field(default=None, exclude=True)
    recorder: RecorderInfo | None = Field(default=None, exclude=True)

    quantity_tonnes: Decimal | None = None
    grade: Decimal | None = None
    recovery: Decimal | None = None
    reason: str | None = None

    source_type: str | None = None
    source_location: str | None = None

    feed_quantity_tonnes: Decimal | None = None
    feed_grade: Decimal | None = None

    output_quantity_tonnes: Decimal | None = None
    output_grade: Decimal | None = None

    moisture: Decimal | None = None
    assay_document_url: str | None = None

    occurred_at: datetime
    recorded_at: datetime
