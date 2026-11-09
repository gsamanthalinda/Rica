import jwt
import pytest

from core.config import settings


def test_settings_use_rs256():
    assert settings.jwt_algorithm == "RS256"
    assert settings.uses_rsa is True


def test_issued_token_is_signed_with_rs256(client, session):
    from models import User, UserRole
    from services.user_service import hash_password

    session.add(
        User(
            email="rs@example.com",
            password_hash=hash_password("password-123"),
            first_name="Rs",
            last_name="User",
            role=UserRole.OPERATIONS_MANAGER,
        )
    )
    session.commit()

    resp = client.post(
        "/auth/login", json={"email": "rs@example.com", "password": "password-123"}
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]

    header = jwt.get_unverified_header(token)
    assert header["alg"] == "RS256"


def test_token_verifies_with_the_public_key(client, session):
    from models import User, UserRole
    from services.user_service import hash_password

    session.add(
        User(
            email="rs2@example.com",
            password_hash=hash_password("password-123"),
            first_name="Rs",
            last_name="User",
            role=UserRole.OPERATIONS_MANAGER,
        )
    )
    session.commit()

    resp = client.post(
        "/auth/login", json={"email": "rs2@example.com", "password": "password-123"}
    )
    token = resp.json()["access_token"]

    payload = jwt.decode(
        token,
        settings.jwt_verification_key,
        algorithms=["RS256"],
    )
    assert payload["email"] == "rs2@example.com"
    assert payload["role"] == "OPERATIONS_MANAGER"


def test_hs256_signed_token_is_rejected(client, session):
    from models import User, UserRole
    from services.user_service import hash_password

    session.add(
        User(
            email="rs3@example.com",
            password_hash=hash_password("password-123"),
            first_name="Rs",
            last_name="User",
            role=UserRole.OPERATIONS_MANAGER,
        )
    )
    session.commit()

    resp = client.post(
        "/auth/login", json={"email": "rs3@example.com", "password": "password-123"}
    )
    token = resp.json()["access_token"]

    payload = jwt.decode(token, options={"verify_signature": False})
    forged = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

    rejected = client.get("/users/me", headers={"Authorization": f"Bearer {forged}"})
    assert rejected.status_code == 401


def test_token_signed_with_another_key_is_rejected(client, session):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    from models import User, UserRole
    from services.user_service import hash_password

    session.add(
        User(
            email="rs4@example.com",
            password_hash=hash_password("password-123"),
            first_name="Rs",
            last_name="User",
            role=UserRole.OPERATIONS_MANAGER,
        )
    )
    session.commit()

    resp = client.post(
        "/auth/login", json={"email": "rs4@example.com", "password": "password-123"}
    )
    token = resp.json()["access_token"]
    payload = jwt.decode(token, options={"verify_signature": False})

    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    forged = jwt.encode(payload, other_pem, algorithm="RS256")

    rejected = client.get("/users/me", headers={"Authorization": f"Bearer {forged}"})
    assert rejected.status_code == 401


def test_production_requires_rsa_keys(monkeypatch):

    from core.config import Settings

    monkeypatch.setenv("TESTING_SKIP_PROD_CHECKS", "0")
    monkeypatch.setenv("TESTING", "0")
    with pytest.raises(ValueError, match="RS\\*"):
        Settings(
            jwt_secret="x" * 40,
            jwt_algorithm="HS256",
            environment="production",
            redis_url="redis://localhost:6379",
            frontend_url="https://app.example.com",
            mfa_encryption_key="BL2NRVMPonjeuRNZeuUUNiDDaJcRmVCMB3mHzst7Zjg=",
        )
