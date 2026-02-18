import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.routers.settings import router


@pytest.fixture(name="client")
def client_fixture(session: Session):
    from fastapi import FastAPI

    from backend.database import get_session

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/settings")
    test_app.dependency_overrides[get_session] = lambda: session
    return TestClient(test_app)


def _add_muscle_group(session: Session, name: str) -> int:
    from backend.models import MuscleGroup

    mg = MuscleGroup(name=name)
    session.add(mg)
    session.commit()
    session.refresh(mg)
    return mg.id


def test_list_empty(client: TestClient):
    response = client.get("/api/settings/conflicts")
    assert response.status_code == 200
    assert response.json() == []


def test_create_conflict(client: TestClient, session: Session):
    chest_id = _add_muscle_group(session, "Chest")
    back_id = _add_muscle_group(session, "Back")

    response = client.post(
        "/api/settings/conflicts",
        json={"muscle_group_a_id": chest_id, "muscle_group_b_id": back_id},
    )
    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["id"], int)
    assert body["muscle_group_a_id"] == chest_id
    assert body["muscle_group_a_name"] == "Chest"
    assert body["muscle_group_b_id"] == back_id
    assert body["muscle_group_b_name"] == "Back"


def test_create_conflict_nonexistent_muscle_group_a(client: TestClient, session: Session):
    back_id = _add_muscle_group(session, "Back")

    response = client.post(
        "/api/settings/conflicts",
        json={"muscle_group_a_id": 99999, "muscle_group_b_id": back_id},
    )
    assert response.status_code == 404


def test_create_conflict_nonexistent_muscle_group_b(client: TestClient, session: Session):
    chest_id = _add_muscle_group(session, "Chest")

    response = client.post(
        "/api/settings/conflicts",
        json={"muscle_group_a_id": chest_id, "muscle_group_b_id": 99999},
    )
    assert response.status_code == 404


def test_create_conflict_same_id(client: TestClient, session: Session):
    chest_id = _add_muscle_group(session, "Chest")

    response = client.post(
        "/api/settings/conflicts",
        json={"muscle_group_a_id": chest_id, "muscle_group_b_id": chest_id},
    )
    assert response.status_code == 400


def test_create_duplicate_conflict_same_direction(client: TestClient, session: Session):
    chest_id = _add_muscle_group(session, "Chest")
    back_id = _add_muscle_group(session, "Back")

    client.post(
        "/api/settings/conflicts",
        json={"muscle_group_a_id": chest_id, "muscle_group_b_id": back_id},
    )
    response = client.post(
        "/api/settings/conflicts",
        json={"muscle_group_a_id": chest_id, "muscle_group_b_id": back_id},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Conflict already exists"


def test_create_duplicate_conflict_reversed_direction(client: TestClient, session: Session):
    chest_id = _add_muscle_group(session, "Chest")
    back_id = _add_muscle_group(session, "Back")

    client.post(
        "/api/settings/conflicts",
        json={"muscle_group_a_id": chest_id, "muscle_group_b_id": back_id},
    )
    response = client.post(
        "/api/settings/conflicts",
        json={"muscle_group_a_id": back_id, "muscle_group_b_id": chest_id},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Conflict already exists"


def test_list_after_create(client: TestClient, session: Session):
    chest_id = _add_muscle_group(session, "Chest")
    shoulders_id = _add_muscle_group(session, "Shoulders")

    client.post(
        "/api/settings/conflicts",
        json={"muscle_group_a_id": chest_id, "muscle_group_b_id": shoulders_id},
    )

    response = client.get("/api/settings/conflicts")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["muscle_group_a_name"] == "Chest"
    assert items[0]["muscle_group_b_name"] == "Shoulders"


def test_delete_conflict(client: TestClient, session: Session):
    chest_id = _add_muscle_group(session, "Chest")
    back_id = _add_muscle_group(session, "Back")

    create_response = client.post(
        "/api/settings/conflicts",
        json={"muscle_group_a_id": chest_id, "muscle_group_b_id": back_id},
    )
    conflict_id = create_response.json()["id"]

    response = client.delete(f"/api/settings/conflicts/{conflict_id}")
    assert response.status_code == 204


def test_delete_nonexistent_conflict(client: TestClient):
    response = client.delete("/api/settings/conflicts/99999")
    assert response.status_code == 404
