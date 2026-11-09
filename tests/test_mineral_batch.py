import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, insert
from sqlalchemy.exc import IntegrityError

import routers.mineral_batch as router_module
from core.auth import get_current_user
from database import get_db
from main import app
from models import MineralBatch, ProcessingStage


def test_stage_is_saved_with_its_fields(session, stage, stage_kwargs):
    saved = session.get(ProcessingStage, stage_kwargs["stage_id"])
    assert saved.stage_name == "Mining"
    assert saved.stage_order == 1


def test_stage_id_is_not_auto_generated(session):
    """stage_id is supplied by the caller, so ids can be fixed (1, 2, 3...)."""
    session.add(ProcessingStage(stage_id=7, stage_name="Refining", stage_order=7))
    session.commit()
    assert session.get(ProcessingStage, 7).stage_name == "Refining"


@pytest.mark.parametrize("field", ["stage_name", "stage_order"])
def test_required_fields_cannot_be_null(rejected, field):
    kwargs = dict(stage_id=5, stage_name="Smelting", stage_order=5)
    kwargs[field] = None
    rejected(ProcessingStage(**kwargs))


def test_stage_name_must_be_unique(stage, rejected):
    rejected(ProcessingStage(stage_id=2, stage_name="Mining", stage_order=2))


def test_stage_order_must_be_unique(stage, rejected):
    rejected(ProcessingStage(stage_id=2, stage_name="Other", stage_order=1))


@pytest.mark.parametrize("order", [0, -1, -100])
def test_stage_order_must_be_greater_than_zero(rejected, order):
    rejected(ProcessingStage(stage_id=5, stage_name="Bad", stage_order=order))


def test_large_stage_order_is_allowed(session, stage):
    session.add(ProcessingStage(stage_id=9, stage_name="Last", stage_order=100))
    session.commit()
    assert session.get(ProcessingStage, 9).stage_order == 100


def test_stages_can_be_listed_in_order(session, stage, second_stage):
    names = [
        s.stage_name
        for s in session.query(ProcessingStage).order_by(ProcessingStage.stage_order)
    ]
    assert names == ["Mining", "Concentrating"]


def test_stage_lists_its_batches(stage, batch):
    assert batch in stage.batches
    assert batch.stage == stage


def test_stage_with_no_batches_has_empty_list(second_stage, batch):
    assert second_stage.batches == []


def test_moving_a_batch_updates_both_stages(session, stage, second_stage, batch):
    batch.stage = second_stage
    session.commit()
    assert batch in second_stage.batches
    assert batch not in stage.batches
    assert batch.stage_id == second_stage.stage_id


def test_batch_requires_a_stage(batch_kwargs, rejected):
    kwargs = {**batch_kwargs, "batch_code": "B-NOSTAGE"}
    del kwargs["stage_id"]
    rejected(MineralBatch(**kwargs))


def test_batch_with_unknown_stage_is_rejected(batch_kwargs, rejected):
    kwargs = {**batch_kwargs, "batch_code": "B-BADSTAGE", "stage_id": 99}
    rejected(MineralBatch(**kwargs))


def test_stage_in_use_cannot_be_deleted(session, stage, batch):
    from sqlalchemy.exc import IntegrityError

    session.delete(stage)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_unused_stage_can_be_deleted(session, second_stage):
    stage_id = second_stage.stage_id
    session.delete(second_stage)
    session.commit()
    assert session.get(ProcessingStage, stage_id) is None


def test_table_name():
    assert ProcessingStage.__tablename__ == "processing_stages"


def test_primary_key_is_stage_id():
    table = ProcessingStage.__table__
    assert [c.name for c in table.primary_key.columns] == ["stage_id"]


@pytest.mark.parametrize("column", ["stage_name", "stage_order"])
def test_columns_are_required_and_unique(column):
    col = ProcessingStage.__table__.c[column]
    assert col.nullable is False
    assert col.unique is True


def test_order_check_constraint_is_defined():
    names = {c.name for c in ProcessingStage.__table__.constraints}
    assert "ck_processing_stages_order_positive" in names


def test_duplicate_stage_id_is_rejected(session, stage):
    """A Core insert makes the database, not the ORM identity map, reject it."""
    with pytest.raises(IntegrityError):
        session.execute(
            insert(ProcessingStage.__table__).values(
                stage_id=stage.stage_id, stage_name="Another", stage_order=50
            )
        )
    session.rollback()


def test_rejected_stage_is_not_saved(session, stage, rejected):
    rejected(ProcessingStage(stage_id=2, stage_name="Mining", stage_order=2))
    assert session.query(ProcessingStage).count() == 1


def test_stage_order_may_have_gaps(session, stage):
    session.add(ProcessingStage(stage_id=2, stage_name="Smelting", stage_order=10))
    session.commit()
    orders = [
        s.stage_order
        for s in session.query(ProcessingStage).order_by(ProcessingStage.stage_order)
    ]
    assert orders == [1, 10]


def test_many_stages_can_be_saved(session):
    session.add_all(
        ProcessingStage(stage_id=i, stage_name=f"Stage {i}", stage_order=i)
        for i in range(1, 8)
    )
    session.commit()
    assert session.query(ProcessingStage).count() == 7


def test_stage_name_of_100_characters_is_allowed(session):
    name = "x" * 100
    session.add(ProcessingStage(stage_id=3, stage_name=name, stage_order=3))
    session.commit()
    assert session.get(ProcessingStage, 3).stage_name == name


def test_stage_names_are_case_sensitive(session, stage):
    session.add(ProcessingStage(stage_id=2, stage_name="mining", stage_order=2))
    session.commit()
    assert session.query(ProcessingStage).count() == 2


def test_stage_can_be_found_by_name(session, stage):
    found = session.query(ProcessingStage).filter_by(stage_name="Mining").one()
    assert found.stage_id == stage.stage_id


def test_unknown_stage_name_returns_nothing(session, stage):
    assert session.query(ProcessingStage).filter_by(stage_name="Nope").first() is None


def test_order_follows_stage_order_not_stage_id(session):
    session.add_all(
        [
            ProcessingStage(stage_id=1, stage_name="Last", stage_order=3),
            ProcessingStage(stage_id=2, stage_name="First", stage_order=1),
            ProcessingStage(stage_id=3, stage_name="Middle", stage_order=2),
        ]
    )
    session.commit()
    names = [
        s.stage_name
        for s in session.query(ProcessingStage).order_by(ProcessingStage.stage_order)
    ]
    assert names == ["First", "Middle", "Last"]


def test_stage_can_be_renamed(session, stage):
    stage.stage_name = "Open-pit mining"
    session.commit()
    session.expire_all()
    assert session.get(ProcessingStage, stage.stage_id).stage_name == "Open-pit mining"


def test_rename_to_existing_name_is_rejected(session, stage, second_stage):
    second_stage.stage_name = "Mining"
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_update_order_to_zero_is_rejected(session, stage):
    stage.stage_order = 0
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_update_order_to_unused_value_is_allowed(session, stage, second_stage):
    second_stage.stage_order = 5
    session.commit()
    assert session.get(ProcessingStage, second_stage.stage_id).stage_order == 5


def test_update_order_to_used_value_is_rejected(session, stage, second_stage):
    second_stage.stage_order = stage.stage_order
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_stage_can_hold_many_batches(session, stage, batch, batch_kwargs):
    other = MineralBatch(**{**batch_kwargs, "batch_code": "B-002"})
    session.add(other)
    session.commit()
    assert set(stage.batches) == {batch, other}


def test_changing_stage_id_directly_moves_the_batch(
    session, stage, second_stage, batch
):
    batch.stage_id = second_stage.stage_id
    session.commit()
    assert batch.stage == second_stage
    assert batch in second_stage.batches
    assert batch not in stage.batches


def test_batches_per_stage_can_be_counted(
    session, stage, second_stage, batch, batch_kwargs
):
    session.add(MineralBatch(**{**batch_kwargs, "batch_code": "B-002"}))
    session.add(
        MineralBatch(
            **{
                **batch_kwargs,
                "batch_code": "B-003",
                "stage_id": second_stage.stage_id,
            }
        )
    )
    session.commit()
    counts = dict(
        session.query(MineralBatch.stage_id, func.count())
        .group_by(MineralBatch.stage_id)
        .all()
    )
    assert counts == {stage.stage_id: 2, second_stage.stage_id: 1}


def test_deleting_a_batch_keeps_its_stage(session, stage, batch):
    session.delete(batch)
    session.commit()
    assert session.get(ProcessingStage, stage.stage_id) is not None
    assert stage.batches == []


def test_stage_lists_its_history_records(stage, history):
    assert history in stage.history_records
    assert history.stage == stage


def test_stage_lists_its_value_calculations(stage, calculation):
    assert calculation in stage.value_calculations
    assert calculation.stage == stage


def test_stage_lists_the_scenarios_assuming_it(second_stage, scenario):
    assert scenario in second_stage.scenarios
    assert scenario.assumed_stage == second_stage


def test_stage_without_dependents_has_empty_lists(second_stage, batch):
    assert second_stage.batches == []
    assert second_stage.history_records == []
    assert second_stage.value_calculations == []
    assert second_stage.scenarios == []


def test_stage_used_by_a_scenario_cannot_be_deleted(session, second_stage, scenario):
    """second_stage is referenced only by the scenario, so this isolates that FK."""
    with pytest.raises(IntegrityError):
        session.execute(
            delete(ProcessingStage.__table__).where(
                ProcessingStage.__table__.c.stage_id == second_stage.stage_id
            )
        )
    session.rollback()


def test_stage_delete_does_not_remove_other_stages(session, stage, second_stage):
    session.delete(second_stage)
    session.commit()
    assert session.query(ProcessingStage).count() == 1
    assert session.get(ProcessingStage, stage.stage_id) is not None


# =============================================================================
# Router tests for routers/mineral_batch.py
# The service is replaced with a fake, so these cover only the router:
# URLs, parameters, validation, status codes, and how arguments reach the service.
# =============================================================================

AUTH = {"Authorization": "Bearer test-token"}
PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-image"


class FakeService:
    """Stands in for MineralBatchService and records every call."""

    calls: list = []
    batch = None
    error: HTTPException | None = None

    def __init__(self, db):
        self.db = db

    def _run(self, name, *args, **kwargs):
        FakeService.calls.append((name, args, kwargs))
        if FakeService.error is not None:
            raise FakeService.error
        return FakeService.batch

    def create_batch(self, payload, user):
        return self._run("create_batch", payload, user)

    def get_all_batches(self, user, sort="desc"):
        result = self._run("get_all_batches", user, sort=sort)
        return [result]

    def get_batch_by_code(self, batch_code, user):
        return self._run("get_batch_by_code", batch_code, user)

    def generate_qr_code(self, batch_code, user):
        self._run("generate_qr_code", batch_code, user)
        return PNG_BYTES

    def save_assay(self, batch_id, user, file_data, filename):
        return self._run("save_assay", batch_id, user, file_data, filename)


@pytest.fixture
def router_client(monkeypatch, batch):
    FakeService.calls = []
    FakeService.batch = batch
    FakeService.error = None
    monkeypatch.setattr(router_module, "MineralBatchService", FakeService)
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: object()
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def last_call():
    return FakeService.calls[-1]


def valid_payload(batch):
    return {
        "mineral_type": "COPPER",
        "source_type": batch.source_type,
        "quantity_tonnes": float(batch.quantity_tonnes),
        "grade": float(batch.grade),
        "recovery": float(batch.recovery),
        "stage_id": batch.stage_id,
    }


# --- authentication -------------------------------------------------------


@pytest.mark.parametrize(
    "method, url",
    [
        ("get", "/mineral-batches"),
        ("get", "/mineral-batches/search?batch_code=CU-1"),
        ("get", "/mineral-batches/code/CU-1"),
        ("get", "/mineral-batches/code/CU-1/qr-code"),
    ],
)
def test_endpoints_reject_requests_without_a_token(router_client, method, url):
    # router_client fakes a logged-in user; remove that so the real auth runs.
    app.dependency_overrides.pop(get_current_user, None)
    response = getattr(router_client, method)(url)
    assert response.status_code in (401, 403)
    assert FakeService.calls == []


def test_service_errors_are_returned_to_the_client(router_client):
    FakeService.error = HTTPException(status_code=403, detail="Unauthorized access.")
    response = router_client.get("/mineral-batches", headers=AUTH)
    assert response.status_code == 403
    assert response.json()["detail"] == "Unauthorized access."


# --- POST /mineral-batches ------------------------------------------------


def test_register_batch_with_empty_body_is_rejected(router_client):
    response = router_client.post("/mineral-batches", json={}, headers=AUTH)
    assert response.status_code == 422
    assert FakeService.calls == []


def test_register_batch_service_error_is_returned(router_client, batch):
    FakeService.error = HTTPException(status_code=422, detail="Only COPPER.")
    response = router_client.post(
        "/mineral-batches", json=valid_payload(batch), headers=AUTH
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Only COPPER."


# --- GET /mineral-batches -------------------------------------------------


def test_list_batches_returns_a_list(router_client, batch):
    response = router_client.get("/mineral-batches", headers=AUTH)
    assert response.status_code == 200
    assert [item["batch_code"] for item in response.json()] == [batch.batch_code]


def test_list_batches_sorts_descending_by_default(router_client):
    router_client.get("/mineral-batches", headers=AUTH)
    _, _, kwargs = last_call()
    assert kwargs["sort"] == "desc"


# --- GET /mineral-batches/search ------------------------------------------


def test_search_returns_a_single_item_list(router_client, batch):
    response = router_client.get(
        f"/mineral-batches/search?batch_code={batch.batch_code}", headers=AUTH
    )
    assert response.status_code == 200
    assert [item["batch_code"] for item in response.json()] == [batch.batch_code]


def test_search_strips_whitespace_from_the_code(router_client):
    router_client.get("/mineral-batches/search?batch_code=%20CU-1%20", headers=AUTH)
    name, args, _ = last_call()
    assert name == "get_batch_by_code"
    assert args[0] == "CU-1"


def test_search_requires_a_batch_code(router_client):
    response = router_client.get("/mineral-batches/search", headers=AUTH)
    assert response.status_code == 422


def test_search_rejects_an_empty_batch_code(router_client):
    response = router_client.get("/mineral-batches/search?batch_code=", headers=AUTH)
    assert response.status_code == 422


def test_search_unknown_code_returns_404(router_client):
    FakeService.error = HTTPException(
        status_code=404, detail="Mineral batch not found."
    )
    response = router_client.get(
        "/mineral-batches/search?batch_code=NOPE", headers=AUTH
    )
    assert response.status_code == 404


# --- GET /mineral-batches/code/{batch_code} -------------------------------


def test_get_batch_by_code_returns_the_batch(router_client, batch):
    response = router_client.get(
        f"/mineral-batches/code/{batch.batch_code}", headers=AUTH
    )
    assert response.status_code == 200
    assert response.json()["batch_code"] == batch.batch_code


def test_get_batch_by_code_passes_the_code_to_the_service(router_client):
    router_client.get("/mineral-batches/code/CU-ABC123", headers=AUTH)
    name, args, _ = last_call()
    assert name == "get_batch_by_code"
    assert args[0] == "CU-ABC123"


def test_get_batch_by_code_unknown_code_returns_404(router_client):
    FakeService.error = HTTPException(
        status_code=404, detail="Mineral batch not found."
    )
    response = router_client.get("/mineral-batches/code/NOPE", headers=AUTH)
    assert response.status_code == 404
    assert response.json()["detail"] == "Mineral batch not found."


# --- GET /mineral-batches/code/{batch_code}/qr-code -----------------------


def test_qr_code_returns_a_png_image(router_client):
    response = router_client.get(
        "/mineral-batches/code/CU-ABC123/qr-code", headers=AUTH
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == PNG_BYTES


def test_qr_code_filename_uses_the_batch_code(router_client):
    response = router_client.get(
        "/mineral-batches/code/CU-ABC123/qr-code", headers=AUTH
    )
    assert 'filename="CU-ABC123-qr.png"' in response.headers["content-disposition"]


def test_qr_code_unknown_code_returns_404(router_client):
    FakeService.error = HTTPException(
        status_code=404, detail="Mineral batch not found."
    )
    response = router_client.get("/mineral-batches/code/NOPE/qr-code", headers=AUTH)
    assert response.status_code == 404


# --- PUT /mineral-batches/{batch_id}/upload-assay -------------------------


def test_upload_assay_returns_the_updated_batch(router_client, batch):
    response = router_client.put(
        f"/mineral-batches/{uuid.uuid4()}/upload-assay",
        files={"file": ("assay.pdf", b"assay-bytes", "application/pdf")},
        headers=AUTH,
    )
    assert response.status_code == 200
    assert response.json()["batch_code"] == batch.batch_code


def test_upload_assay_sends_file_contents_and_name_to_the_service(router_client):
    batch_id = uuid.uuid4()
    router_client.put(
        f"/mineral-batches/{batch_id}/upload-assay",
        files={"file": ("assay.pdf", b"assay-bytes", "application/pdf")},
        headers=AUTH,
    )
    name, args, _ = last_call()
    assert name == "save_assay"
    assert args[0] == batch_id
    assert args[2] == b"assay-bytes"
    assert args[3] == "assay.pdf"


def test_upload_assay_requires_a_file(router_client):
    response = router_client.put(
        f"/mineral-batches/{uuid.uuid4()}/upload-assay", headers=AUTH
    )
    assert response.status_code == 422
    assert FakeService.calls == []


def test_upload_assay_rejects_an_invalid_batch_id(router_client):
    response = router_client.put(
        "/mineral-batches/not-a-uuid/upload-assay",
        files={"file": ("assay.pdf", b"x", "application/pdf")},
        headers=AUTH,
    )
    assert response.status_code == 422
    assert FakeService.calls == []


def test_upload_assay_unknown_batch_returns_404(router_client):
    FakeService.error = HTTPException(
        status_code=404, detail="Mineral batch not found."
    )
    response = router_client.put(
        f"/mineral-batches/{uuid.uuid4()}/upload-assay",
        files={"file": ("assay.pdf", b"x", "application/pdf")},
        headers=AUTH,
    )
    assert response.status_code == 404
