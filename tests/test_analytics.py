from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.database import get_session
from backend.models import Lift, Workout, WorkoutLift, WorkoutSet
from backend.routers.analytics import router


@pytest.fixture(name="session")
def session_fixture():
    import backend.models as _models  # noqa: F401

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
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/analytics")
    test_app.dependency_overrides[get_session] = lambda: session
    return TestClient(test_app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lift(session: Session, name: str) -> int:
    lift = Lift(name=name)
    session.add(lift)
    session.commit()
    session.refresh(lift)
    return lift.id


def _make_workout(session: Session, d: date) -> int:
    workout = Workout(date=d)
    session.add(workout)
    session.commit()
    session.refresh(workout)
    return workout.id


def _add_lift_to_workout(session: Session, workout_id: int, lift_id: int) -> int:
    wl = WorkoutLift(workout_id=workout_id, lift_id=lift_id)
    session.add(wl)
    session.commit()
    session.refresh(wl)
    return wl.id


def _add_set(session: Session, wl_id: int, reps: int, weight: float):
    ws = WorkoutSet(workout_lift_id=wl_id, set_number=1, reps=reps, weight=weight)
    session.add(ws)
    session.commit()


# ---------------------------------------------------------------------------
# GET /api/analytics/progress
# ---------------------------------------------------------------------------


def test_progress_empty(client: TestClient):
    response = client.get("/api/analytics/progress")
    assert response.status_code == 200
    assert response.json() == []


def test_progress_first_workout_indexes_one(client: TestClient, session: Session):
    lift_id = _make_lift(session, "Bench Press")
    w_id = _make_workout(session, date(2025, 1, 1))
    wl_id = _add_lift_to_workout(session, w_id, lift_id)
    _add_set(session, wl_id, reps=5, weight=100.0)

    response = client.get("/api/analytics/progress")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["strength_index"] == pytest.approx(1.0)
    assert data[0]["endurance_index"] == pytest.approx(1.0)


def test_progress_ordered_by_date(client: TestClient, session: Session):
    lift_id = _make_lift(session, "Squat")
    w1 = _make_workout(session, date(2025, 1, 1))
    w2 = _make_workout(session, date(2025, 3, 1))
    # Insert in reverse order to confirm sorting
    wl2 = _add_lift_to_workout(session, w2, lift_id)
    wl1 = _add_lift_to_workout(session, w1, lift_id)
    _add_set(session, wl1, 5, 100.0)
    _add_set(session, wl2, 5, 120.0)

    data = client.get("/api/analytics/progress").json()
    assert len(data) == 2
    assert data[0]["date"] < data[1]["date"]
    assert data[1]["strength_index"] == pytest.approx(1.2)


def test_progress_workout_with_no_sets_returns_none_indexes(client: TestClient, session: Session):
    lift_id = _make_lift(session, "Pull-up")
    w_id = _make_workout(session, date(2025, 1, 1))
    _add_lift_to_workout(session, w_id, lift_id)  # no sets added

    data = client.get("/api/analytics/progress").json()
    assert data[0]["strength_index"] is None
    assert data[0]["endurance_index"] is None


# ---------------------------------------------------------------------------
# GET /api/analytics/lifts/{lift_id}
# ---------------------------------------------------------------------------


def test_lift_history_unknown_lift(client: TestClient):
    response = client.get("/api/analytics/lifts/99999")
    assert response.status_code == 404


def test_lift_history_known_lift_no_workouts(client: TestClient, session: Session):
    lift_id = _make_lift(session, "Dumbbell Curl")
    response = client.get(f"/api/analytics/lifts/{lift_id}")
    assert response.status_code == 200
    assert response.json() == []


def test_lift_history_returns_only_that_lift(client: TestClient, session: Session):
    lift_a = _make_lift(session, "Deadlift")
    lift_b = _make_lift(session, "Row")

    w1 = _make_workout(session, date(2025, 1, 1))
    w2 = _make_workout(session, date(2025, 2, 1))

    wl1a = _add_lift_to_workout(session, w1, lift_a)
    _add_set(session, wl1a, 5, 100.0)

    wl2b = _add_lift_to_workout(session, w2, lift_b)
    _add_set(session, wl2b, 5, 80.0)

    # lift_a only appears in w1
    data = client.get(f"/api/analytics/lifts/{lift_a}").json()
    assert len(data) == 1
    assert data[0]["workout_id"] == w1


def test_lift_history_indexes_progress(client: TestClient, session: Session):
    lift_id = _make_lift(session, "Overhead Press")

    w1 = _make_workout(session, date(2025, 1, 1))
    w2 = _make_workout(session, date(2025, 2, 1))

    wl1 = _add_lift_to_workout(session, w1, lift_id)
    _add_set(session, wl1, 5, 60.0)

    wl2 = _add_lift_to_workout(session, w2, lift_id)
    _add_set(session, wl2, 5, 75.0)

    data = client.get(f"/api/analytics/lifts/{lift_id}").json()
    assert len(data) == 2
    assert data[0]["strength_index"] == pytest.approx(1.0)
    assert data[1]["strength_index"] == pytest.approx(75.0 / 60.0)
