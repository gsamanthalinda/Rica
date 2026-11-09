import re

from services import email_service
from services.user_service import hash_password


def _make_user(
    session, email, password, role="OPERATIONS_MANAGER", first="Test", last="User"
):
    from models import User

    obj = User(
        email=email,
        password_hash=hash_password(password),
        first_name=first,
        last_name=last,
        role=role,
        mfa_enabled=False,
    )
    session.add(obj)
    session.commit()
    return obj


def _sent_code(email="alice@example.com"):
    emails = email_service.get_sent_emails()
    assert emails, "no reset email was sent"
    body = emails[-1]["body"]
    match = re.search(r"code is: (\d{6})", body)
    assert match, f"no reset code in email body: {body!r}"
    return match.group(1)


def _request_code(client, email):
    email_service.clear_sent_emails()
    resp = client.post("/auth/forgot-password", json={"email": email})
    assert resp.status_code == 200, resp.text
    return resp


def test_forgot_password_existing_user(client, session):
    _make_user(session, "alice@example.com", "password-123")
    resp = _request_code(client, "alice@example.com")
    data = resp.json()
    assert "message" in data
    assert "token" not in data
    assert len(_sent_code()) == 6


def test_forgot_password_unknown_email(client):
    email_service.clear_sent_emails()
    resp = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "message" in data
    assert "token" not in data
    assert email_service.get_sent_emails() == []


def test_verify_reset_code_returns_token(client, session):
    _make_user(session, "bob@example.com", "password-123")
    _request_code(client, "bob@example.com")
    code = _sent_code()

    resp = client.post(
        "/auth/reset/verify", json={"email": "bob@example.com", "code": code}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["token"]


def test_verify_reset_code_is_single_use(client, session):
    _make_user(session, "bob@example.com", "password-123")
    _request_code(client, "bob@example.com")
    code = _sent_code()

    first = client.post(
        "/auth/reset/verify", json={"email": "bob@example.com", "code": code}
    )
    assert first.status_code == 200, first.text

    second = client.post(
        "/auth/reset/verify", json={"email": "bob@example.com", "code": code}
    )
    assert second.status_code == 400, second.text


def test_verify_reset_code_invalid_code(client, session):
    _make_user(session, "bob@example.com", "password-123")
    _request_code(client, "bob@example.com")

    resp = client.post(
        "/auth/reset/verify", json={"email": "bob@example.com", "code": "000000"}
    )
    assert resp.status_code == 400, resp.text


def test_verify_reset_code_unknown_email(client):
    resp = client.post(
        "/auth/reset/verify", json={"email": "nobody@example.com", "code": "123456"}
    )
    assert resp.status_code == 400, resp.text


def test_verify_reset_code_rejects_non_numeric_code(client, session):
    _make_user(session, "bob@example.com", "password-123")
    resp = client.post(
        "/auth/reset/verify", json={"email": "bob@example.com", "code": "abcdef"}
    )
    assert resp.status_code == 422, resp.text


def test_verify_reset_code_locks_after_too_many_attempts(client, session):
    _make_user(session, "bob@example.com", "password-123")
    _request_code(client, "bob@example.com")
    code = _sent_code()

    for _ in range(5):
        resp = client.post(
            "/auth/reset/verify", json={"email": "bob@example.com", "code": "000000"}
        )
        assert resp.status_code == 400, resp.text

    locked = client.post(
        "/auth/reset/verify", json={"email": "bob@example.com", "code": code}
    )
    assert locked.status_code == 400, locked.text
    assert "attempts" in locked.json()["detail"].lower()


def test_resend_replaces_previous_code(client, session):
    _make_user(session, "bob@example.com", "password-123")
    _request_code(client, "bob@example.com")
    first_code = _sent_code()

    _request_code(client, "bob@example.com")
    second_code = _sent_code()

    stale = client.post(
        "/auth/reset/verify", json={"email": "bob@example.com", "code": first_code}
    )
    assert stale.status_code == 400, stale.text

    fresh = client.post(
        "/auth/reset/verify", json={"email": "bob@example.com", "code": second_code}
    )
    assert fresh.status_code == 200, fresh.text


def test_reset_password_success(client, session):
    _make_user(session, "bob@example.com", "password-123")
    _request_code(client, "bob@example.com")
    code = _sent_code()

    verified = client.post(
        "/auth/reset/verify", json={"email": "bob@example.com", "code": code}
    )
    token = verified.json()["token"]

    resp = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "new-password-123"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["message"] == "Password has been reset successfully"


def test_reset_password_invalid_token(client):
    resp = client.post(
        "/auth/reset-password",
        json={"token": "invalid-token", "new_password": "new-password-123"},
    )
    assert resp.status_code == 400, resp.text


def test_reset_password_short_password(client, session):
    _make_user(session, "carol@example.com", "password-123")
    _request_code(client, "carol@example.com")
    code = _sent_code()

    verified = client.post(
        "/auth/reset/verify", json={"email": "carol@example.com", "code": code}
    )
    token = verified.json()["token"]

    resp = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "short"},
    )
    assert resp.status_code == 422, resp.text
