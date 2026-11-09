import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

import pytest
from pydantic import ValidationError

from repositories.value_calculation_repository import ValueCalculationRepository
from schemas.value_calculation import ValueCalculationCreate, ValueCalculationResponse
from services import value_calculation_service as svc
from services.value_calculation_service import (
    NoUserAvailableError,
    PriceUnavailableError,
    ValueCalculationService,
)

TEST_PRICE = Decimal("10000")
AMOUNT_FIELDS = [
    "quantity",
    "contained_metal_tonnes",
    "recoverable_metal_tonnes",
    "calculated_value",
]


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code
        self.text = ""

    def json(self):
        return self._data


@pytest.fixture()
def response_data():
    return dict(
        calculation_id=uuid.uuid4(),
        batch_id=uuid.uuid4(),
        batch_history_id=uuid.uuid4(),
        stage_id=2,
        quantity=Decimal("1000"),
        grade=Decimal("0.025"),
        recovery=Decimal("0.85"),
        reference_price=Decimal("14751.02138"),
        price_date=date(2026, 10, 15),
        contained_metal_tonnes=Decimal("25"),
        recoverable_metal_tonnes=Decimal("21.25"),
        calculated_value=Decimal("313459.2"),
        calculated_at=datetime(2026, 10, 15, 7, 0, tzinfo=timezone.utc),
        calculated_by=uuid.uuid4(),
    )


@pytest.fixture()
def repository(session):
    return ValueCalculationRepository(session)


@pytest.fixture()
def service(session, monkeypatch):
    monkeypatch.setattr(
        ValueCalculationService, "_fetch_lme_price", lambda self: TEST_PRICE
    )
    return ValueCalculationService(session)


@pytest.fixture()
def price_service(monkeypatch):
    monkeypatch.setattr(svc.settings, "LME_API_KEY", "test-key")
    monkeypatch.setattr(svc.settings, "LME_API_URL", "https://example.test/api")
    monkeypatch.setattr(svc.settings, "LME_SYMBOL", "LME-XCU")
    monkeypatch.setattr(svc.settings, "LME_UNIT_TO_TONNE", 32150.7466)
    return ValueCalculationService(db=None)


def test_schema_accepts_valid_data(response_data):
    result = ValueCalculationResponse(**response_data)
    assert result.reference_price == Decimal("14751.02138")


def test_schema_defaults(response_data):
    result = ValueCalculationResponse(**response_data)
    assert result.quantity_unit == "tonnes"
    assert result.price_unit == "USD/tonne"
    assert result.currency == "USD"
    assert result.price_source == "Metals-API (LME copper)"


def test_schema_is_built_from_a_database_row(calculation):
    result = ValueCalculationResponse.model_validate(calculation)
    assert result.calculation_id == calculation.calculation_id
    assert result.batch_id == calculation.batch_id


def test_schema_recovery_is_optional(response_data):
    response_data["recovery"] = None
    assert ValueCalculationResponse(**response_data).recovery is None


@pytest.mark.parametrize("price", [Decimal("0"), Decimal("-1")])
def test_schema_reference_price_must_be_greater_than_zero(response_data, price):
    response_data["reference_price"] = price
    with pytest.raises(ValidationError):
        ValueCalculationResponse(**response_data)


@pytest.mark.parametrize("field", ["grade", "recovery"])
@pytest.mark.parametrize("value", [Decimal("-0.1"), Decimal("1.1")])
def test_schema_grade_and_recovery_must_be_between_zero_and_one(
    response_data, field, value
):
    response_data[field] = value
    with pytest.raises(ValidationError):
        ValueCalculationResponse(**response_data)


@pytest.mark.parametrize("field", AMOUNT_FIELDS)
def test_schema_zero_amounts_are_allowed(response_data, field):
    response_data[field] = Decimal("0")
    assert ValueCalculationResponse(**response_data)


@pytest.mark.parametrize("field", AMOUNT_FIELDS)
def test_schema_negative_amounts_are_rejected(response_data, field):
    response_data[field] = Decimal("-1")
    with pytest.raises(ValidationError):
        ValueCalculationResponse(**response_data)


def test_schema_create_requires_all_fields():
    with pytest.raises(ValidationError):
        ValueCalculationCreate()


def test_schema_create_accepts_valid_data():
    data = ValueCalculationCreate(
        batch_id=uuid.uuid4(),
        batch_history_id=uuid.uuid4(),
        stage_id=1,
        calculated_by=uuid.uuid4(),
    )
    assert data.stage_id == 1


def test_repository_create_saves_and_returns_the_calculation(repository, calc_kwargs):
    saved = repository.create(calc_kwargs)
    assert saved.calculation_id is not None
    assert saved.batch_id == calc_kwargs["batch_id"]
    assert saved.calculated_at is not None


def test_repository_create_accepts_string_ids(repository, calc_kwargs):
    data = {
        **calc_kwargs,
        "batch_id": str(calc_kwargs["batch_id"]),
        "batch_history_id": str(calc_kwargs["batch_history_id"]),
        "calculated_by": str(calc_kwargs["calculated_by"]),
    }
    saved = repository.create(data)
    assert saved.batch_id == calc_kwargs["batch_id"]
    assert saved.calculated_by == calc_kwargs["calculated_by"]


def test_repository_create_does_not_change_the_input(repository, calc_kwargs):
    original = dict(calc_kwargs)
    repository.create(calc_kwargs)
    assert calc_kwargs == original


def test_repository_get_returns_the_saved_calculation(repository, calc_kwargs):
    saved = repository.create(calc_kwargs)
    assert repository.get(saved.calculation_id).calculation_id == saved.calculation_id


def test_repository_get_returns_none_for_an_unknown_id(repository):
    assert repository.get(uuid.uuid4()) is None


def test_repository_get_by_batch_returns_every_calculation(repository, calc_kwargs):
    repository.create(calc_kwargs)
    repository.create(calc_kwargs)
    results = repository.get_by_batch(calc_kwargs["batch_id"])
    assert len(results) == 2
    assert results[0].calculation_id != results[1].calculation_id


def test_repository_get_by_batch_returns_nothing_for_an_unknown_batch(
    repository, calc_kwargs
):
    repository.create(calc_kwargs)
    assert repository.get_by_batch(uuid.uuid4()) == []


def test_repository_get_by_batch_history_returns_matching_calculations(
    repository, calc_kwargs
):
    repository.create(calc_kwargs)
    results = repository.get_by_batch_history(calc_kwargs["batch_history_id"])
    assert len(results) == 1
    assert results[0].batch_history_id == calc_kwargs["batch_history_id"]


def test_repository_get_by_batch_history_returns_nothing_for_an_unknown_history(
    repository, calc_kwargs
):
    repository.create(calc_kwargs)
    assert repository.get_by_batch_history(uuid.uuid4()) == []


def test_price_is_taken_from_latest_and_converted_to_tonnes(price_service, monkeypatch):
    calls = {}

    def fake_get(url, params=None, timeout=None):
        calls["url"] = url
        calls["params"] = params
        return FakeResponse({"success": True, "rates": {"USDLME-XCU": 0.458808}})

    monkeypatch.setattr(svc.requests, "get", fake_get)

    price = price_service._fetch_lme_price()

    expected = (Decimal("0.458808") * Decimal("32150.7466")).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    assert price == expected
    assert calls["url"] == "https://example.test/api/latest"
    assert calls["params"]["symbols"] == "LME-XCU"
    assert calls["params"]["base"] == "USD"


def test_price_api_success_false_raises(price_service, monkeypatch):
    monkeypatch.setattr(
        svc.requests,
        "get",
        lambda *a, **k: FakeResponse({"success": False, "error": {"code": 101}}),
    )
    with pytest.raises(PriceUnavailableError):
        price_service._fetch_lme_price()


def test_price_missing_symbol_raises(price_service, monkeypatch):
    monkeypatch.setattr(
        svc.requests,
        "get",
        lambda *a, **k: FakeResponse({"success": True, "rates": {}}),
    )
    with pytest.raises(PriceUnavailableError):
        price_service._fetch_lme_price()


def test_price_http_error_raises(price_service, monkeypatch):
    monkeypatch.setattr(
        svc.requests, "get", lambda *a, **k: FakeResponse({}, status_code=500)
    )
    with pytest.raises(PriceUnavailableError):
        price_service._fetch_lme_price()


def test_service_value_is_calculated_from_the_batch_values(
    service, batch, history, user
):
    result = service.calculate_for_batch(batch.batch_id, user.user_id)
    assert result.contained_metal_tonnes == Decimal("25")
    assert result.recoverable_metal_tonnes == Decimal("21.25")
    assert result.reference_price == TEST_PRICE
    assert result.calculated_value == Decimal("212500")


def test_service_history_values_take_priority_over_batch_values(
    service, session, batch, history, user
):
    history.quantity_tonnes = Decimal("500")
    history.grade = Decimal("0.05")
    history.recovery = Decimal("0.5")
    session.commit()

    result = service.calculate_for_batch(batch.batch_id, user.user_id)

    assert result.contained_metal_tonnes == Decimal("25")
    assert result.recoverable_metal_tonnes == Decimal("12.5")
    assert result.calculated_value == Decimal("125000")


def test_service_calculation_has_todays_date_and_labels(service, batch, history, user):
    result = service.calculate_for_batch(batch.batch_id, user.user_id)
    assert result.price_date == date.today()
    assert result.current_price == result.reference_price
    assert result.price_unit == "USD/tonne"
    assert result.currency == "USD"
    assert result.price_source == "Metals-API (LME copper)"
    assert result.calculated_by == user.user_id
    assert result.batch_history_id == history.history_id


def test_service_every_call_saves_a_new_calculation(service, batch, history, user):
    first = service.calculate_for_batch(batch.batch_id, user.user_id)
    second = service.calculate_for_batch(batch.batch_id, user.user_id)
    assert first.calculation_id != second.calculation_id
    assert len(service.get_calculations_by_batch(batch.batch_id)) == 2


def test_service_unknown_batch_raises_lookup_error(service, user):
    with pytest.raises(LookupError):
        service.calculate_for_batch(uuid.uuid4(), user.user_id)


def test_service_batch_without_history_raises_lookup_error(service, batch, user):
    with pytest.raises(LookupError):
        service.calculate_for_batch(batch.batch_id, user.user_id)


def test_service_price_failure_saves_nothing(
    session, monkeypatch, batch, history, user
):
    def failing_price(self):
        raise PriceUnavailableError("down")

    monkeypatch.setattr(ValueCalculationService, "_fetch_lme_price", failing_price)
    failing_service = ValueCalculationService(session)

    with pytest.raises(PriceUnavailableError):
        failing_service.calculate_for_batch(batch.batch_id, user.user_id)

    assert failing_service.get_calculations_by_batch(batch.batch_id) == []


def test_service_default_user_is_the_first_user(service, user):
    assert service.get_default_user_id() == user.user_id


def test_service_no_user_raises_an_error(service):
    with pytest.raises(NoUserAvailableError):
        service.get_default_user_id()


def test_service_calculations_can_be_listed_by_batch_and_by_history(
    service, batch, history, user
):
    service.calculate_for_batch(batch.batch_id, user.user_id)
    assert len(service.get_calculations_by_batch(batch.batch_id)) == 1
    assert len(service.get_calculations_by_batch_history(history.history_id)) == 1
