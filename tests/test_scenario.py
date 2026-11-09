from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from models import Scenario, ScenarioResult


def assert_decimal(actual, expected):
    assert Decimal(str(actual)) == Decimal(str(expected))


def test_create_scenario(session, scenario):
    session.refresh(scenario)

    assert scenario.scenario_id is not None
    assert scenario.batch_id is not None
    assert scenario.baseline_calculation_id is not None
    assert scenario.created_by is not None
    assert scenario.scenario_name == "Higher recovery"

    assert_decimal(scenario.assumed_quantity, "1000")
    assert_decimal(scenario.assumed_grade, "0.025")
    assert_decimal(scenario.assumed_recovery, "0.90")
    assert_decimal(scenario.assumed_price, "9500")

    assert scenario.price_unit == "USD/tonne"
    assert scenario.currency == "USD"


def test_scenario_has_correct_foreign_keys(
    scenario, batch, calculation, user, second_stage
):
    assert scenario.batch_id == batch.batch_id
    assert scenario.baseline_calculation_id == calculation.calculation_id
    assert scenario.created_by == user.user_id
    assert scenario.assumed_stage_id == second_stage.stage_id


def test_scenario_relationships(scenario, batch, calculation, user, second_stage):
    assert scenario.batch.batch_id == batch.batch_id
    assert scenario.baseline_calculation.calculation_id == calculation.calculation_id
    assert scenario.creator.user_id == user.user_id
    assert scenario.assumed_stage.stage_id == second_stage.stage_id


def test_scenario_can_be_reloaded(session, scenario):
    scenario_id = scenario.scenario_id

    session.expire_all()
    loaded = session.get(Scenario, scenario_id)

    assert loaded is not None
    assert loaded.scenario_id == scenario_id
    assert loaded.scenario_name == "Higher recovery"


def test_scenario_name_can_be_updated(session, scenario):
    scenario.scenario_name = "Recovery Improvement"
    session.commit()
    session.refresh(scenario)

    assert scenario.scenario_name == "Recovery Improvement"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("assumed_quantity", Decimal("-1")),
        ("assumed_grade", Decimal("-0.01")),
        ("assumed_grade", Decimal("1.01")),
        ("assumed_recovery", Decimal("-0.01")),
        ("assumed_recovery", Decimal("1.01")),
        ("assumed_price", Decimal("0")),
        ("assumed_price", Decimal("-1")),
    ],
)
def test_scenario_rejects_invalid_values(session, scenario_kwargs, field, value):
    data = dict(scenario_kwargs)
    data[field] = value

    session.add(Scenario(**data))

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


@pytest.mark.parametrize(
    "field",
    [
        "batch_id",
        "baseline_calculation_id",
        "created_by",
        "scenario_name",
        "assumed_quantity",
        "assumed_grade",
        "assumed_recovery",
        "assumed_price",
        "assumed_stage_id",
        "price_unit",
        "currency",
    ],
)
def test_scenario_rejects_null_required_fields(session, scenario_kwargs, field):
    data = dict(scenario_kwargs)
    data[field] = None

    session.add(Scenario(**data))

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_create_scenario_result(session, scenario, result_kwargs):
    result = ScenarioResult(**result_kwargs)

    session.add(result)
    session.commit()
    session.refresh(result)

    assert result.results_id is not None
    assert result.scenario_id == scenario.scenario_id

    assert_decimal(result.simulated_value, "213750")
    assert_decimal(result.baseline_value, "201875")
    assert_decimal(result.value_difference, "11875")
    assert_decimal(result.percentage_difference, "5.882353")


def test_scenario_results_relationship(session, scenario, result_kwargs):
    result = ScenarioResult(**result_kwargs)

    session.add(result)
    session.commit()
    session.refresh(scenario)

    assert len(scenario.results) == 1
    assert scenario.results[0].results_id == result.results_id


def test_scenario_can_have_multiple_executions(session, scenario, result_kwargs):
    first = ScenarioResult(**result_kwargs)

    second_data = dict(result_kwargs)
    second_data["execution_number"] = 2
    second_data["simulated_value"] = Decimal("215000")
    second_data["value_difference"] = Decimal("13125")

    second = ScenarioResult(**second_data)

    session.add_all([first, second])
    session.commit()
    session.refresh(scenario)

    assert len(scenario.results) == 2
    assert scenario.results[0].execution_number == 1
    assert scenario.results[1].execution_number == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("execution_number", 0),
        ("execution_number", -1),
        ("simulated_value", Decimal("-1")),
        ("baseline_value", Decimal("-1")),
    ],
)
def test_scenario_result_rejects_invalid_values(session, result_kwargs, field, value):
    data = dict(result_kwargs)
    data[field] = value

    session.add(ScenarioResult(**data))

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_scenario_result_execution_number_must_be_unique(session, result_kwargs):
    first = ScenarioResult(**result_kwargs)
    session.add(first)
    session.commit()

    duplicate = ScenarioResult(**result_kwargs)
    session.add(duplicate)

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_scenario_result_requires_scenario(session, result_kwargs):
    data = dict(result_kwargs)
    data["scenario_id"] = None

    session.add(ScenarioResult(**data))

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_scenario_can_be_deleted_without_results(session, scenario):
    scenario_id = scenario.scenario_id

    session.delete(scenario)
    session.commit()

    assert session.get(Scenario, scenario_id) is None
