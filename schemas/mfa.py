from pydantic import BaseModel, ConfigDict


class MFASetupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str


class MFASetupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    secret: str
    qr_code_url: str
    token: str


class MFAVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    code: str


class MFAVerifyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mfa_enabled: bool
    message: str


class MFALoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str
    code: str


class MFALoginResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    access_token: str
    token_type: str = "bearer"


class MFADisableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
