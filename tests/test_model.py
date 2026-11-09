import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import DataError, IntegrityError, StatementError

from models import (
    AccountStatus,
    BatchHistory,
    BatchStatus,
    MineralBatch,
    ProcessingStage,
    Scenario,
    ScenarioResult,
    SourceType,
    User,
    UserRole,
    ValueCalculation,
)


def test_calculation_is_saved(session, calculation):
    saved = session.get(ValueCalculation, calculation.calculation_id)
    assert saved.reference_price == Decimal("9500")
    assert saved.price_unit == "USD/tonne"
    assert saved.currency == "USD"
    assert saved.price_source == "LME"
    assert saved.price_date == date(2026, 1, 1)
    assert saved.contained_metal_tonnes == Decimal("25")
    assert saved.recoverable_metal_tonnes == Decimal("21.25")
    assert saved.calculated_value == Decimal("201875")


def test_defaults(calculation):
    assert isinstance(calculation.calculation_id, uuid.UUID)
    assert calculation.calculated_at is not None


@pytest.mark.parametrize(
    "field",
    [
        "batch_id",
        "batch_history_id",
        "stage_id",
        "reference_price",
        "price_unit",
        "currency",
        "price_source",
        "price_date",
        "contained_metal_tonnes",
        "recoverable_metal_tonnes",
        "calculated_value",
        "calculated_by",
    ],
)
def test_required_fields_cannot_be_null(calc_kwargs, rejected, field):
    rejected(ValueCalculation(**{**calc_kwargs, field: None}))


@pytest.mark.parametrize("price", [Decimal("0"), Decimal("-5")])
def test_reference_price_must_be_greater_than_zero(calc_kwargs, rejected, price):
    rejected(ValueCalculation(**{**calc_kwargs, "reference_price": price}))


@pytest.mark.parametrize(
    "field", ["contained_metal_tonnes", "recoverable_metal_tonnes", "calculated_value"]
)
def test_negative_amounts_are_rejected(calc_kwargs, rejected, field):
    rejected(ValueCalculation(**{**calc_kwargs, field: Decimal("-1")}))


@pytest.mark.parametrize(
    "field", ["contained_metal_tonnes", "recoverable_metal_tonnes", "calculated_value"]
)
def test_zero_amounts_are_allowed(session, calc_kwargs, field):
    session.add(ValueCalculation(**{**calc_kwargs, field: Decimal("0")}))
    session.commit()


def test_unknown_stage_is_rejected(calc_kwargs, rejected):
    rejected(ValueCalculation(**{**calc_kwargs, "stage_id": 99}))


def test_same_batch_can_be_valued_more_than_once(session, calculation, calc_kwargs):
    session.add(ValueCalculation(**{**calc_kwargs, "reference_price": Decimal("9600")}))
    session.commit()
    assert session.query(ValueCalculation).count() == 2


def test_calculation_relationships(calculation, batch, history, stage, user, scenario):
    assert calculation.batch == batch
    assert calculation.batch_history == history
    assert calculation.stage == stage
    assert calculation.calculator == user
    assert scenario in calculation.baseline_for_scenarios


@pytest.mark.parametrize("field", ["batch_id", "batch_history_id", "calculated_by"])
def test_unknown_references_are_rejected(calc_kwargs, rejected, field):
    rejected(ValueCalculation(**{**calc_kwargs, field: uuid.uuid4()}))


def test_user_is_saved_with_its_fields(session, user, user_kwargs):
    saved = session.get(User, user.user_id)
    assert saved.first_name == user_kwargs["first_name"]
    assert saved.last_name == user_kwargs["last_name"]
    assert saved.email == user_kwargs["email"]
    assert saved.password_hash == user_kwargs["password_hash"]
    assert saved.role == UserRole.OPERATIONS_MANAGER


def test_defaults_are_applied(user):
    assert isinstance(user.user_id, uuid.UUID)
    assert user.account_status == AccountStatus.ACTIVE
    assert user.created_at is not None


def test_email_must_be_unique(session, user, user_kwargs, rejected):
    rejected(User(**{**user_kwargs, "first_name": "Other"}))


@pytest.mark.parametrize("role", list(UserRole))
def test_every_role_is_accepted(session, user_kwargs, role):
    session.add(User(**{**user_kwargs, "role": role}))
    session.commit()
    assert session.query(User).one().role == role


def test_invalid_role_is_rejected(session, user_kwargs):
    session.add(User(**{**user_kwargs, "role": "SUPERUSER"}))

    with pytest.raises((LookupError, StatementError, IntegrityError, DataError)):
        session.commit()

    session.rollback()


def test_account_can_be_disabled(session, user):
    user.account_status = AccountStatus.DISABLED
    session.commit()
    session.expire_all()
    assert session.get(User, user.user_id).account_status == AccountStatus.DISABLED


def test_user_relationships_list_their_records(
    user, batch, history, calculation, scenario
):
    assert batch in user.batches
    assert history in user.history_events
    assert calculation in user.value_calculations
    assert scenario in user.scenarios


def test_scenario_is_saved(session, scenario):
    saved = session.get(Scenario, scenario.scenario_id)
    assert saved.scenario_name == "Higher recovery"
    assert saved.assumed_quantity == Decimal("1000")
    assert saved.assumed_grade == Decimal("0.025")
    assert saved.assumed_recovery == Decimal("0.90")
    assert saved.assumed_price == Decimal("9500")
    assert saved.price_unit == "USD/tonne"
    assert saved.currency == "USD"


def test_primary_key_is_a_uuid(scenario):
    assert isinstance(scenario.scenario_id, uuid.UUID)


def test_negative_quantity_is_rejected(scenario_kwargs, rejected):
    rejected(Scenario(**{**scenario_kwargs, "assumed_quantity": Decimal("-1")}))


def test_zero_assumed_quantity_is_allowed(session, scenario_kwargs):
    session.add(Scenario(**{**scenario_kwargs, "assumed_quantity": Decimal("0")}))
    session.commit()


@pytest.mark.parametrize("value", [Decimal("-0.1"), Decimal("1.1")])
def test_grade_outside_zero_to_one_is_rejected(scenario_kwargs, rejected, value):
    rejected(Scenario(**{**scenario_kwargs, "assumed_grade": value}))


@pytest.mark.parametrize("value", [Decimal("-0.1"), Decimal("1.1")])
def test_recovery_outside_zero_to_one_is_rejected(scenario_kwargs, rejected, value):
    rejected(Scenario(**{**scenario_kwargs, "assumed_recovery": value}))


@pytest.mark.parametrize("price", [Decimal("0"), Decimal("-5")])
def test_price_must_be_greater_than_zero(scenario_kwargs, rejected, price):
    rejected(Scenario(**{**scenario_kwargs, "assumed_price": price}))


def test_one_calculation_can_baseline_many_scenarios(
    session, scenario, scenario_kwargs, calculation
):
    session.add(Scenario(**{**scenario_kwargs, "scenario_name": "Second"}))
    session.commit()
    assert len(calculation.baseline_for_scenarios) == 2


def test_scenario_relationships(
    scenario, batch, calculation, user, second_stage, result_kwargs, session
):
    assert scenario.batch == batch
    assert scenario.baseline_calculation == calculation
    assert scenario.creator == user
    assert scenario.assumed_stage == second_stage
    assert scenario.results == []


@pytest.fixture()
def result(session, result_kwargs):
    obj = ScenarioResult(**result_kwargs)
    session.add(obj)
    session.commit()
    return obj


def test_result_is_saved(session, result):
    saved = session.get(ScenarioResult, result.results_id)
    assert saved.execution_number == 1
    assert saved.simulated_value == Decimal("213750")
    assert saved.baseline_value == Decimal("201875")
    assert saved.value_difference == Decimal("11875")
    assert saved.percentage_difference == Decimal("5.882353")


def test_percentage_difference_is_optional(session, result_kwargs):
    obj = ScenarioResult(
        **{
            **result_kwargs,
            "baseline_value": Decimal("0"),
            "percentage_difference": None,
        }
    )
    session.add(obj)
    session.commit()
    assert obj.percentage_difference is None


def test_value_difference_may_be_negative(session, result_kwargs):
    obj = ScenarioResult(
        **{
            **result_kwargs,
            "simulated_value": Decimal("100"),
            "value_difference": Decimal("-201775"),
        }
    )
    session.add(obj)
    session.commit()
    assert obj.value_difference == Decimal("-201775")


def test_execution_number_must_be_unique_within_a_scenario(
    result, result_kwargs, rejected
):
    rejected(ScenarioResult(**result_kwargs))


def test_same_execution_number_is_allowed_in_another_scenario(
    session, result, result_kwargs, scenario_kwargs
):
    other = Scenario(**{**scenario_kwargs, "scenario_name": "Other"})
    session.add(other)
    session.commit()

    session.add(ScenarioResult(**{**result_kwargs, "scenario_id": other.scenario_id}))
    session.commit()

    assert session.query(ScenarioResult).count() == 2


@pytest.mark.parametrize("number", [0, -1])
def test_execution_number_must_be_greater_than_zero(result_kwargs, rejected, number):
    rejected(ScenarioResult(**{**result_kwargs, "execution_number": number}))


@pytest.mark.parametrize("field", ["simulated_value", "baseline_value"])
def test_negative_values_are_rejected(result_kwargs, rejected, field):
    rejected(ScenarioResult(**{**result_kwargs, field: Decimal("-1")}))


def test_unknown_scenario_is_rejected(result_kwargs, rejected):
    rejected(ScenarioResult(**{**result_kwargs, "scenario_id": uuid.uuid4()}))


def test_results_are_ordered_by_execution_number(session, scenario, result_kwargs):
    for number in (3, 1, 2):
        session.add(ScenarioResult(**{**result_kwargs, "execution_number": number}))

    session.commit()
    session.refresh(scenario)

    assert [result.execution_number for result in scenario.results] == [1, 2, 3]


def test_result_links_back_to_its_scenario(result, scenario):
    assert result.scenario == scenario
    assert result in scenario.results


def test_stage_is_saved(session, stage, stage_kwargs):
    saved = session.get(ProcessingStage, stage.stage_id)
    assert saved.stage_name == stage_kwargs["stage_name"]
    assert saved.stage_order == stage_kwargs["stage_order"]


def test_stage_name_must_be_unique(stage, rejected):
    rejected(ProcessingStage(stage_id=2, stage_name="Mining", stage_order=2))


def test_stage_order_must_be_unique(stage, rejected):
    rejected(ProcessingStage(stage_id=2, stage_name="Other", stage_order=1))


@pytest.mark.parametrize("order", [0, -1])
def test_stage_order_must_be_greater_than_zero(rejected, order):
    rejected(ProcessingStage(stage_id=5, stage_name="Bad", stage_order=order))


def test_stage_relationships_list_their_records(
    stage, second_stage, batch, history, calculation, scenario
):
    assert batch in stage.batches
    assert history in stage.history_records
    assert calculation in stage.value_calculations
    assert scenario in second_stage.scenarios


def test_batch_is_saved_with_its_fields(session, batch, batch_kwargs):
    saved = session.get(MineralBatch, batch.batch_id)
    assert saved.batch_code == "B-001"
    assert saved.source_type == SourceType.PURCHASED
    assert saved.quantity_tonnes == Decimal("1000")
    assert saved.grade == Decimal("0.025")
    assert saved.recovery == Decimal("0.85")
    assert saved.stage_id == batch_kwargs["stage_id"]


def test_defaults_applied(batch):
    assert isinstance(batch.batch_id, uuid.UUID)
    assert batch.mineral_type == "COPPER"
    assert batch.status == BatchStatus.ACTIVE
    assert batch.created_at is not None


def test_recovery_is_optional(session, batch_kwargs):
    session.add(MineralBatch(**{**batch_kwargs, "recovery": None}))
    session.commit()
    assert session.query(MineralBatch).one().recovery is None


def test_batch_code_must_be_unique(batch, batch_kwargs, rejected):
    rejected(MineralBatch(**batch_kwargs))


@pytest.mark.parametrize("source", list(SourceType))
def test_both_source_types_are_accepted(session, batch_kwargs, source):
    session.add(MineralBatch(**{**batch_kwargs, "source_type": source}))
    session.commit()
    assert session.query(MineralBatch).one().source_type == source


def test_only_copper_is_allowed(batch_kwargs, rejected):
    rejected(MineralBatch(**{**batch_kwargs, "mineral_type": "GOLD"}))


def test_zero_quantity_is_allowed(session, batch_kwargs):
    session.add(MineralBatch(**{**batch_kwargs, "quantity_tonnes": Decimal("0")}))
    session.commit()


@pytest.mark.parametrize("grade", [Decimal("0"), Decimal("1")])
def test_grade_boundaries_are_allowed(session, batch_kwargs, grade):
    session.add(MineralBatch(**{**batch_kwargs, "grade": grade}))
    session.commit()


@pytest.mark.parametrize("recovery", [Decimal("-0.1"), Decimal("1.1")])
def test_recovery_outside_zero(batch_kwargs, rejected, recovery):
    rejected(MineralBatch(**{**batch_kwargs, "recovery": recovery}))


def test_unknown_creator_is_rejected(batch_kwargs, rejected):
    rejected(MineralBatch(**{**batch_kwargs, "created_by": uuid.uuid4()}))


def test_batch_relationships(batch, user, stage, history, calculation, scenario):
    assert batch.creator == user
    assert batch.stage == stage
    assert history in batch.history
    assert calculation in batch.value_calculations
    assert scenario in batch.scenarios


def test_history_is_saved(session, history, batch, stage, user):
    saved = session.get(BatchHistory, history.history_id)
    assert saved.batch_id == batch.batch_id
    assert saved.current_stage_id == stage.stage_id
    assert saved.recorded_by == user.user_id


def test_reason_and_snapshot_values_are_optional(history):
    assert history.reason is None
    assert history.quantity_tonnes is None
    assert history.grade is None
    assert history.recovery is None


def test_reason_and_snapshot_values_are_stored(session, history_kwargs):
    obj = BatchHistory(
        **history_kwargs,
        reason="Grade corrected after assay",
        quantity_tonnes=Decimal("990"),
        grade=Decimal("0.024"),
        recovery=Decimal("0.80"),
    )
    session.add(obj)
    session.commit()

    assert obj.reason == "Grade corrected after assay"
    assert obj.quantity_tonnes == Decimal("990")
    assert obj.grade == Decimal("0.024")
    assert obj.recovery == Decimal("0.80")


def test_unknown_batch_is_rejected(history_kwargs, rejected):
    rejected(BatchHistory(**{**history_kwargs, "batch_id": uuid.uuid4()}))


def test_unknown_user_is_rejected(history_kwargs, rejected):
    rejected(BatchHistory(**{**history_kwargs, "recorded_by": uuid.uuid4()}))


def test_negative_snapshot_quantity_is_rejected(history_kwargs, rejected):
    rejected(BatchHistory(**{**history_kwargs, "quantity_tonnes": Decimal("-1")}))


@pytest.mark.parametrize("value", [Decimal("-0.1"), Decimal("1.1")])
def test_snapshot_grade_outside_zero_to_one_is_rejected(
    history_kwargs, rejected, value
):
    rejected(BatchHistory(**{**history_kwargs, "grade": value}))


@pytest.mark.parametrize("value", [Decimal("-0.1"), Decimal("1.1")])
def test_snapshot_recovery_outside_zero_to_one_is_rejected(
    history_kwargs, rejected, value
):
    rejected(BatchHistory(**{**history_kwargs, "recovery": value}))


def test_batch_history_is_ordered_by_occurred_at(
    session, batch, history_kwargs, second_stage
):
    later = BatchHistory(
        **{
            **history_kwargs,
            "occurred_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
        }
    )
    earlier = BatchHistory(
        **{
            **history_kwargs,
            "current_stage_id": second_stage.stage_id,
            "occurred_at": datetime(2026, 2, 1, tzinfo=timezone.utc),
        }
    )

    session.add_all([later, earlier])
    session.commit()
    session.refresh(batch)

    assert [item.history_id for item in batch.history][-2:] == [
        earlier.history_id,
        later.history_id,
    ]


def test_history_relationships(history, batch, stage, user, calculation):
    assert history.batch == batch
    assert history.stage == stage
    assert history.recorder == user
    assert calculation in history.value_calculations
