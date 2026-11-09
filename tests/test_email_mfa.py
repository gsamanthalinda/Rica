import re

from services import email_service


def _clear():
    email_service.clear_sent_emails()


def _sent_bodies(subject_contains=""):
    return [
        email["body"]
        for email in email_service.get_sent_emails()
        if subject_contains in email["subject"]
    ]


def _extract_code(body: str) -> str:
    match = re.search(r"\b(\d{6})\b", body)
    assert match is not None, f"no code found in body: {body!r}"
    return match.group(1)


def _latest_code(subject_contains: str) -> str:
    bodies = _sent_bodies(subject_contains)
    assert bodies, "no matching email was sent"
    return _extract_code(bodies[-1])


def _create_email_mfa_user(session, email="mfa@example.com", password="password-123"):
    from models import User, UserRole
    from services.user_service import hash_password

    user = User(
        email=email,
        password_hash=hash_password(password),
        first_name="Mfa",
        last_name="User",
        role=UserRole.OPERATIONS_MANAGER,
        email_mfa_enabled=True,
    )
    session.add(user)
    session.commit()
    return user


def test_login_returns_challenge_for_email_mfa_user(client, session):
    _clear()
    _create_email_mfa_user(session)

    resp = client.post(
        "/auth/login", json={"email": "mfa@example.com", "password": "password-123"}
    )
    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data["challenge_id"]
    assert data["expires_in"] > 0
    assert "verification code" in data["detail"].lower()
    assert len(_sent_bodies("sign-in verification code")) == 1

    _clear()


def test_login_without_email_mfa_returns_token(client, session):
    from models import User, UserRole
    from services.user_service import hash_password

    _clear()
    session.add(
        User(
            email="legacy@example.com",
            password_hash=hash_password("password-123"),
            first_name="Legacy",
            last_name="User",
            role=UserRole.OPERATIONS_MANAGER,
        )
    )
    session.commit()

    resp = client.post(
        "/auth/login", json={"email": "legacy@example.com", "password": "password-123"}
    )
    assert resp.status_code == 200, resp.text
    assert "access_token" in resp.json()

    _clear()


def test_login_wrong_password_returns_401(client, session):
    _clear()
    _create_email_mfa_user(session)

    resp = client.post(
        "/auth/login", json={"email": "mfa@example.com", "password": "wrong-password"}
    )
    assert resp.status_code == 401, resp.text
    assert _sent_bodies() == []

    _clear()


def test_verify_login_code_returns_access_token(client, session):
    _clear()
    _create_email_mfa_user(session)

    login = client.post(
        "/auth/login", json={"email": "mfa@example.com", "password": "password-123"}
    )
    challenge_id = login.json()["challenge_id"]
    code = _latest_code("sign-in verification code")

    resp = client.post(
        "/auth/mfa/verify-login", json={"challenge_id": challenge_id, "code": code}
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]

    me = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    assert me.json()["email"] == "mfa@example.com"

    _clear()


def test_verify_login_code_is_single_use(client, session):
    _clear()
    _create_email_mfa_user(session)

    login = client.post(
        "/auth/login", json={"email": "mfa@example.com", "password": "password-123"}
    )
    challenge_id = login.json()["challenge_id"]
    code = _latest_code("sign-in verification code")

    first = client.post(
        "/auth/mfa/verify-login", json={"challenge_id": challenge_id, "code": code}
    )
    assert first.status_code == 200, first.text

    second = client.post(
        "/auth/mfa/verify-login", json={"challenge_id": challenge_id, "code": code}
    )
    assert second.status_code == 400, second.text
    assert "already been used" in second.json()["detail"].lower()

    _clear()


def test_verify_login_with_invalid_code_fails(client, session):
    _clear()
    _create_email_mfa_user(session)

    login = client.post(
        "/auth/login", json={"email": "mfa@example.com", "password": "password-123"}
    )
    challenge_id = login.json()["challenge_id"]

    resp = client.post(
        "/auth/mfa/verify-login", json={"challenge_id": challenge_id, "code": "000000"}
    )
    assert resp.status_code == 400, resp.text
    assert "invalid verification code" in resp.json()["detail"].lower()

    _clear()


def test_verify_login_blocks_after_too_many_attempts(client, session):
    _clear()
    _create_email_mfa_user(session)

    login = client.post(
        "/auth/login", json={"email": "mfa@example.com", "password": "password-123"}
    )
    challenge_id = login.json()["challenge_id"]

    for _ in range(5):
        resp = client.post(
            "/auth/mfa/verify-login",
            json={"challenge_id": challenge_id, "code": "000000"},
        )
        assert resp.status_code == 400, resp.text

    resp = client.post(
        "/auth/mfa/verify-login", json={"challenge_id": challenge_id, "code": "000000"}
    )
    assert resp.status_code == 400
    assert "too many attempts" in resp.json()["detail"].lower()

    _clear()


def test_verify_login_with_unknown_challenge_fails(client):
    _clear()

    resp = client.post(
        "/auth/mfa/verify-login",
        json={
            "challenge_id": "00000000-0000-0000-0000-000000000000",
            "code": "123456",
        },
    )
    assert resp.status_code == 400, resp.text

    _clear()


def test_resend_replaces_previous_code(client, session):
    _clear()
    _create_email_mfa_user(session)

    login = client.post(
        "/auth/login", json={"email": "mfa@example.com", "password": "password-123"}
    )
    challenge_id = login.json()["challenge_id"]
    first_code = _latest_code("sign-in verification code")

    resend = client.post("/auth/mfa/resend", json={"challenge_id": challenge_id})
    assert resend.status_code == 200, resend.text
    assert resend.json()["challenge_id"] == challenge_id
    second_code = _latest_code("sign-in verification code")
    assert len(_sent_bodies("sign-in verification code")) == 2

    stale = client.post(
        "/auth/mfa/verify-login",
        json={"challenge_id": challenge_id, "code": first_code},
    )
    assert stale.status_code == 400, stale.text

    fresh = client.post(
        "/auth/mfa/verify-login",
        json={"challenge_id": challenge_id, "code": second_code},
    )
    assert fresh.status_code == 200, fresh.text
    assert "access_token" in fresh.json()

    _clear()


def test_login_challenge_code_is_not_stored_in_plain_text(client, session):
    from models import OneTimeCode, OneTimeCodePurpose

    _clear()
    _create_email_mfa_user(session)

    client.post(
        "/auth/login", json={"email": "mfa@example.com", "password": "password-123"}
    )
    code = _latest_code("sign-in verification code")

    record = (
        session.query(OneTimeCode)
        .filter(OneTimeCode.purpose == OneTimeCodePurpose.LOGIN_MFA)
        .first()
    )
    assert record is not None
    assert record.code_hash != code
    assert len(record.code_hash) == 64
    assert record.used_at is None

    _clear()
