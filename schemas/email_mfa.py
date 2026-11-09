from pydantic import BaseModel, ConfigDict, Field


class LoginChallengeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    challenge_id: str
    expires_in: int
    detail: str


class VerifyLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge_id: str
    code: str = Field(min_length=6, max_length=6)


class ResendCodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge_id: str


class ResendCodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    challenge_id: str
    expires_in: int
    message: str
