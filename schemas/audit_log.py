from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AuditLogCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: Optional[str] = None
    action: str
    resource: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audit_id: str
    user_id: Optional[str] = None
    action: str
    resource: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime


class AuditLogListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    logs: list[AuditLogResponse]
    total: int
