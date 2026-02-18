import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.routers.muscle_groups import router


@pytest.fixture(name="client")
def client_fixture(session: Session):
    from fastapi import FastAPI

    from backend.database import get_session

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/muscle-groups")
    test_app.dependency_overrides[get_session] = lambda: session
    return TestClient(test_app)


def test_list_empty(client: TestClient):
    response = client.get("/api/muscle-groups/")
    assert response.status_code == 200
    assert response.json() == []


def test_create(client: TestClient):
    response = client.post("/api/muscle-groups/", json={"id": 0, "name": "Chest"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Chest"
    assert isinstance(body["id"], int)


def test_create_duplicate_name(client: TestClient):
    client.post("/api/muscle-groups/", json={"id": 0, "name": "Back"})
    response = client.post("/api/muscle-groups/", json={"id": 0, "name": "Back"})
    assert response.status_code == 400
    assert response.json() == {"detail": "Name already exists"}


def test_list_after_create(client: TestClient):
    client.post("/api/muscle-groups/", json={"id": 0, "name": "Legs"})
    response = client.get("/api/muscle-groups/")
    assert response.status_code == 200
    names = [mg["name"] for mg in response.json()]
    assert "Legs" in names


def test_rename(client: TestClient):
    create_response = client.post("/api/muscle-groups/", json={"id": 0, "name": "Shoulders"})
    muscle_group_id = create_response.json()["id"]
    response = client.patch(
        f"/api/muscle-groups/{muscle_group_id}", json={"id": muscle_group_id, "name": "Delts"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Delts"
    assert body["id"] == muscle_group_id


def test_rename_nonexistent(client: TestClient):
    response = client.patch("/api/muscle-groups/99999", json={"id": 99999, "name": "Ghost"})
    assert response.status_code == 404


def test_delete(client: TestClient):
    create_response = client.post("/api/muscle-groups/", json={"id": 0, "name": "Triceps"})
    muscle_group_id = create_response.json()["id"]
    response = client.delete(f"/api/muscle-groups/{muscle_group_id}")
    assert response.status_code == 204


def test_delete_nonexistent(client: TestClient):
    response = client.delete("/api/muscle-groups/99999")
    assert response.status_code == 404
