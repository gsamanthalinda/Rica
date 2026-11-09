import pyotp

from services.user_service import hash_password


def _make_user(session, email, password, role, first, last):
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


def _login(client, email, password):
    from core.auth import _blacklist

    _blacklist.clear()
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return client


def test_mfa_setup(client, session, admin_user, admin_client):
    resp = admin_client.post("/auth/mfa/setup")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "secret" in data
    assert "qr_code_url" in data
    assert "token" in data


def test_mfa_setup_already_enabled(client, session, admin_user, admin_client):
    setup = admin_client.post("/auth/mfa/setup")
    assert setup.status_code == 200
    token = setup.json()["token"]
    secret = setup.json()["secret"]
    admin_client.post(
        "/auth/mfa/verify",
        json={"token": token, "code": pyotp.TOTP(secret).now()},
    )

    resp = admin_client.post("/auth/mfa/setup")
    assert resp.status_code == 400, resp.text


def test_mfa_verify_success(client, session, admin_user, admin_client):
    setup = admin_client.post("/auth/mfa/setup")
    assert setup.status_code == 200
    data = setup.json()
    resp = admin_client.post(
        "/auth/mfa/verify",
        json={"token": data["token"], "code": pyotp.TOTP(data["secret"]).now()},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["mfa_enabled"] is True


def test_mfa_verify_invalid_code(client, session, admin_user, admin_client):
    setup = admin_client.post("/auth/mfa/setup")
    data = setup.json()
    resp = admin_client.post(
        "/auth/mfa/verify",
        json={"token": data["token"], "code": "000000"},
    )
    assert resp.status_code == 400, resp.text


def test_mfa_verify_invalid_token(client, session, admin_client):
    resp = admin_client.post(
        "/auth/mfa/verify",
        json={"token": "does-not-exist", "code": "000000"},
    )
    assert resp.status_code == 400, resp.text


def test_mfa_disable_success(client, session, admin_user, admin_client):
    setup = admin_client.post("/auth/mfa/setup")
    assert setup.status_code == 200
    data = setup.json()
    admin_client.post(
        "/auth/mfa/verify",
        json={"token": data["token"], "code": pyotp.TOTP(data["secret"]).now()},
    )

    resp = admin_client.post(
        "/auth/mfa/disable",
        json={"code": pyotp.TOTP(data["secret"]).now()},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["mfa_enabled"] is False


def test_mfa_disable_not_enabled(client, session, admin_client):
    resp = admin_client.post(
        "/auth/mfa/disable",
        json={"code": "000000"},
    )
    assert resp.status_code == 400, resp.text


def test_mfa_disable_invalid_code(client, session, admin_user, admin_client):
    setup = admin_client.post("/auth/mfa/setup")
    assert setup.status_code == 200
    data = setup.json()
    admin_client.post(
        "/auth/mfa/verify",
        json={"token": data["token"], "code": pyotp.TOTP(data["secret"]).now()},
    )

    resp = admin_client.post(
        "/auth/mfa/disable",
        json={"code": "000000"},
    )
    assert resp.status_code == 400, resp.text


def test_mfa_login_success(client, session, admin_user, admin_client):
    setup = admin_client.post("/auth/mfa/setup")
    assert setup.status_code == 200
    data = setup.json()
    admin_client.post(
        "/auth/mfa/verify",
        json={"token": data["token"], "code": pyotp.TOTP(data["secret"]).now()},
    )

    resp = client.post(
        "/auth/mfa/login",
        json={
            "email": "admin@example.com",
            "password": "admin-password-123",
            "code": pyotp.TOTP(data["secret"]).now(),
        },
    )
    assert resp.status_code == 200, resp.text
    assert "access_token" in resp.json()


def test_mfa_login_not_enabled(client, session, admin_user):
    resp = client.post(
        "/auth/mfa/login",
        json={
            "email": "admin@example.com",
            "password": "admin-password-123",
            "code": "000000",
        },
    )
    assert resp.status_code == 400, resp.text


def test_mfa_login_invalid_code(client, session, admin_user, admin_client):
    setup = admin_client.post("/auth/mfa/setup")
    assert setup.status_code == 200
    data = setup.json()
    admin_client.post(
        "/auth/mfa/verify",
        json={"token": data["token"], "code": pyotp.TOTP(data["secret"]).now()},
    )

    resp = client.post(
        "/auth/mfa/login",
        json={
            "email": "admin@example.com",
            "password": "admin-password-123",
            "code": "000000",
        },
    )
    assert resp.status_code == 400, resp.text
