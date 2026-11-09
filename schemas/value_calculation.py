from pydantic import BaseModel, ConfigDict, Field
from datetime import date, datetime
from decimal import Decimal
import uuid
from typing import List, Optional


class ValueCalculationCreate(BaseModel):
    batch_id: uuid.UUID
    batch_history_id: uuid.UUID
    stage_id: int
    calculated_by: uuid.UUID


class ValueCalculationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    calculation_id: uuid.UUID
    batch_id: uuid.UUID
    batch_history_id: uuid.UUID
    stage_id: int
    quantity: Decimal = Field(..., ge=0)
    quantity_unit: str = Field(default="tonnes")
    grade: Decimal = Field(..., ge=0, le=1)
    recovery: Optional[Decimal] = Field(None, ge=0, le=1)
    reference_price: Decimal = Field(..., gt=0)
    price_unit: str = Field(default="USD/tonne")
    currency: str = Field(default="USD")
    price_source: str = Field(default="Metals-API (LME copper)")
    price_date: date
    contained_metal_tonnes: Decimal = Field(..., ge=0)
    recoverable_metal_tonnes: Decimal = Field(..., ge=0)
    calculated_value: Decimal = Field(..., ge=0)
    calculated_at: datetime
    calculated_by: uuid.UUID


class ValueTableRow(BaseModel):
    stage_id: int
    stage_name: str
    stage_order: int
    occurred_at: datetime
    quantity_tonnes: Decimal
    grade: Decimal
    contained_metal_tonnes: Decimal
    recovery: Optional[Decimal]
    recoverable_metal_tonnes: Decimal
    total_value: Decimal
    value_lost: Decimal
    value_change_pct: Optional[Decimal]


class ValueTableResponse(BaseModel):
    batch_id: uuid.UUID
    batch_code: str
    reference_price: Decimal
    price_unit: str
    currency: str
    price_source: str
    price_date: date
    rows: List[ValueTableRow]
