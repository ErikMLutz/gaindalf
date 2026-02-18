"""Smoke tests: verify all tables are created and basic records round-trip."""

from datetime import date

from sqlmodel import Session, select

from backend.models import (
    Lift,
    LiftMuscleGroup,
    MuscleGroup,
    MuscleGroupConflict,
    Workout,
    WorkoutLift,
    WorkoutSet,
)


def test_muscle_group_roundtrip(session: Session):
    mg = MuscleGroup(name="Chest")
    session.add(mg)
    session.commit()
    session.refresh(mg)
    assert mg.id is not None
    assert session.exec(select(MuscleGroup)).one().name == "Chest"


def test_lift_roundtrip(session: Session):
    lift = Lift(name="Bench Press")
    session.add(lift)
    session.commit()
    session.refresh(lift)
    assert lift.id is not None


def test_lift_muscle_group_link(session: Session):
    mg = MuscleGroup(name="Chest")
    lift = Lift(name="Bench Press")
    session.add(mg)
    session.add(lift)
    session.commit()
    session.refresh(mg)
    session.refresh(lift)

    link = LiftMuscleGroup(lift_id=lift.id, muscle_group_id=mg.id)
    session.add(link)
    session.commit()

    result = session.exec(select(LiftMuscleGroup)).one()
    assert result.lift_id == lift.id
    assert result.muscle_group_id == mg.id


def test_workout_roundtrip(session: Session):
    workout = Workout(date=date(2025, 1, 15), subtitle="Heavy leg day")
    session.add(workout)
    session.commit()
    session.refresh(workout)
    assert workout.id is not None
    assert workout.subtitle == "Heavy leg day"


def test_workout_lift_and_set_roundtrip(session: Session):
    mg = MuscleGroup(name="Legs")
    lift = Lift(name="Squat")
    workout = Workout(date=date(2025, 1, 15))
    session.add_all([mg, lift, workout])
    session.commit()
    session.refresh(lift)
    session.refresh(workout)

    wl = WorkoutLift(workout_id=workout.id, lift_id=lift.id, display_order=0)
    session.add(wl)
    session.commit()
    session.refresh(wl)

    ws = WorkoutSet(workout_lift_id=wl.id, set_number=1, reps=5, weight=100.0)
    session.add(ws)
    session.commit()
    session.refresh(ws)

    assert ws.id is not None
    assert ws.reps == 5
    assert ws.weight == 100.0


def test_muscle_group_conflict_roundtrip(session: Session):
    arms = MuscleGroup(name="Arms")
    shoulders = MuscleGroup(name="Shoulders")
    session.add_all([arms, shoulders])
    session.commit()
    session.refresh(arms)
    session.refresh(shoulders)

    conflict = MuscleGroupConflict(muscle_group_a_id=arms.id, muscle_group_b_id=shoulders.id)
    session.add(conflict)
    session.commit()
    session.refresh(conflict)
    assert conflict.id is not None
