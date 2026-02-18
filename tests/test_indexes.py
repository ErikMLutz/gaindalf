from datetime import date

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.services.indexes import (
    WorkoutIndexes,
    calculate_workout_indexes,
    get_all_workout_indexes,
    get_lift_index_history,
)

# ---------------------------------------------------------------------------
# Session fixture (independent of the app's engine)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def make_workout(session: Session, d: date) -> int:
    """Insert a Workout and return its id."""
    from backend.models import Workout

    w = Workout(date=d)
    session.add(w)
    session.commit()
    session.refresh(w)
    return w.id


def make_lift(session: Session, name: str) -> int:
    """Insert a Lift and return its id."""
    from backend.models import Lift

    lift = Lift(name=name)
    session.add(lift)
    session.commit()
    session.refresh(lift)
    return lift.id


def add_lift_to_workout(session: Session, workout_id: int, lift_id: int) -> int:
    """Insert a WorkoutLift and return its id."""
    from backend.models import WorkoutLift

    wl = WorkoutLift(workout_id=workout_id, lift_id=lift_id)
    session.add(wl)
    session.commit()
    session.refresh(wl)
    return wl.id


def add_set(
    session: Session,
    workout_lift_id: int,
    reps: int | None,
    weight: float | None,
    set_number: int = 1,
) -> None:
    """Insert a WorkoutSet."""
    from backend.models import WorkoutSet

    ws = WorkoutSet(
        workout_lift_id=workout_lift_id,
        set_number=set_number,
        reps=reps,
        weight=weight,
    )
    session.add(ws)
    session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_first_workout_strength_index_is_one(session: Session):
    """A lift's very first appearance should yield strength_index = 1.0."""
    w1 = make_workout(session, date(2025, 1, 1))
    lift = make_lift(session, "Squat")
    wl1 = add_lift_to_workout(session, w1, lift)
    add_set(session, wl1, reps=5, weight=100.0)

    result = calculate_workout_indexes(w1, session)

    assert isinstance(result, WorkoutIndexes)
    assert result.strength_index == pytest.approx(1.0)


def test_strength_index_improves(session: Session):
    """Second workout with higher max weight → strength_index > 1.0."""
    lift = make_lift(session, "Bench Press")

    w1 = make_workout(session, date(2025, 1, 1))
    wl1 = add_lift_to_workout(session, w1, lift)
    add_set(session, wl1, reps=5, weight=100.0)

    w2 = make_workout(session, date(2025, 1, 8))
    wl2 = add_lift_to_workout(session, w2, lift)
    add_set(session, wl2, reps=5, weight=120.0)

    result = calculate_workout_indexes(w2, session)

    assert result.strength_index == pytest.approx(1.2)


def test_strength_index_regression(session: Session):
    """Second workout with lower max weight → strength_index < 1.0."""
    lift = make_lift(session, "Deadlift")

    w1 = make_workout(session, date(2025, 1, 1))
    wl1 = add_lift_to_workout(session, w1, lift)
    add_set(session, wl1, reps=5, weight=200.0)

    w2 = make_workout(session, date(2025, 1, 8))
    wl2 = add_lift_to_workout(session, w2, lift)
    add_set(session, wl2, reps=5, weight=180.0)

    result = calculate_workout_indexes(w2, session)

    assert result.strength_index == pytest.approx(0.9)


def test_endurance_index_first_is_one(session: Session):
    """A lift's very first appearance should yield endurance_index = 1.0."""
    w1 = make_workout(session, date(2025, 1, 1))
    lift = make_lift(session, "Row")
    wl1 = add_lift_to_workout(session, w1, lift)
    add_set(session, wl1, reps=10, weight=60.0)

    result = calculate_workout_indexes(w1, session)

    assert result.endurance_index == pytest.approx(1.0)


def test_endurance_index_increases_with_volume(session: Session):
    """More total volume in the second workout → endurance_index > 1.0."""
    lift = make_lift(session, "Pull-up")

    w1 = make_workout(session, date(2025, 1, 1))
    wl1 = add_lift_to_workout(session, w1, lift)
    # volume = 3 * 10 * 50 = 1500
    add_set(session, wl1, reps=10, weight=50.0, set_number=1)
    add_set(session, wl1, reps=10, weight=50.0, set_number=2)
    add_set(session, wl1, reps=10, weight=50.0, set_number=3)

    w2 = make_workout(session, date(2025, 1, 8))
    wl2 = add_lift_to_workout(session, w2, lift)
    # volume = 3 * 12 * 55 = 1980
    add_set(session, wl2, reps=12, weight=55.0, set_number=1)
    add_set(session, wl2, reps=12, weight=55.0, set_number=2)
    add_set(session, wl2, reps=12, weight=55.0, set_number=3)

    result = calculate_workout_indexes(w2, session)

    assert result.endurance_index is not None
    assert result.endurance_index > 1.0
    assert result.endurance_index == pytest.approx(1980 / 1500)


def test_no_sets_returns_none(session: Session):
    """A WorkoutLift with no sets is excluded; if it's the only lift, both indexes are None."""
    w1 = make_workout(session, date(2025, 1, 1))
    lift = make_lift(session, "Curl")
    add_lift_to_workout(session, w1, lift)
    # No sets added intentionally

    result = calculate_workout_indexes(w1, session)

    assert result.strength_index is None
    assert result.endurance_index is None


def test_missing_baseline_excluded(session: Session):
    """
    A lift that first appears in workout 2 (with workout 2 being its baseline)
    but we craft a scenario where the lift appears only in workout 2 and workout 2
    is the baseline — so it IS included. Instead test that a lift added only to
    workout 2 does not distort the average: baseline and current are the same wl,
    so ratio = 1.0, which is correct. Actually test the documented behaviour:
    lifts with baseline_max == 0 or no sets are excluded.
    """
    lift_a = make_lift(session, "Squat")
    lift_b = make_lift(session, "Lunge")  # will only appear in w2 with weight=0

    w1 = make_workout(session, date(2025, 1, 1))
    wl1a = add_lift_to_workout(session, w1, lift_a)
    add_set(session, wl1a, reps=5, weight=100.0)

    w2 = make_workout(session, date(2025, 1, 8))
    wl2a = add_lift_to_workout(session, w2, lift_a)
    add_set(session, wl2a, reps=5, weight=110.0)
    # lift_b baseline has weight=0 → should be excluded from average
    wl2b = add_lift_to_workout(session, w2, lift_b)
    add_set(session, wl2b, reps=10, weight=0.0)

    result = calculate_workout_indexes(w2, session)

    # Only lift_a contributes: 110/100 = 1.1
    assert result.strength_index == pytest.approx(1.1)


def test_multiple_lifts_averaged(session: Session):
    """Two lifts contributing 1.0 and 2.0 → average strength_index = 1.5."""
    lift_a = make_lift(session, "Overhead Press")
    lift_b = make_lift(session, "Lateral Raise")

    # Establish baselines
    w1 = make_workout(session, date(2025, 1, 1))
    wl1a = add_lift_to_workout(session, w1, lift_a)
    add_set(session, wl1a, reps=5, weight=80.0)
    wl1b = add_lift_to_workout(session, w1, lift_b)
    add_set(session, wl1b, reps=10, weight=20.0)

    # Second workout: lift_a stays the same (ratio 1.0), lift_b doubles (ratio 2.0)
    w2 = make_workout(session, date(2025, 1, 8))
    wl2a = add_lift_to_workout(session, w2, lift_a)
    add_set(session, wl2a, reps=5, weight=80.0)
    wl2b = add_lift_to_workout(session, w2, lift_b)
    add_set(session, wl2b, reps=10, weight=40.0)

    result = calculate_workout_indexes(w2, session)

    assert result.strength_index == pytest.approx(1.5)


def test_get_all_workout_indexes_ordered_by_date(session: Session):
    """get_all_workout_indexes returns results ordered by date ascending."""
    lift = make_lift(session, "Press")

    w3 = make_workout(session, date(2025, 3, 1))
    w1 = make_workout(session, date(2025, 1, 1))
    w2 = make_workout(session, date(2025, 2, 1))

    for wid in (w1, w2, w3):
        wl = add_lift_to_workout(session, wid, lift)
        add_set(session, wl, reps=5, weight=100.0)

    results = get_all_workout_indexes(session)

    assert len(results) == 3
    dates = [r.date for r in results]
    assert dates == sorted(dates)
    assert dates[0] == "2025-01-01"
    assert dates[1] == "2025-02-01"
    assert dates[2] == "2025-03-01"


def test_get_lift_index_history_only_includes_that_lift(session: Session):
    """
    Two lifts across two workouts. History for lift_a only includes workouts
    that contain lift_a and reflects only lift_a's contribution.
    """
    lift_a = make_lift(session, "Bench")
    lift_b = make_lift(session, "Fly")

    # w1: both lifts present
    w1 = make_workout(session, date(2025, 1, 1))
    wl1a = add_lift_to_workout(session, w1, lift_a)
    add_set(session, wl1a, reps=5, weight=100.0)
    wl1b = add_lift_to_workout(session, w1, lift_b)
    add_set(session, wl1b, reps=12, weight=30.0)

    # w2: only lift_b
    w2 = make_workout(session, date(2025, 1, 8))
    wl2b = add_lift_to_workout(session, w2, lift_b)
    add_set(session, wl2b, reps=12, weight=35.0)

    # w3: only lift_a with higher weight
    w3 = make_workout(session, date(2025, 1, 15))
    wl3a = add_lift_to_workout(session, w3, lift_a)
    add_set(session, wl3a, reps=5, weight=110.0)

    history_a = get_lift_index_history(lift_a, session)
    history_b = get_lift_index_history(lift_b, session)

    # lift_a appears in w1 and w3 only
    assert len(history_a) == 2
    assert history_a[0].workout_id == w1
    assert history_a[1].workout_id == w3

    # First entry is baseline → strength_index = 1.0
    assert history_a[0].strength_index == pytest.approx(1.0)
    # Second entry: 110/100 = 1.1
    assert history_a[1].strength_index == pytest.approx(1.1)

    # lift_b appears in w1 and w2 only
    assert len(history_b) == 2
    workout_ids_b = {r.workout_id for r in history_b}
    assert w2 in workout_ids_b
    assert w3 not in workout_ids_b
