import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from models import Scenario, ScenarioResult
from services import scenario_results as result_service

D = Decimal


@pytest.fixture()
def add_result(session, result_kwargs):
    def _add(**overrides):
        obj = ScenarioResult(**{**result_kwargs, **overrides})
        session.add(obj)
        session.commit()
        return obj

    return _add


def test_duplicate_execution_number_is_rejected_by_the_database(
    session, add_result, result_kwargs
):
    add_result()
    session.add(ScenarioResult(**result_kwargs))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_same_execution_number_allowed_for_different_scenarios(
    session, add_result, scenario_kwargs
):
    other = Scenario(**{**scenario_kwargs, "scenario_name": "Other"})
    session.add(other)
    session.commit()

    add_result()
    add_result(scenario_id=other.scenario_id)

    assert session.query(ScenarioResult).count() == 2


def test_scenario_has_results(session, scenario, add_result):
    assert result_service.scenario_has_results(session, scenario.scenario_id) is False
    add_result()
    assert result_service.scenario_has_results(session, scenario.scenario_id) is True


def test_result_cannot_reference_a_missing_scenario(session, result_kwargs):
    session.add(ScenarioResult(**{**result_kwargs, "scenario_id": uuid.uuid4()}))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_get_result_by_id(client, add_result, scenario):
    result = add_result()

    response = client.get(f"/scenario-results/{result.results_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["results_id"] == str(result.results_id)
    assert body["scenario_id"] == str(scenario.scenario_id)
    assert body["execution_number"] == 1


def test_result_serialisation_of_uuid_decimal_and_timestamp(client, add_result):
    result = add_result()

    body = client.get(f"/scenario-results/{result.results_id}").json()

    assert uuid.UUID(body["results_id"])
    assert D(body["simulated_value"]) == D("213750")
    assert D(body["baseline_value"]) == D("201875")
    assert D(body["value_difference"]) == D("11875")
    assert D(body["percentage_difference"]) == D("5.882353")
    assert isinstance(body["simulated_value"], str)
    assert datetime.fromisoformat(body["calculated_at"])


def test_null_percentage_is_returned_as_null(client, add_result):
    result = add_result(baseline_value=D("0"), percentage_difference=None)

    body = client.get(f"/scenario-results/{result.results_id}").json()

    assert body["percentage_difference"] is None


def test_missing_result_returns_404(client):
    missing = uuid.uuid4()

    response = client.get(f"/scenario-results/{missing}")

    assert response.status_code == 404
    assert response.json() == {"detail": f"Scenario result {missing} not found"}


def test_invalid_result_id_returns_422(client):
    assert client.get("/scenario-results/not-a-uuid").status_code == 422


def test_list_results_ordered_by_execution_number(client, scenario, add_result):
    for number in (3, 1, 2):
        add_result(execution_number=number)

    response = client.get(f"/scenarios/{scenario.scenario_id}/results")

    assert response.status_code == 200
    assert [r["execution_number"] for r in response.json()] == [1, 2, 3]


def test_list_results_only_returns_that_scenarios_results(
    client, session, scenario, scenario_kwargs, add_result
):
    other = Scenario(**{**scenario_kwargs, "scenario_name": "Other"})
    session.add(other)
    session.commit()
    add_result()
    add_result(scenario_id=other.scenario_id)

    body = client.get(f"/scenarios/{scenario.scenario_id}/results").json()

    assert [r["scenario_id"] for r in body] == [str(scenario.scenario_id)]


def test_list_results_empty_for_scenario_without_results(client, scenario):
    assert client.get(f"/scenarios/{scenario.scenario_id}/results").json() == []


def test_get_specific_execution(client, scenario, add_result):
    add_result(execution_number=1)
    add_result(execution_number=2)

    response = client.get(f"/scenarios/{scenario.scenario_id}/results/2")

    assert response.status_code == 200
    assert response.json()["execution_number"] == 2


def test_missing_execution_returns_404(client, scenario):
    assert client.get(f"/scenarios/{scenario.scenario_id}/results/9").status_code == 404


@pytest.mark.parametrize("number", ["0", "-1", "abc"])
def test_invalid_execution_number_returns_422(client, scenario, number):
    url = f"/scenarios/{scenario.scenario_id}/results/{number}"
    assert client.get(url).status_code == 422


def test_result_records_cannot_be_changed_through_the_api(client, add_result):
    result = add_result()
    url = f"/scenario-results/{result.results_id}"

    assert client.post(f"/scenarios/{result.scenario_id}/results").status_code == 405
    assert client.put(url, json={}).status_code == 405
    assert client.patch(url, json={}).status_code == 405
    assert client.delete(url).status_code == 405


def test_read_routes_are_registered_in_openapi(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert "get" in paths["/scenario-results/{results_id}"]
    assert "get" in paths["/scenarios/{scenario_id}/results"]
    assert "get" in paths["/scenarios/{scenario_id}/results/{execution_number}"]
