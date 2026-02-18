from dataclasses import dataclass

from sqlmodel import Session, select

from backend.models import Workout, WorkoutLift, WorkoutSet


@dataclass
class WorkoutIndexes:
    workout_id: int
    date: str  # ISO date string
    strength_index: float | None
    endurance_index: float | None


def _get_baseline_workout_lift_id(lift_id: int, session: Session) -> int | None:
    """Return the WorkoutLift.id for the very first appearance of this lift."""
    statement = (
        select(WorkoutLift.id)
        .join(Workout, Workout.id == WorkoutLift.workout_id)
        .where(WorkoutLift.lift_id == lift_id)
        .order_by(Workout.date.asc(), WorkoutLift.id.asc())
        .limit(1)
    )
    return session.exec(statement).first()


def _max_weight_for_workout_lift(workout_lift_id: int, session: Session) -> float | None:
    """Return the max weight across all sets for a given WorkoutLift, or None."""
    sets = session.exec(
        select(WorkoutSet).where(WorkoutSet.workout_lift_id == workout_lift_id)
    ).all()
    weights = [s.weight for s in sets if s.weight is not None]
    return max(weights) if weights else None


def _volume_for_workout_lift(workout_lift_id: int, session: Session) -> float:
    """Return sum(reps * weight) for all sets where both reps and weight are non-null."""
    sets = session.exec(
        select(WorkoutSet).where(WorkoutSet.workout_lift_id == workout_lift_id)
    ).all()
    return sum(s.reps * s.weight for s in sets if s.reps is not None and s.weight is not None)


def calculate_workout_indexes(workout_id: int, session: Session) -> WorkoutIndexes:
    """Compute strength and endurance indexes for a single workout."""
    workout = session.get(Workout, workout_id)
    if workout is None:
        raise ValueError(f"Workout {workout_id} not found")

    workout_lifts = session.exec(
        select(WorkoutLift).where(WorkoutLift.workout_id == workout_id)
    ).all()

    strength_ratios: list[float] = []
    endurance_ratios: list[float] = []

    for wl in workout_lifts:
        baseline_wl_id = _get_baseline_workout_lift_id(wl.lift_id, session)
        if baseline_wl_id is None:
            continue

        # --- Strength index ---
        baseline_max = _max_weight_for_workout_lift(baseline_wl_id, session)
        current_max = _max_weight_for_workout_lift(wl.id, session)
        if baseline_max is not None and baseline_max > 0 and current_max is not None:
            strength_ratios.append(current_max / baseline_max)

        # --- Endurance index ---
        baseline_volume = _volume_for_workout_lift(baseline_wl_id, session)
        current_volume = _volume_for_workout_lift(wl.id, session)
        if baseline_volume > 0:
            endurance_ratios.append(current_volume / baseline_volume)

    strength_index = sum(strength_ratios) / len(strength_ratios) if strength_ratios else None
    endurance_index = sum(endurance_ratios) / len(endurance_ratios) if endurance_ratios else None

    return WorkoutIndexes(
        workout_id=workout_id,
        date=workout.date.isoformat(),
        strength_index=strength_index,
        endurance_index=endurance_index,
    )


def get_all_workout_indexes(session: Session) -> list[WorkoutIndexes]:
    """Return WorkoutIndexes for every workout, ordered by date ASC."""
    workouts = session.exec(select(Workout).order_by(Workout.date.asc())).all()
    return [calculate_workout_indexes(w.id, session) for w in workouts]


def get_lift_index_history(lift_id: int, session: Session) -> list[WorkoutIndexes]:
    """
    Return WorkoutIndexes for every workout that contains the given lift,
    ordered by date ASC. Each result reflects only that single lift's contribution.
    """
    statement = (
        select(WorkoutLift)
        .join(Workout, Workout.id == WorkoutLift.workout_id)
        .where(WorkoutLift.lift_id == lift_id)
        .order_by(Workout.date.asc(), WorkoutLift.id.asc())
    )
    workout_lifts = session.exec(statement).all()

    baseline_wl_id = _get_baseline_workout_lift_id(lift_id, session)
    baseline_max = _max_weight_for_workout_lift(baseline_wl_id, session) if baseline_wl_id else None
    baseline_volume = _volume_for_workout_lift(baseline_wl_id, session) if baseline_wl_id else 0.0

    results: list[WorkoutIndexes] = []
    for wl in workout_lifts:
        workout = session.get(Workout, wl.workout_id)

        current_max = _max_weight_for_workout_lift(wl.id, session)
        current_volume = _volume_for_workout_lift(wl.id, session)

        if baseline_max is not None and baseline_max > 0 and current_max is not None:
            strength_index: float | None = current_max / baseline_max
        else:
            strength_index = None

        if baseline_volume > 0:
            endurance_index: float | None = current_volume / baseline_volume
        else:
            endurance_index = None

        results.append(
            WorkoutIndexes(
                workout_id=wl.workout_id,
                date=workout.date.isoformat(),
                strength_index=strength_index,
                endurance_index=endurance_index,
            )
        )

    return results
