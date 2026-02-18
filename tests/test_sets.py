from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.models import Lift, Workout, WorkoutLift
from backend.routers.sets import router


@pytest.fixture(name="client")
def client_fixture(session: Session):
    from fastapi import FastAPI

    from backend.database import get_session

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api")
    test_app.dependency_overrides[get_session] = lambda: session
    return TestClient(test_app)


@pytest.fixture(name="static_session")
def static_session_fixture():
    """A session backed by a StaticPool engine so it works across TestClient threads."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="static_client")
def static_client_fixture(static_session: Session):
    from fastapi import FastAPI

    from backend.database import get_session

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api")
    test_app.dependency_overrides[get_session] = lambda: static_session
    return TestClient(test_app)


@pytest.fixture(name="workout_lift_id")
def workout_lift_id_fixture(static_session: Session) -> int:
    lift = Lift(name="Bench Press")
    static_session.add(lift)
    static_session.commit()
    static_session.refresh(lift)

    workout = Workout(date=date(2026, 2, 18))
    static_session.add(workout)
    static_session.commit()
    static_session.refresh(workout)

    workout_lift = WorkoutLift(workout_id=workout.id, lift_id=lift.id, display_order=0)
    static_session.add(workout_lift)
    static_session.commit()
    static_session.refresh(workout_lift)

    return workout_lift.id


def test_add_set_to_valid_workout_lift(static_client: TestClient, workout_lift_id: int):
    response = static_client.post(
        f"/api/workout-lifts/{workout_lift_id}/sets",
        json={"reps": 10, "weight": 135.0},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["set_number"] == 1
    assert body["reps"] == 10
    assert body["weight"] == 135.0
    assert isinstance(body["id"], int)


def test_add_second_set_auto_increments_set_number(static_client: TestClient, workout_lift_id: int):
    static_client.post(
        f"/api/workout-lifts/{workout_lift_id}/sets",
        json={"reps": 10, "weight": 135.0},
    )
    response = static_client.post(
        f"/api/workout-lifts/{workout_lift_id}/sets",
        json={"reps": 8, "weight": 145.0},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["set_number"] == 2


def test_add_set_to_nonexistent_workout_lift(static_client: TestClient):
    response = static_client.post(
        "/api/workout-lifts/99999/sets",
        json={"reps": 5, "weight": 100.0},
    )
    assert response.status_code == 404


def test_patch_set_updates_reps_and_weight(static_client: TestClient, workout_lift_id: int):
    create_response = static_client.post(
        f"/api/workout-lifts/{workout_lift_id}/sets",
        json={"reps": 10, "weight": 135.0},
    )
    set_id = create_response.json()["id"]

    response = static_client.patch(
        f"/api/sets/{set_id}",
        json={"reps": 12, "weight": 140.0},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reps"] == 12
    assert body["weight"] == 140.0


def test_patch_nonexistent_set(static_client: TestClient):
    response = static_client.patch(
        "/api/sets/99999",
        json={"reps": 5, "weight": 100.0},
    )
    assert response.status_code == 404


def test_delete_set(static_client: TestClient, workout_lift_id: int):
    create_response = static_client.post(
        f"/api/workout-lifts/{workout_lift_id}/sets",
        json={"reps": 10, "weight": 135.0},
    )
    set_id = create_response.json()["id"]

    response = static_client.delete(f"/api/sets/{set_id}")
    assert response.status_code == 204


def test_delete_nonexistent_set(static_client: TestClient):
    response = static_client.delete("/api/sets/99999")
    assert response.status_code == 404
