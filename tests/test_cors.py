ALLOWED_ORIGIN = "http://localhost:3000"
DISALLOWED_ORIGIN = "http://evil.example.com"


def test_preflight_from_allowed_origin_is_accepted(client):
    resp = client.options(
        "/auth/login",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_preflight_allows_authorization_header(client):
    resp = client.options(
        "/auth/login",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert resp.status_code == 200, resp.text
    allowed_headers = resp.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed_headers


def test_preflight_from_disallowed_origin_is_rejected(client):
    resp = client.options(
        "/auth/login",
        headers={
            "Origin": DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 400
    assert "access-control-allow-origin" not in resp.headers


def test_request_from_allowed_origin_carries_cors_header(client):
    resp = client.get("/health", headers={"Origin": ALLOWED_ORIGIN})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_request_without_origin_has_no_cors_header(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers


def test_cors_origin_list_is_parsed_from_the_setting():
    from core.config import parse_cors_origins

    assert parse_cors_origins("http://localhost:3000") == ["http://localhost:3000"]
    assert parse_cors_origins("http://a.test, http://b.test") == [
        "http://a.test",
        "http://b.test",
    ]
    assert parse_cors_origins("") == []
