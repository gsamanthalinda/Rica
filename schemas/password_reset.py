from pydantic import BaseModel, ConfigDict, field_validator


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str


class ForgotPasswordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message: str


class ResetVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    code: str

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not v or not v.isdigit() or len(v) != 6:
            raise ValueError("Code must be 6 digits")
        return v


class ResetVerifyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    token: str


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v or len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class ResetPasswordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message: str
