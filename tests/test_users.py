def test_create_user(admin_client):
    resp = admin_client.post(
        "/users/",
        json={
            "email": "new@example.com",
            "password": "password-123",
            "first_name": "New",
            "last_name": "User",
            "role": "OPERATIONS_MANAGER",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["email"] == "new@example.com"
    assert data["first_name"] == "New"
    assert data["last_name"] == "User"
    assert data["role"] == "OPERATIONS_MANAGER"
    assert data["account_status"] == "PENDING"
    assert "password_hash" not in data


def test_create_user_duplicate_email(admin_client, admin_user):
    resp = admin_client.post(
        "/users/",
        json={
            "email": "admin@example.com",
            "password": "password-123",
            "first_name": "Dup",
            "last_name": "User",
            "role": "OPERATIONS_MANAGER",
        },
    )
    assert resp.status_code == 409


def test_list_users(admin_client, admin_user):
    resp = admin_client.get("/users/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(u["email"] == "admin@example.com" for u in data["users"])


def test_get_user_by_id(admin_client, admin_user):
    resp = admin_client.get(f"/users/{admin_user.user_id}")
    assert resp.status_code == 200
    assert resp.json()["email"] == "admin@example.com"


def test_get_user_not_found(admin_client):
    resp = admin_client.get("/users/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_update_user(admin_client, admin_user, non_admin_user):
    resp = admin_client.patch(
        f"/users/{non_admin_user.user_id}",
        json={"first_name": "Updated", "role": "SUPPLY_CHAIN_MANAGER"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["first_name"] == "Updated"
    assert data["role"] == "SUPPLY_CHAIN_MANAGER"


def test_update_user_not_found(admin_client):
    resp = admin_client.patch(
        "/users/00000000-0000-0000-0000-000000000000",
        json={"first_name": "X"},
    )
    assert resp.status_code == 404


def test_disable_user(admin_client, admin_user, non_admin_user):
    resp = admin_client.delete(f"/users/{non_admin_user.user_id}")
    assert resp.status_code == 204

    resp = admin_client.get(f"/users/{non_admin_user.user_id}")
    assert resp.status_code == 200
    assert resp.json()["account_status"] == "DISABLED"


def test_disable_user_not_found(admin_client):
    resp = admin_client.delete("/users/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_no_token_rejected(client):
    """Endpoints reject requests without a valid token."""
    resp = client.get("/users/")
    assert resp.status_code == 401


def test_get_current_user(admin_client, admin_user):
    resp = admin_client.get("/users/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "admin@example.com"
    assert data["user_id"] == str(admin_user.user_id)


def test_disable_user_patch(admin_client, admin_user, non_admin_user):
    resp = admin_client.patch(f"/users/{non_admin_user.user_id}/disable")
    assert resp.status_code == 200
    assert resp.json()["account_status"] == "DISABLED"


def test_disable_user_patch_not_found(admin_client):
    resp = admin_client.patch("/users/00000000-0000-0000-0000-000000000000/disable")
    assert resp.status_code == 404
