import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.routers.workouts import router


@pytest.fixture(name="session")
def session_fixture():
    """Override the conftest session fixture with StaticPool so that the
    in-memory SQLite database is shared across all connections (including
    those made from the anyio thread pool used by the TestClient)."""
    import backend.models as _models  # noqa: F401 — register all tables

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    from fastapi import FastAPI

    from backend.database import get_session

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/workouts")
    test_app.dependency_overrides[get_session] = lambda: session
    return TestClient(test_app)


def _create_lift(session: Session, name: str) -> int:
    from backend.models import Lift

    lift = Lift(name=name)
    session.add(lift)
    session.commit()
    session.refresh(lift)
    return lift.id


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


def test_list_empty(client: TestClient):
    response = client.get("/api/workouts/")
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_create(client: TestClient):
    response = client.post("/api/workouts/")
    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["id"], int)
    assert "date" in body
    assert body["subtitle"] == ""
    assert body["workout_lifts"] == []


def test_list_after_create(client: TestClient):
    client.post("/api/workouts/")
    response = client.get("/api/workouts/")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["lift_names"] == []


# ---------------------------------------------------------------------------
# Get detail
# ---------------------------------------------------------------------------


def test_get_detail(client: TestClient):
    create_resp = client.post("/api/workouts/")
    workout_id = create_resp.json()["id"]
    response = client.get(f"/api/workouts/{workout_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == workout_id
    assert body["workout_lifts"] == []


def test_get_nonexistent(client: TestClient):
    response = client.get("/api/workouts/99999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Patch subtitle
# ---------------------------------------------------------------------------


def test_patch_subtitle(client: TestClient):
    create_resp = client.post("/api/workouts/")
    workout_id = create_resp.json()["id"]
    response = client.patch(f"/api/workouts/{workout_id}", json={"subtitle": "Push day"})
    assert response.status_code == 200
    body = response.json()
    assert body["subtitle"] == "Push day"
    assert body["id"] == workout_id


def test_patch_nonexistent(client: TestClient):
    response = client.patch("/api/workouts/99999", json={"subtitle": "Ghost"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Add lift
# ---------------------------------------------------------------------------


def test_add_lift(client: TestClient, session: Session):
    lift_id = _create_lift(session, "Bench Press")
    create_resp = client.post("/api/workouts/")
    workout_id = create_resp.json()["id"]

    add_resp = client.post(
        f"/api/workouts/{workout_id}/lifts",
        json={"lift_id": lift_id, "display_order": 0},
    )
    assert add_resp.status_code == 201
    body = add_resp.json()
    assert body["lift_id"] == lift_id
    assert body["lift_name"] == "Bench Press"
    assert body["sets"] == []

    # Confirm lift appears in detail
    detail_resp = client.get(f"/api/workouts/{workout_id}")
    assert detail_resp.status_code == 200
    workout_lifts = detail_resp.json()["workout_lifts"]
    assert len(workout_lifts) == 1
    assert workout_lifts[0]["lift_name"] == "Bench Press"


def test_add_lift_invalid_lift_id(client: TestClient):
    create_resp = client.post("/api/workouts/")
    workout_id = create_resp.json()["id"]
    response = client.post(
        f"/api/workouts/{workout_id}/lifts",
        json={"lift_id": 99999},
    )
    assert response.status_code == 404


def test_add_lift_invalid_workout_id(client: TestClient, session: Session):
    lift_id = _create_lift(session, "Squat")
    response = client.post(
        "/api/workouts/99999/lifts",
        json={"lift_id": lift_id},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Delete workout lift
# ---------------------------------------------------------------------------


def test_delete_workout_lift(client: TestClient, session: Session):
    lift_id = _create_lift(session, "Deadlift")
    create_resp = client.post("/api/workouts/")
    workout_id = create_resp.json()["id"]

    add_resp = client.post(
        f"/api/workouts/{workout_id}/lifts",
        json={"lift_id": lift_id},
    )
    wl_id = add_resp.json()["id"]

    del_resp = client.delete(f"/api/workouts/{workout_id}/lifts/{wl_id}")
    assert del_resp.status_code == 204

    detail_resp = client.get(f"/api/workouts/{workout_id}")
    assert detail_resp.json()["workout_lifts"] == []


# ---------------------------------------------------------------------------
# Delete workout
# ---------------------------------------------------------------------------


def test_delete_workout(client: TestClient):
    create_resp = client.post("/api/workouts/")
    workout_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/workouts/{workout_id}")
    assert del_resp.status_code == 204

    get_resp = client.get(f"/api/workouts/{workout_id}")
    assert get_resp.status_code == 404


def test_delete_workout_cascades(client: TestClient, session: Session):
    """Deleting a workout removes its WorkoutLifts and WorkoutSets (no orphans)."""
    from sqlmodel import select

    from backend.models import WorkoutSet

    lift_id = _create_lift(session, "Overhead Press")
    create_resp = client.post("/api/workouts/")
    workout_id = create_resp.json()["id"]

    add_resp = client.post(
        f"/api/workouts/{workout_id}/lifts",
        json={"lift_id": lift_id},
    )
    wl_id = add_resp.json()["id"]

    # Add a WorkoutSet directly via the session
    ws = WorkoutSet(workout_lift_id=wl_id, set_number=1, reps=5, weight=60.0)
    session.add(ws)
    session.commit()

    # Delete the workout via the API
    del_resp = client.delete(f"/api/workouts/{workout_id}")
    assert del_resp.status_code == 204

    # No orphan WorkoutSets should remain
    remaining_sets = session.exec(
        select(WorkoutSet).where(WorkoutSet.workout_lift_id == wl_id)
    ).all()
    assert remaining_sets == []


def test_delete_nonexistent(client: TestClient):
    response = client.delete("/api/workouts/99999")
    assert response.status_code == 404
