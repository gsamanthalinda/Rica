import pytest
from sqlalchemy.orm import sessionmaker

from models import ProcessingStage

URL = "/processing-stages"


def create(client, name="Mining", order=1):
    return client.post(URL, json={"stage_name": name, "stage_order": order})


def test_create_returns_201_and_generated_id(client):
    response = create(client)

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "stage_id": body["stage_id"],
        "stage_name": "Mining",
        "stage_order": 1,
    }
    assert isinstance(body["stage_id"], int)


def test_create_is_persisted(client, engine):
    stage_id = create(client).json()["stage_id"]

    with sessionmaker(bind=engine)() as fresh:
        saved = fresh.get(ProcessingStage, stage_id)
        assert (saved.stage_name, saved.stage_order) == ("Mining", 1)


def test_create_strips_whitespace_from_name(client):
    assert create(client, name="  Smelting  ").json()["stage_name"] == "Smelting"


@pytest.mark.parametrize(
    "payload",
    [
        {"stage_order": 1},
        {"stage_name": "Mining"},
        {},
    ],
)
def test_create_rejects_missing_fields(client, payload):
    assert client.post(URL, json=payload).status_code == 422


@pytest.mark.parametrize("order", [0, -1, 32768])
def test_create_rejects_out_of_range_order(client, order):
    response = create(client, order=order)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "stage_order"]


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_create_rejects_invalid_name(client, name):
    assert create(client, name=name).status_code == 422


def test_create_rejects_client_supplied_stage_id(client):
    response = client.post(
        URL, json={"stage_id": 7, "stage_name": "Mining", "stage_order": 1}
    )
    assert response.status_code == 422


def test_create_rejects_duplicate_name(client):
    create(client, name="Mining", order=1)

    response = create(client, name="Mining", order=2)

    assert response.status_code == 409
    assert "Mining" in response.json()["detail"]


def test_create_rejects_duplicate_order(client):
    create(client, name="Mining", order=1)

    response = create(client, name="Crushing", order=1)

    assert response.status_code == 409
    assert "order 1" in response.json()["detail"]


def test_list_is_ordered_by_stage_order(client):
    create(client, "Smelting", 3)
    create(client, "Mining", 1)
    create(client, "Concentrating", 2)

    response = client.get(URL)

    assert response.status_code == 200
    assert [s["stage_name"] for s in response.json()] == [
        "Mining",
        "Concentrating",
        "Smelting",
    ]


def test_list_is_empty_when_no_stages(client):
    assert client.get(URL).json() == []


def test_get_existing_stage(client):
    stage_id = create(client).json()["stage_id"]

    response = client.get(f"{URL}/{stage_id}")

    assert response.status_code == 200
    assert response.json()["stage_name"] == "Mining"


def test_get_missing_stage_returns_404(client):
    response = client.get(f"{URL}/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Processing stage 999 not found"}


@pytest.mark.parametrize("bad_id", ["abc", "0", "40000"])
def test_get_rejects_invalid_id(client, bad_id):
    assert client.get(f"{URL}/{bad_id}").status_code == 422


def test_patch_updates_only_given_fields(client):
    stage_id = create(client).json()["stage_id"]

    response = client.patch(f"{URL}/{stage_id}", json={"stage_order": 5})

    assert response.status_code == 200
    assert response.json() == {
        "stage_id": stage_id,
        "stage_name": "Mining",
        "stage_order": 5,
    }


def test_patch_can_keep_its_own_name_and_order(client):
    stage_id = create(client).json()["stage_id"]

    response = client.patch(
        f"{URL}/{stage_id}", json={"stage_name": "Mining", "stage_order": 1}
    )

    assert response.status_code == 200


def test_patch_rejects_name_used_by_another_stage(client):
    create(client, "Mining", 1)
    other = create(client, "Crushing", 2).json()["stage_id"]

    response = client.patch(f"{URL}/{other}", json={"stage_name": "Mining"})

    assert response.status_code == 409


def test_patch_rejects_order_used_by_another_stage(client):
    create(client, "Mining", 1)
    other = create(client, "Crushing", 2).json()["stage_id"]

    response = client.patch(f"{URL}/{other}", json={"stage_order": 1})

    assert response.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"stage_name": None},
        {"stage_order": None},
        {"stage_order": 0},
        {"stage_id": 3},
    ],
)
def test_patch_rejects_invalid_payload(client, payload):
    stage_id = create(client).json()["stage_id"]

    assert client.patch(f"{URL}/{stage_id}", json=payload).status_code == 422


def test_patch_missing_stage_returns_404(client):
    assert client.patch(f"{URL}/999", json={"stage_order": 2}).status_code == 404


def test_delete_unreferenced_stage(client):
    stage_id = create(client).json()["stage_id"]

    response = client.delete(f"{URL}/{stage_id}")

    assert response.status_code == 204
    assert client.get(f"{URL}/{stage_id}").status_code == 404


def test_delete_missing_stage_returns_404(client):
    assert client.delete(f"{URL}/999").status_code == 404


def test_delete_stage_used_by_a_batch_is_rejected(client, session, batch, stage):
    response = client.delete(f"{URL}/{stage.stage_id}")

    assert response.status_code == 409
    assert "in use" in response.json()["detail"]
    session.expire_all()
    assert session.get(ProcessingStage, stage.stage_id) is not None


def test_delete_stage_used_only_by_a_scenario_is_rejected(
    client, session, scenario, second_stage
):
    response = client.delete(f"{URL}/{second_stage.stage_id}")

    assert response.status_code == 409
    session.expire_all()
    assert session.get(ProcessingStage, second_stage.stage_id) is not None


def test_failed_delete_leaves_related_records_untouched(client, session, batch, stage):
    client.delete(f"{URL}/{stage.stage_id}")

    session.expire_all()
    assert session.get(type(batch), batch.batch_id).stage_id == stage.stage_id


def test_routes_are_registered_in_openapi(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert set(paths[URL]) == {"get", "post"}
    assert set(paths[URL + "/{stage_id}"]) == {"get", "patch", "delete"}


def test_health_still_works(client):
    assert client.get("/health").json() == {"status": "ok"}
