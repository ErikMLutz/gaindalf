import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.database import get_session
from backend.models import MuscleGroup
from backend.routers.lifts import router


@pytest.fixture(name="client")
def client_fixture(session: Session):
    from fastapi import FastAPI

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/lifts")
    test_app.dependency_overrides[get_session] = lambda: session
    return TestClient(test_app)


def make_muscle_groups(session: Session, *names: str) -> list[int]:
    """Create MuscleGroup records and return their IDs."""
    ids = []
    for name in names:
        mg = MuscleGroup(name=name)
        session.add(mg)
        session.commit()
        session.refresh(mg)
        ids.append(mg.id)
    return ids


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------


def test_list_lifts_empty(client: TestClient):
    response = client.get("/api/lifts/")
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# POST /
# ---------------------------------------------------------------------------


def test_create_lift_valid(session: Session, client: TestClient):
    chest_id, triceps_id = make_muscle_groups(session, "Chest", "Triceps")

    response = client.post(
        "/api/lifts/",
        json={"name": "Bench Press", "muscle_group_ids": [chest_id, triceps_id]},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Bench Press"
    assert set(data["muscle_group_ids"]) == {chest_id, triceps_id}
    assert isinstance(data["id"], int)


def test_create_lift_invalid_muscle_group(client: TestClient):
    response = client.post(
        "/api/lifts/",
        json={"name": "Squat", "muscle_group_ids": [999]},
    )
    assert response.status_code == 400


def test_create_lift_duplicate_name(session: Session, client: TestClient):
    make_muscle_groups(session, "Legs")
    client.post("/api/lifts/", json={"name": "Squat", "muscle_group_ids": []})

    response = client.post("/api/lifts/", json={"name": "Squat", "muscle_group_ids": []})
    assert response.status_code == 400
    assert response.json()["detail"] == "Name already exists"


# ---------------------------------------------------------------------------
# GET / — after data exists
# ---------------------------------------------------------------------------


def test_list_lifts_with_muscle_groups(session: Session, client: TestClient):
    (chest_id,) = make_muscle_groups(session, "Chest")
    client.post(
        "/api/lifts/",
        json={"name": "Bench Press", "muscle_group_ids": [chest_id]},
    )

    response = client.get("/api/lifts/")
    assert response.status_code == 200
    lifts = response.json()
    assert len(lifts) == 1
    assert lifts[0]["name"] == "Bench Press"
    assert lifts[0]["muscle_group_ids"] == [chest_id]


# ---------------------------------------------------------------------------
# PATCH /{id}
# ---------------------------------------------------------------------------


def test_patch_lift_name(session: Session, client: TestClient):
    (legs_id,) = make_muscle_groups(session, "Legs")
    create_resp = client.post(
        "/api/lifts/",
        json={"name": "Squat", "muscle_group_ids": [legs_id]},
    )
    lift_id = create_resp.json()["id"]

    response = client.patch(f"/api/lifts/{lift_id}", json={"name": "Front Squat"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Front Squat"
    assert data["muscle_group_ids"] == [legs_id]


def test_patch_lift_muscle_group_ids(session: Session, client: TestClient):
    chest_id, back_id = make_muscle_groups(session, "Chest", "Back")
    create_resp = client.post(
        "/api/lifts/",
        json={"name": "Bench Press", "muscle_group_ids": [chest_id]},
    )
    lift_id = create_resp.json()["id"]

    response = client.patch(f"/api/lifts/{lift_id}", json={"muscle_group_ids": [back_id]})
    assert response.status_code == 200
    data = response.json()
    # old muscle group gone, new one present
    assert data["muscle_group_ids"] == [back_id]
    assert chest_id not in data["muscle_group_ids"]


def test_patch_lift_not_found(client: TestClient):
    response = client.patch("/api/lifts/9999", json={"name": "Ghost"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /{id}
# ---------------------------------------------------------------------------


def test_delete_lift(session: Session, client: TestClient):
    client.post("/api/lifts/", json={"name": "Curl", "muscle_group_ids": []})

    list_resp = client.get("/api/lifts/")
    lift_id = list_resp.json()[0]["id"]

    response = client.delete(f"/api/lifts/{lift_id}")
    assert response.status_code == 204

    list_after = client.get("/api/lifts/")
    assert list_after.json() == []


def test_delete_lift_not_found(client: TestClient):
    response = client.delete("/api/lifts/9999")
    assert response.status_code == 404
