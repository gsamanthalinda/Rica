from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class ActivationCodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class ActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr | None = None
    code: str = Field(min_length=6, max_length=6)
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def _passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class ActivationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message: str


class ActivationCodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message: str
    expires_in: int
