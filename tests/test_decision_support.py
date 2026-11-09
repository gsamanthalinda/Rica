from uuid import uuid4

import pytest

from models import User, UserRole
from models.decision_support import ScenarioDecision

# Role allowed to use the decision-support endpoints.
DECISION_ROLE = UserRole.SUPPLY_CHAIN_MANAGER
DECISION_EMAIL = "decider@example.com"
DECISION_PASSWORD = "decider-password-123"

# The service only lets a user see data from their own company, so the logged-in
# user and the user who owns the test data must share a company.
COMPANY = "Test Company"


@pytest.fixture()
def user(session, user_kwargs):
    """Same as the shared `user` fixture, but with a company."""
    obj = User(**{**user_kwargs, "company_name": COMPANY})
    session.add(obj)
    session.commit()
    return obj


@pytest.fixture()
def decider(session):
    """The user who is logged in for every test in this file."""
    from services.user_service import hash_password

    obj = User(
        email=DECISION_EMAIL,
        password_hash=hash_password(DECISION_PASSWORD),
        first_name="Dee",
        last_name="Cider",
        role=DECISION_ROLE,
        mfa_enabled=False,
        company_name=COMPANY,
    )
    session.add(obj)
    session.commit()
    return obj


@pytest.fixture(autouse=True)
def _authenticated(client, decider):
    """Log in as the decider; decision-support endpoints require a token."""
    from core.auth import _blacklist

    _blacklist.clear()
    resp = client.post(
        "/auth/login", json={"email": DECISION_EMAIL, "password": DECISION_PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    client.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
    return client


def _body(context=None):
    # The assessor is taken from the login token, not from the request body.
    return {"context": context or {}}


def _assess(client, scenario_result, body=None):
    return client.post(
        "/decision_support/assess",
        params={"scenario_result_id": str(scenario_result.results_id)},
        json=body if body is not None else _body(),
    )


def test_assess_scenario(client, decider, scenario, scenario_result):
    response = _assess(
        client,
        scenario_result,
        _body(
            {
                "technical_recovery_min": 0.72,
                "technical_recovery_max": 0.88,
                "required_capacity_tonnes": 50000,
                "available_capacity_tonnes": 60000,
                "regulatory_status": "CONFIRMED",
                "infrastructure_status": "AVAILABLE",
                "operation_specific_technical_evidence": True,
                "cost_data_complete": True,
                "downside_price": 8000,
            }
        ),
    )

    assert response.status_code == 201, response.text

    data = response.json()
    assert data["scenario_result_id"] == str(scenario_result.results_id)
    assert data["assessed_by"] == str(decider.user_id)
    assert data["lifecycle_state"] == "ASSESSED"
    assert data["assessment_outcome"] in {
        "VIABLE",
        "CONDITIONALLY_VIABLE",
        "NOT_VIABLE",
        "INSUFFICIENT_INFORMATION",
    }
    assert data["recommendation"] in {
        "PROCEED",
        "PROCEED_AFTER_VALIDATION",
        "REVISE_SCENARIO",
        "REVIEW_REQUIRED",
    }
    assert isinstance(data["findings"], list)
    assert isinstance(data["recommendations"], list)


def test_assess_requires_login(client, scenario_result):
    client.headers.pop("Authorization", None)
    response = _assess(client, scenario_result)
    assert response.status_code in (401, 403)


def test_assess_does_not_need_assessed_by_in_the_body(client, decider, scenario_result):
    response = _assess(client, scenario_result, {"context": {}})
    assert response.status_code == 201, response.text
    assert response.json()["assessed_by"] == str(decider.user_id)


@pytest.mark.parametrize("claimed", ["not-a-uuid", str(uuid4())])
def test_assess_ignores_assessed_by_sent_in_the_body(
    client, decider, scenario_result, claimed
):
    """A caller cannot assess on behalf of someone else; the token decides."""
    response = _assess(client, scenario_result, {"assessed_by": claimed, "context": {}})
    assert response.status_code == 201, response.text
    assert response.json()["assessed_by"] == str(decider.user_id)


def test_get_decision(client, scenario_result):
    create_response = _assess(client, scenario_result)
    assert create_response.status_code == 201, create_response.text

    decision_id = create_response.json()["id"]

    response = client.get(f"/decision_support/{decision_id}")

    assert response.status_code == 200, response.text
    assert response.json()["id"] == decision_id


def test_list_decisions_for_scenario(client, scenario, scenario_result):
    create_response = _assess(client, scenario_result)
    assert create_response.status_code == 201, create_response.text

    response = client.get(
        f"/decision_support/scenario/{scenario.scenario_id}",
        params={"limit": 100, "offset": 0},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) == 1
    assert data[0]["scenario_result_id"] == str(scenario_result.results_id)


def test_reassess_updates_existing_decision(client, session, scenario_result):
    first_response = _assess(client, scenario_result)
    assert first_response.status_code == 201, first_response.text
    first_id = first_response.json()["id"]

    second_response = _assess(
        client,
        scenario_result,
        _body(
            {
                "infrastructure_status": "AVAILABLE",
                "regulatory_status": "CONFIRMED",
                "cost_data_complete": True,
            }
        ),
    )
    assert second_response.status_code == 201, second_response.text
    assert second_response.json()["id"] == first_id

    decisions = (
        session.query(ScenarioDecision)
        .filter(ScenarioDecision.scenario_result_id == str(scenario_result.results_id))
        .all()
    )
    assert len(decisions) == 1


def test_delete_decision(client, scenario_result):
    create_response = _assess(client, scenario_result)
    assert create_response.status_code == 201, create_response.text

    decision_id = create_response.json()["id"]

    assert client.delete(f"/decision_support/{decision_id}").status_code == 204
    assert client.get(f"/decision_support/{decision_id}").status_code == 404


def test_assess_requires_scenario_result_id(client):
    response = client.post("/decision_support/assess", json=_body())
    assert response.status_code == 422


def test_assess_rejects_invalid_context(client, scenario_result):
    response = _assess(client, scenario_result, _body({"technical_recovery_min": 1.5}))
    assert response.status_code == 422
