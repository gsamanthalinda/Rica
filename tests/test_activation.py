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


def test_admin_creates_passwordless_user_and_code_is_emailed(admin_client):
    _clear()

    resp = admin_client.post(
        "/users/",
        json={
            "email": "newcomer@example.com",
            "password": "password-123",
            "first_name": "New",
            "last_name": "Comer",
            "role": "OPERATIONS_MANAGER",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["account_status"] == "PENDING"

    bodies = _sent_bodies("Activate your RICA account")
    assert len(bodies) == 1
    assert len(bodies[0].split("activation code is: ")[1].split("\n")[0]) == 6

    _clear()


def test_request_activation_code_sends_code(client, session):
    from models import AccountStatus, User, UserRole

    _clear()
    session.add(
        User(
            email="pending@example.com",
            password_hash=None,
            first_name="Pend",
            last_name="Ing",
            role=UserRole.OPERATIONS_MANAGER,
            account_status=AccountStatus.PENDING,
            email_mfa_enabled=True,
        )
    )
    session.commit()

    resp = client.post(
        "/auth/activate/send-code", json={"email": "pending@example.com"}
    )
    assert resp.status_code == 200, resp.text
    assert "code has been sent" in resp.json()["message"].lower()
    assert len(_sent_bodies("Activate your RICA account")) == 1

    _clear()


def test_request_activation_code_unknown_email_sends_nothing(client):
    _clear()

    resp = client.post("/auth/activate/send-code", json={"email": "nobody@example.com"})
    assert resp.status_code == 200, resp.text
    assert _sent_bodies() == []

    _clear()


def test_resend_activation_code_replaces_previous_code(client, session):
    from models import AccountStatus, User, UserRole

    _clear()
    session.add(
        User(
            email="pending@example.com",
            password_hash=None,
            first_name="Pend",
            last_name="Ing",
            role=UserRole.OPERATIONS_MANAGER,
            account_status=AccountStatus.PENDING,
            email_mfa_enabled=True,
        )
    )
    session.commit()

    client.post("/auth/activate/send-code", json={"email": "pending@example.com"})
    first_code = _latest_code("Activate your RICA account")

    resp = client.post("/auth/activate/resend", json={"email": "pending@example.com"})
    assert resp.status_code == 200, resp.text
    second_code = _latest_code("Activate your RICA account")

    assert len(_sent_bodies("Activate your RICA account")) == 2

    activate = client.post(
        "/auth/activate",
        json={
            "email": "pending@example.com",
            "code": first_code,
            "password": "password-123",
            "confirm_password": "password-123",
        },
    )
    assert activate.status_code == 400, activate.text

    activate = client.post(
        "/auth/activate",
        json={
            "email": "pending@example.com",
            "code": second_code,
            "password": "password-123",
            "confirm_password": "password-123",
        },
    )
    assert activate.status_code == 200, activate.text

    _clear()


def test_activate_with_valid_code_activates_account(client, session):
    from models import AccountStatus, User, UserRole

    _clear()
    session.add(
        User(
            email="pending@example.com",
            password_hash=None,
            first_name="Pend",
            last_name="Ing",
            role=UserRole.OPERATIONS_MANAGER,
            account_status=AccountStatus.PENDING,
            email_mfa_enabled=True,
        )
    )
    session.commit()

    client.post("/auth/activate/send-code", json={"email": "pending@example.com"})
    code = _latest_code("Activate your RICA account")

    resp = client.post(
        "/auth/activate",
        json={
            "email": "pending@example.com",
            "code": code,
            "password": "password-123",
            "confirm_password": "password-123",
        },
    )
    assert resp.status_code == 200, resp.text
    assert "activated" in resp.json()["message"].lower()

    user = session.query(User).filter(User.email == "pending@example.com").first()
    assert user.account_status == AccountStatus.ACTIVE
    assert user.activated_at is not None
    assert user.password_hash is not None

    login = client.post(
        "/auth/login",
        json={"email": "pending@example.com", "password": "password-123"},
    )
    assert login.status_code == 202, login.text
    assert "challenge_id" in login.json()

    _clear()


def test_activate_with_invalid_code_fails(client, session):
    from models import AccountStatus, User, UserRole

    _clear()
    session.add(
        User(
            email="pending@example.com",
            password_hash=None,
            first_name="Pend",
            last_name="Ing",
            role=UserRole.OPERATIONS_MANAGER,
            account_status=AccountStatus.PENDING,
            email_mfa_enabled=True,
        )
    )
    session.commit()

    client.post("/auth/activate/send-code", json={"email": "pending@example.com"})

    resp = client.post(
        "/auth/activate",
        json={
            "email": "pending@example.com",
            "code": "000000",
            "password": "password-123",
            "confirm_password": "password-123",
        },
    )
    assert resp.status_code == 400, resp.text
    assert "invalid activation code" in resp.json()["detail"].lower()

    _clear()


def test_activate_code_cannot_be_reused(client, session):
    from models import AccountStatus, User, UserRole

    _clear()
    session.add(
        User(
            email="pending@example.com",
            password_hash=None,
            first_name="Pend",
            last_name="Ing",
            role=UserRole.OPERATIONS_MANAGER,
            account_status=AccountStatus.PENDING,
            email_mfa_enabled=True,
        )
    )
    session.commit()

    client.post("/auth/activate/send-code", json={"email": "pending@example.com"})
    code = _latest_code("Activate your RICA account")

    payload = {
        "email": "pending@example.com",
        "code": code,
        "password": "password-123",
        "confirm_password": "password-123",
    }
    assert client.post("/auth/activate", json=payload).status_code == 200
    assert client.post("/auth/activate", json=payload).status_code == 400

    _clear()


def test_activate_blocks_after_too_many_attempts(client, session):
    from models import AccountStatus, User, UserRole

    _clear()
    session.add(
        User(
            email="pending@example.com",
            password_hash=None,
            first_name="Pend",
            last_name="Ing",
            role=UserRole.OPERATIONS_MANAGER,
            account_status=AccountStatus.PENDING,
            email_mfa_enabled=True,
        )
    )
    session.commit()

    client.post("/auth/activate/send-code", json={"email": "pending@example.com"})

    for _ in range(5):
        resp = client.post(
            "/auth/activate",
            json={
                "email": "pending@example.com",
                "code": "000000",
                "password": "password-123",
                "confirm_password": "password-123",
            },
        )
        assert resp.status_code == 400, resp.text

    resp = client.post(
        "/auth/activate",
        json={
            "email": "pending@example.com",
            "code": "000000",
            "password": "password-123",
            "confirm_password": "password-123",
        },
    )
    assert resp.status_code == 400
    assert "too many attempts" in resp.json()["detail"].lower()

    _clear()


def test_activate_expired_code_fails(client, session):
    from datetime import datetime, timedelta, timezone

    from models import AccountStatus, OneTimeCodePurpose, User, UserRole

    _clear()
    session.add(
        User(
            email="pending@example.com",
            password_hash=None,
            first_name="Pend",
            last_name="Ing",
            role=UserRole.OPERATIONS_MANAGER,
            account_status=AccountStatus.PENDING,
            email_mfa_enabled=True,
        )
    )
    session.commit()

    client.post("/auth/activate/send-code", json={"email": "pending@example.com"})

    from repositories import one_time_code_repository

    record = one_time_code_repository.get_latest_active(
        session,
        session.query(User).filter(User.email == "pending@example.com").first().user_id,
        OneTimeCodePurpose.ACTIVATION,
    )
    record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    session.commit()

    resp = client.post(
        "/auth/activate",
        json={
            "email": "pending@example.com",
            "code": "123456",
            "password": "password-123",
            "confirm_password": "password-123",
        },
    )
    assert resp.status_code == 400, resp.text
    assert "expired" in resp.json()["detail"].lower()

    _clear()


def test_activate_unknown_email_fails(client):
    _clear()

    resp = client.post(
        "/auth/activate",
        json={
            "email": "nobody@example.com",
            "code": "123456",
            "password": "password-123",
            "confirm_password": "password-123",
        },
    )
    assert resp.status_code == 400, resp.text

    _clear()


def test_activate_rejects_password_mismatch(client, session):
    _clear()

    resp = client.post(
        "/auth/activate",
        json={
            "email": "pending@example.com",
            "code": "123456",
            "password": "password-123",
            "confirm_password": "password-124",
        },
    )
    assert resp.status_code == 422, resp.text

    _clear()


def test_activate_rejects_short_password(client):
    _clear()

    resp = client.post(
        "/auth/activate",
        json={
            "email": "pending@example.com",
            "code": "123456",
            "password": "short",
            "confirm_password": "short",
        },
    )
    assert resp.status_code == 422, resp.text

    _clear()


def test_activate_without_email_uses_code_to_identify_account(client, session):
    from models import AccountStatus, User, UserRole

    _clear()
    session.add(
        User(
            email="pending@example.com",
            password_hash=None,
            first_name="Pend",
            last_name="Ing",
            role=UserRole.OPERATIONS_MANAGER,
            account_status=AccountStatus.PENDING,
            email_mfa_enabled=True,
        )
    )
    session.commit()

    client.post("/auth/activate/send-code", json={"email": "pending@example.com"})
    code = _latest_code("Activate your RICA account")

    resp = client.post(
        "/auth/activate",
        json={
            "code": code,
            "password": "password-123",
            "confirm_password": "password-123",
        },
    )
    assert resp.status_code == 200, resp.text
    assert "activated" in resp.json()["message"].lower()

    user = session.query(User).filter(User.email == "pending@example.com").first()
    assert user.account_status == AccountStatus.ACTIVE
    assert user.password_hash is not None

    _clear()


def test_activate_without_email_rejects_wrong_code(client, session):
    from models import AccountStatus, User, UserRole

    _clear()
    session.add(
        User(
            email="pending@example.com",
            password_hash=None,
            first_name="Pend",
            last_name="Ing",
            role=UserRole.OPERATIONS_MANAGER,
            account_status=AccountStatus.PENDING,
            email_mfa_enabled=True,
        )
    )
    session.commit()

    client.post("/auth/activate/send-code", json={"email": "pending@example.com"})

    resp = client.post(
        "/auth/activate",
        json={
            "code": "000000",
            "password": "password-123",
            "confirm_password": "password-123",
        },
    )
    assert resp.status_code == 400, resp.text
    assert "invalid or expired activation code" in resp.json()["detail"].lower()

    _clear()


def test_activate_without_email_cannot_reuse_code(client, session):
    from models import AccountStatus, User, UserRole

    _clear()
    session.add(
        User(
            email="pending@example.com",
            password_hash=None,
            first_name="Pend",
            last_name="Ing",
            role=UserRole.OPERATIONS_MANAGER,
            account_status=AccountStatus.PENDING,
            email_mfa_enabled=True,
        )
    )
    session.commit()

    client.post("/auth/activate/send-code", json={"email": "pending@example.com"})
    code = _latest_code("Activate your RICA account")

    payload = {
        "code": code,
        "password": "password-123",
        "confirm_password": "password-123",
    }
    assert client.post("/auth/activate", json=payload).status_code == 200
    assert client.post("/auth/activate", json=payload).status_code == 400

    _clear()


def test_activate_without_email_rejects_expired_code(client, session):
    from datetime import datetime, timedelta, timezone

    from models import AccountStatus, OneTimeCodePurpose, User, UserRole

    _clear()
    session.add(
        User(
            email="pending@example.com",
            password_hash=None,
            first_name="Pend",
            last_name="Ing",
            role=UserRole.OPERATIONS_MANAGER,
            account_status=AccountStatus.PENDING,
            email_mfa_enabled=True,
        )
    )
    session.commit()

    client.post("/auth/activate/send-code", json={"email": "pending@example.com"})

    from repositories import one_time_code_repository

    record = one_time_code_repository.get_latest_active(
        session,
        session.query(User).filter(User.email == "pending@example.com").first().user_id,
        OneTimeCodePurpose.ACTIVATION,
    )
    record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    session.commit()

    resp = client.post(
        "/auth/activate",
        json={
            "code": "123456",
            "password": "password-123",
            "confirm_password": "password-123",
        },
    )
    assert resp.status_code == 400, resp.text

    _clear()


def test_activate_email_still_verified_when_supplied(client, session):
    from models import AccountStatus, User, UserRole

    _clear()
    session.add(
        User(
            email="pending@example.com",
            password_hash=None,
            first_name="Pend",
            last_name="Ing",
            role=UserRole.OPERATIONS_MANAGER,
            account_status=AccountStatus.PENDING,
            email_mfa_enabled=True,
        )
    )
    session.commit()

    client.post("/auth/activate/send-code", json={"email": "pending@example.com"})
    code = _latest_code("Activate your RICA account")

    resp = client.post(
        "/auth/activate",
        json={
            "email": "someone-else@example.com",
            "code": code,
            "password": "password-123",
            "confirm_password": "password-123",
        },
    )
    assert resp.status_code == 400, resp.text

    _clear()
