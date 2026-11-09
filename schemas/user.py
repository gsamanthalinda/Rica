from pydantic import BaseModel, field_validator
from datetime import datetime
from models import UserRole


class UserCreate(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    role: UserRole = UserRole.OPERATIONS_MANAGER
    company_name: str | None = None


class UserUpdate(BaseModel):
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    role: UserRole | None = None
    company_name: str | None = None


class UserResponse(BaseModel):
    user_id: str
    email: str
    first_name: str
    last_name: str
    role: str
    account_status: str
    company_name: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}

    @field_validator("user_id", mode="before")
    @classmethod
    def _coerce_uuid(cls, v):
        return str(v) if v is not None else v


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
