def _create_user(
    session, email, password, role="OPERATIONS_MANAGER", first="Test", last="User"
):
    from models import User
    from services.user_service import hash_password

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


def test_login_success(client, session):
    _create_user(session, "alice@example.com", "password-123")
    resp = client.post(
        "/auth/login",
        json={
            "email": "alice@example.com",
            "password": "password-123",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, session):
    _create_user(session, "alice@example.com", "password-123")
    resp = client.post(
        "/auth/login",
        json={
            "email": "alice@example.com",
            "password": "wrong",
        },
    )
    assert resp.status_code == 401


def test_login_unknown_email(client):
    resp = client.post(
        "/auth/login",
        json={
            "email": "nobody@example.com",
            "password": "password-123",
        },
    )
    assert resp.status_code == 401


def test_login_disabled_user(client, session):
    _create_user(session, "bob@example.com", "password-123")

    from models import User

    user = session.query(User).filter(User.email == "bob@example.com").first()
    user.account_status = "DISABLED"
    session.commit()

    resp = client.post(
        "/auth/login",
        json={
            "email": "bob@example.com",
            "password": "password-123",
        },
    )
    assert resp.status_code == 401


def test_logout_without_token(client):
    resp = client.post("/auth/logout")
    assert resp.status_code == 401


def test_logout_with_token(client, session):
    _create_user(session, "carol@example.com", "password-123")
    login = client.post(
        "/auth/login",
        json={
            "email": "carol@example.com",
            "password": "password-123",
        },
    )
    token = login.json()["access_token"]

    resp = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Successfully logged out"


def test_logout_blacklisted_token_rejected(client, session):
    _create_user(session, "dave@example.com", "password-123")
    login = client.post(
        "/auth/login",
        json={
            "email": "dave@example.com",
            "password": "password-123",
        },
    )
    token = login.json()["access_token"]

    client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    resp = client.get("/users/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
