import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


def parse_cors_origins(origins: str) -> list[str]:
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "RS256"
    jwt_private_key_path: str | None = "./keys/private.pem"
    jwt_public_key_path: str | None = "./keys/public.pem"
    access_token_expire_minutes: int = 15
    refresh_token_expire_minutes: int = 60 * 24 * 7
    mfa_token_expire_minutes: int = 5
    redis_url: str | None = None
    cors_origins: str = Field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:3000")
    )
    mfa_required: bool = True
    email_mfa_enabled: bool = False
    mfa_encryption_key: str = Field(min_length=1)
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    smtp_from: str

    DATABASE_URL: str = "postgresql://user:password@localhost:5432/dbname"
    LME_API_KEY: str | None = None
    LME_API_URL: str = "https://metals-api.com/api"
    LME_SYMBOL: str = "XCU"
    LME_UNIT_TO_TONNE: float = 0.0

    login_max_attempts: int = 5
    login_window_seconds: int = 900
    lockout_duration_seconds: int = 900
    trust_proxy_headers: bool = False

    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    password_reset_token_expire_minutes: int = 30
    password_reset_ip_limit: int = 5
    forgot_password_ip_limit: int = 5
    password_reset_window_seconds: int = 900
    reset_password_ip_limit: int = 5
    reset_verify_ip_limit: int = 10
    reset_request_ip_limit: int = 5
    forgot_password_email_limit: int = 5
    reset_password_email_limit: int = 5
    reset_verify_email_limit: int = 10
    reset_request_email_limit: int = 5

    one_time_code_expire_minutes: int = 5
    one_time_code_ip_limit: int = 5
    resend_one_time_code_ip_limit: int = 3

    frontend_url: str = "http://localhost:3000"

    @field_validator("cors_origins")
    @classmethod
    def _validate_cors_origins(cls, v: str) -> str:
        if v:
            parse_cors_origins(v)
        return v

    @field_validator("mfa_encryption_key")
    @classmethod
    def _validate_mfa_encryption_key(cls, v: str) -> str:
        from cryptography.fernet import Fernet

        try:
            Fernet(v)
        except Exception as e:
            raise ValueError("MFA_ENCRYPTION_KEY must be a valid Fernet key") from e
        return v

    @field_validator("jwt_secret")
    @classmethod
    def _validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return v

    @model_validator(mode="after")
    def validate_runtime_requirements(self):
        if os.environ.get("TESTING_SKIP_PROD_CHECKS") == "0":
            if self.environment == "production":
                if not self.uses_rsa:
                    raise ValueError("JWT_ALGORITHM must use RS* in production")
                if not self.redis_url:
                    raise ValueError("REDIS_URL is required in production")
                if self.frontend_url == "http://localhost:3000":
                    raise ValueError(
                        "FRONTEND_URL must be set to a non-localhost value in production"
                    )
            return self

        testing = os.getenv("TESTING") == "1"
        if testing:
            self.DATABASE_URL = "sqlite:///:memory:"
            return self

        if self.environment == "production":
            if not self.uses_rsa:
                raise ValueError("JWT_ALGORITHM must use RS* in production")
            if not self.redis_url:
                raise ValueError("REDIS_URL is required in production")
            if self.frontend_url == "http://localhost:3000":
                raise ValueError(
                    "FRONTEND_URL must be set to a non-localhost value in production"
                )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return parse_cors_origins(self.cors_origins)

    @property
    def uses_rsa(self) -> bool:
        return self.jwt_algorithm.upper().startswith("RS")

    @property
    def jwt_signing_key(self):
        if self.uses_rsa:
            path = (
                Path(self.jwt_private_key_path) if self.jwt_private_key_path else None
            )
            if path and not path.exists():
                # Auto-generate keys for testing/local environments
                try:
                    from cryptography.hazmat.primitives import serialization
                    from cryptography.hazmat.primitives.asymmetric import rsa

                    path.parent.mkdir(parents=True, exist_ok=True)
                    pub_path = (
                        Path(self.jwt_public_key_path)
                        if self.jwt_public_key_path
                        else path.parent / "public.pem"
                    )
                    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
                    private_pem = key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption(),
                    )
                    public_pem = key.public_key().public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo,
                    )
                    path.write_bytes(private_pem)
                    pub_path.write_bytes(public_pem)
                except Exception:
                    pass
            return path.read_text() if path else self.jwt_secret
        return self.jwt_secret

    @property
    def jwt_verification_key(self):
        if self.uses_rsa:
            path = Path(self.jwt_public_key_path) if self.jwt_public_key_path else None
            if path and not path.exists():
                # Try to generate from private key or generate both
                priv_path = (
                    Path(self.jwt_private_key_path)
                    if self.jwt_private_key_path
                    else None
                )
                try:
                    if priv_path and priv_path.exists():
                        from cryptography.hazmat.primitives import serialization

                        private_key = serialization.load_pem_private_key(
                            priv_path.read_bytes(), password=None
                        )
                        public_pem = private_key.public_key().public_bytes(
                            encoding=serialization.Encoding.PEM,
                            format=serialization.PublicFormat.SubjectPublicKeyInfo,
                        )
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(public_pem)
                    else:
                        from cryptography.hazmat.primitives import serialization
                        from cryptography.hazmat.primitives.asymmetric import rsa

                        path.parent.mkdir(parents=True, exist_ok=True)
                        if priv_path:
                            priv_path.parent.mkdir(parents=True, exist_ok=True)
                        key = rsa.generate_private_key(
                            public_exponent=65537, key_size=2048
                        )
                        private_pem = key.private_bytes(
                            encoding=serialization.Encoding.PEM,
                            format=serialization.PrivateFormat.PKCS8,
                            encryption_algorithm=serialization.NoEncryption(),
                        )
                        public_pem = key.public_key().public_bytes(
                            encoding=serialization.Encoding.PEM,
                            format=serialization.PublicFormat.SubjectPublicKeyInfo,
                        )
                        if priv_path:
                            priv_path.write_bytes(private_pem)
                        path.write_bytes(public_pem)
                except Exception:
                    pass
            return path.read_text() if path else self.jwt_secret
        return self.jwt_secret


settings = Settings()
DATABASE_URL = settings.DATABASE_URL
