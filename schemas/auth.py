from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    challenge_id: str | None = None
    expires_in: int | None = None
    detail: str | None = None
    mfa_token: str | None = None


class LogoutResponse(BaseModel):
    detail: str
