from fastapi.testclient import TestClient
from main import app

from models import User, UserRole
from services.user_service import hash_password


def _make_user(session, email, password, role, first, last):
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


def test_value_calculation_endpoints_exist():
    with TestClient(app) as client:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        openapi_schema = response.json()

        paths = openapi_schema.get("paths", {})
        assert "/values/batches/{batch_id}/calculate" in paths
        assert "/values/batches/{batch_id}/values" in paths
        assert "/values/history/{history_id}/values" in paths


def test_calculate_requires_authentication(session):
    _make_user(
        session,
        "scm@example.com",
        "SupplyChain123!",
        UserRole.SUPPLY_CHAIN_MANAGER,
        "Supply",
        "Chain Manager",
    )
    with TestClient(app) as client:
        response = client.post(
            "/values/batches/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/calculate"
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Missing or invalid authorization header"


def test_calculate_requires_supply_chain_manager_role(session, client):
    _make_user(
        session,
        "ops@example.com",
        "OpsPassword123!",
        UserRole.OPERATIONS_MANAGER,
        "Ops",
        "Manager",
    )
    _login(client, "ops@example.com", "OpsPassword123!")
    response = client.post(
        "/values/batches/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/calculate"
    )
    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Only supply chain managers can access value calculations"
    )


def test_calculate_allows_supply_chain_manager(session, client):
    _make_user(
        session,
        "scm@example.com",
        "SupplyChain123!",
        UserRole.SUPPLY_CHAIN_MANAGER,
        "Supply",
        "Chain Manager",
    )
    _login(client, "scm@example.com", "SupplyChain123!")
    response = client.post(
        "/values/batches/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/calculate"
    )

    assert response.status_code == 404
