"""Unit tests for the intelligent lift selection algorithm."""

from datetime import date, timedelta

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.models import (
    Lift,
    LiftMuscleGroup,
    MuscleGroup,
    MuscleGroupConflict,
    Workout,
    WorkoutLift,
    WorkoutSet,
)
from backend.services.algorithm import suggest_lift


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
# Helper factories
# ---------------------------------------------------------------------------


def _add_muscle_group(session: Session, name: str) -> MuscleGroup:
    mg = MuscleGroup(name=name)
    session.add(mg)
    session.commit()
    session.refresh(mg)
    return mg


def _add_lift(session: Session, name: str, *muscle_groups: MuscleGroup) -> Lift:
    lift = Lift(name=name)
    session.add(lift)
    session.commit()
    session.refresh(lift)
    for mg in muscle_groups:
        lmg = LiftMuscleGroup(lift_id=lift.id, muscle_group_id=mg.id)
        session.add(lmg)
    session.commit()
    return lift


def _add_conflict(session: Session, mg_a: MuscleGroup, mg_b: MuscleGroup) -> None:
    conflict = MuscleGroupConflict(muscle_group_a_id=mg_a.id, muscle_group_b_id=mg_b.id)
    session.add(conflict)
    session.commit()


def _add_workout(session: Session, workout_date: date) -> Workout:
    workout = Workout(date=workout_date)
    session.add(workout)
    session.commit()
    session.refresh(workout)
    return workout


def _add_workout_lift(session: Session, workout: Workout, lift: Lift) -> WorkoutLift:
    wl = WorkoutLift(workout_id=workout.id, lift_id=lift.id)
    session.add(wl)
    session.commit()
    session.refresh(wl)
    return wl


def _add_set(
    session: Session,
    workout_lift: WorkoutLift,
    set_number: int,
    reps: int | None = None,
    weight: float | None = None,
) -> WorkoutSet:
    ws = WorkoutSet(
        workout_lift_id=workout_lift.id,
        set_number=set_number,
        reps=reps,
        weight=weight,
    )
    session.add(ws)
    session.commit()
    session.refresh(ws)
    return ws


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_empty_workout_uses_all_groups(session: Session):
    """An empty workout (no lifts yet) should consider any muscle group valid."""
    chest = _add_muscle_group(session, "Chest")
    legs = _add_muscle_group(session, "Legs")
    _add_lift(session, "Bench Press", chest)
    _add_lift(session, "Squat", legs)

    workout = _add_workout(session, date.today())

    result = suggest_lift(workout.id, session)

    assert result.muscle_group_id in {chest.id, legs.id}
    assert result.lift_id is not None
    assert result.lift_name != ""


def test_selects_least_recently_trained_group(session: Session):
    """Two muscle groups — one trained recently, one never — should pick the never-trained one."""
    chest = _add_muscle_group(session, "Chest")
    back = _add_muscle_group(session, "Back")

    bench = _add_lift(session, "Bench Press", chest)
    row = _add_lift(session, "Barbell Row", back)

    # Train chest yesterday
    past_workout = _add_workout(session, date.today() - timedelta(days=1))
    _add_workout_lift(session, past_workout, bench)

    # Today's empty workout
    today_workout = _add_workout(session, date.today())

    result = suggest_lift(today_workout.id, session)

    # Back was never trained — should be selected
    assert result.muscle_group_id == back.id
    assert result.lift_id == row.id


def test_avoids_groups_in_current_workout(session: Session):
    """If the current workout already has a chest lift, the algorithm must not pick chest again."""
    chest = _add_muscle_group(session, "Chest")
    legs = _add_muscle_group(session, "Legs")

    bench = _add_lift(session, "Bench Press", chest)
    squat = _add_lift(session, "Squat", legs)

    workout = _add_workout(session, date.today())
    # Chest lift already in this workout
    _add_workout_lift(session, workout, bench)

    result = suggest_lift(workout.id, session)

    assert result.muscle_group_id == legs.id
    assert result.lift_id == squat.id


def test_avoids_conflicting_groups(session: Session):
    """Group A is in the workout, group B conflicts with A — should pick C instead."""
    group_a = _add_muscle_group(session, "Chest")
    group_b = _add_muscle_group(session, "Shoulders")  # conflicts with Chest
    group_c = _add_muscle_group(session, "Legs")

    lift_a = _add_lift(session, "Bench Press", group_a)
    _add_lift(session, "Overhead Press", group_b)
    lift_c = _add_lift(session, "Squat", group_c)

    _add_conflict(session, group_a, group_b)

    workout = _add_workout(session, date.today())
    _add_workout_lift(session, workout, lift_a)

    result = suggest_lift(workout.id, session)

    # group_a is used, group_b conflicts → must pick group_c
    assert result.muscle_group_id == group_c.id
    assert result.lift_id == lift_c.id


def test_relaxes_conflict_when_all_excluded(session: Session):
    """If all non-used groups conflict with the used group, fall back to any non-used group."""
    group_a = _add_muscle_group(session, "Chest")
    group_b = _add_muscle_group(session, "Shoulders")

    lift_a = _add_lift(session, "Bench Press", group_a)
    lift_b = _add_lift(session, "Overhead Press", group_b)

    # The only other group conflicts with A
    _add_conflict(session, group_a, group_b)

    workout = _add_workout(session, date.today())
    _add_workout_lift(session, workout, lift_a)

    # With conflict relaxed, group_b is the only option
    result = suggest_lift(workout.id, session)

    assert result.muscle_group_id == group_b.id
    assert result.lift_id == lift_b.id


def test_selects_least_recently_done_lift_in_group(session: Session):
    """Two lifts in the chosen group — one done recently, one never — picks the never-done one."""
    chest = _add_muscle_group(session, "Chest")

    bench = _add_lift(session, "Bench Press", chest)
    cable_fly = _add_lift(session, "Cable Fly", chest)

    # Train bench recently
    past_workout = _add_workout(session, date.today() - timedelta(days=3))
    _add_workout_lift(session, past_workout, bench)

    # Today's empty workout
    today_workout = _add_workout(session, date.today())

    result = suggest_lift(today_workout.id, session)

    assert result.muscle_group_id == chest.id
    # cable_fly was never done — should be chosen over bench
    assert result.lift_id == cable_fly.id


def test_previous_sets_populated(session: Session):
    """When a lift has been done before, previous_sets should be populated."""
    chest = _add_muscle_group(session, "Chest")
    bench = _add_lift(session, "Bench Press", chest)

    past_workout = _add_workout(session, date.today() - timedelta(days=7))
    past_wl = _add_workout_lift(session, past_workout, bench)
    _add_set(session, past_wl, set_number=1, reps=5, weight=100.0)
    _add_set(session, past_wl, set_number=2, reps=5, weight=100.0)
    _add_set(session, past_wl, set_number=3, reps=4, weight=100.0)

    today_workout = _add_workout(session, date.today())

    result = suggest_lift(today_workout.id, session)

    assert result.lift_id == bench.id
    assert len(result.previous_sets) == 3
    assert result.previous_sets[0].set_number == 1
    assert result.previous_sets[0].reps == 5
    assert result.previous_sets[0].weight == 100.0
    assert result.previous_sets[1].set_number == 2
    assert result.previous_sets[2].set_number == 3
    assert result.previous_sets[2].reps == 4
    # All SetData objects should have real ids
    for s in result.previous_sets:
        assert s.id is not None
