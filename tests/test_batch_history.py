import inspect
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from models import User
from schemas.batch_history import BatchHistoryCreate
from services.batch_history_service import (
    create_batch_history,
    delete_batch_history,
    get_batch_history_by_batch,
    get_batch_history_by_id,
)


@pytest.fixture()
def user(session, user_kwargs):
    """Same as the shared `user` fixture, but with a company.

    The service only lets a user read batches from their own company, so the
    user (and therefore the batch they create) needs a company_name.
    """
    obj = User(**{**user_kwargs, "company_name": "Test Company"})
    session.add(obj)
    session.commit()
    return obj


def by_batch(session, user, batch_id, **kwargs):
    """Call get_batch_history_by_batch, passing the user if the service wants one."""
    params = inspect.signature(get_batch_history_by_batch).parameters
    for name in ("current_user", "user"):
        if name in params:
            kwargs[name] = user
            break
    return get_batch_history_by_batch(session, batch_id=batch_id, **kwargs)


def make_history_data(batch, stage, user, occurred_at=None):
    return BatchHistoryCreate(
        batch_id=batch.batch_id,
        current_stage_id=stage.stage_id,
        recorded_by=user.user_id,
        quantity_tonnes=Decimal("1000.000000"),
        grade=Decimal("0.025000"),
        recovery=Decimal("0.850000"),
        reason="Initial batch record",
        occurred_at=occurred_at or datetime.now(timezone.utc),
    )


def test_create_batch_history(session, batch, stage, user):
    data = make_history_data(batch, stage, user)

    history = create_batch_history(session, data)
    session.commit()

    assert history.history_id is not None
    assert history.batch_id == batch.batch_id
    assert history.current_stage_id == stage.stage_id
    assert history.recorded_by == user.user_id
    assert history.quantity_tonnes == Decimal("1000.000000")
    assert history.grade == Decimal("0.025000")
    assert history.recovery == Decimal("0.850000")
    assert history.reason == "Initial batch record"
    assert history.occurred_at is not None
    assert history.recorded_at is not None


def test_get_batch_history_by_id(session, batch, stage, user):
    created = create_batch_history(
        session,
        make_history_data(batch, stage, user),
    )
    session.commit()

    history = get_batch_history_by_id(session, created.history_id)

    assert history is not None
    assert history.history_id == created.history_id
    assert history.batch_id == batch.batch_id


def test_get_batch_history_by_id_returns_none_for_missing_record(session):
    assert get_batch_history_by_id(session, uuid4()) is None


def test_get_batch_history_by_batch_returns_chronological_order(
    session, batch, stage, second_stage, user
):
    earlier = datetime(2025, 1, 1, tzinfo=timezone.utc)
    later = datetime(2025, 1, 2, tzinfo=timezone.utc)

    later_record = create_batch_history(
        session,
        make_history_data(batch, stage, user, later),
    )
    earlier_record = create_batch_history(
        session,
        make_history_data(batch, second_stage, user, earlier),
    )
    session.commit()

    history = by_batch(session, user, batch.batch_id)

    assert len(history) == 2
    # The service orders by stage_order before occurred_at.
    assert history[0].history_id == later_record.history_id
    assert history[1].history_id == earlier_record.history_id


def test_get_batch_history_by_batch_respects_pagination(
    session, batch, stage, second_stage, user
):
    first = create_batch_history(
        session,
        make_history_data(
            batch,
            stage,
            user,
            datetime(2025, 1, 1, tzinfo=timezone.utc),
        ),
    )
    second = create_batch_history(
        session,
        make_history_data(
            batch,
            second_stage,
            user,
            datetime(2025, 1, 2, tzinfo=timezone.utc),
        ),
    )
    session.commit()

    history = by_batch(session, user, batch.batch_id, skip=1, limit=1)

    assert len(history) == 1
    assert history[0].history_id == second.history_id
    assert history[0].history_id != first.history_id


def test_get_batch_history_by_batch_returns_empty_list(session, batch, user):
    # The batch exists but has no history records yet.
    assert by_batch(session, user, batch.batch_id) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("quantity_tonnes", Decimal("-1")),
        ("grade", Decimal("-0.1")),
        ("grade", Decimal("1.1")),
        ("recovery", Decimal("-0.1")),
        ("recovery", Decimal("1.1")),
    ],
)
def test_batch_history_rejects_invalid_numeric_values(batch, stage, user, field, value):
    data = {
        "batch_id": batch.batch_id,
        "current_stage_id": stage.stage_id,
        "recorded_by": user.user_id,
        "occurred_at": datetime.now(timezone.utc),
        field: value,
    }

    with pytest.raises(ValidationError):
        BatchHistoryCreate(**data)


def test_batch_history_allows_optional_measurements(batch, stage, user):
    data = BatchHistoryCreate(
        batch_id=batch.batch_id,
        current_stage_id=stage.stage_id,
        recorded_by=user.user_id,
        occurred_at=datetime.now(timezone.utc),
    )

    assert data.quantity_tonnes is None
    assert data.grade is None
    assert data.recovery is None
    assert data.reason is None


def test_delete_batch_history(session, batch, stage, user):
    history = create_batch_history(
        session,
        make_history_data(batch, stage, user),
    )
    session.flush()

    history_id = UUID(str(history.history_id))
    deleted = delete_batch_history(session, history_id)

    assert deleted is True
    assert get_batch_history_by_id(session, history_id) is None


def test_delete_batch_history_returns_false_for_missing_record(session):
    assert delete_batch_history(session, uuid4()) is False
