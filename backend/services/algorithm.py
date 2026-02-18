from dataclasses import dataclass, field
from datetime import date

from fastapi import HTTPException
from sqlmodel import Session, select

from backend.models import (
    LiftMuscleGroup,
    MuscleGroup,
    MuscleGroupConflict,
    Workout,
    WorkoutLift,
    WorkoutSet,
)


@dataclass
class SetData:
    set_number: int
    reps: int | None
    weight: float | None
    id: int | None = None


@dataclass
class SuggestResult:
    muscle_group_id: int
    muscle_group_name: str
    lift_id: int
    lift_name: str
    previous_sets: list[SetData] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_used_group_ids(workout_id: int, session: Session) -> set[int]:
    """Return the set of muscle_group_ids already represented in this workout."""
    workout_lifts = session.exec(
        select(WorkoutLift).where(WorkoutLift.workout_id == workout_id)
    ).all()
    lift_ids = [wl.lift_id for wl in workout_lifts]
    if not lift_ids:
        return set()
    lmg_rows = session.exec(
        select(LiftMuscleGroup).where(LiftMuscleGroup.lift_id.in_(lift_ids))
    ).all()
    return {row.muscle_group_id for row in lmg_rows}


def _get_conflict_group_ids(used_group_ids: set[int], session: Session) -> set[int]:
    """Return muscle_group_ids that conflict with any used group (excluding used ones)."""
    if not used_group_ids:
        return set()
    conflicts = session.exec(
        select(MuscleGroupConflict).where(
            MuscleGroupConflict.muscle_group_a_id.in_(used_group_ids)
            | MuscleGroupConflict.muscle_group_b_id.in_(used_group_ids)
        )
    ).all()
    conflict_ids: set[int] = set()
    for c in conflicts:
        if c.muscle_group_a_id not in used_group_ids:
            conflict_ids.add(c.muscle_group_a_id)
        if c.muscle_group_b_id not in used_group_ids:
            conflict_ids.add(c.muscle_group_b_id)
    return conflict_ids


def _last_trained_date(group_id: int, session: Session) -> date | None:
    """Return the most recent workout date for the given muscle group, or None."""
    lmg_rows = session.exec(
        select(LiftMuscleGroup).where(LiftMuscleGroup.muscle_group_id == group_id)
    ).all()
    lift_ids = [row.lift_id for row in lmg_rows]
    if not lift_ids:
        return None
    workout_lifts = session.exec(select(WorkoutLift).where(WorkoutLift.lift_id.in_(lift_ids))).all()
    if not workout_lifts:
        return None
    workout_ids = [wl.workout_id for wl in workout_lifts]
    workouts = session.exec(select(Workout).where(Workout.id.in_(workout_ids))).all()
    if not workouts:
        return None
    return max(w.date for w in workouts)


def _select_candidate_group(candidates: set[int], session: Session) -> MuscleGroup:
    """Among candidate group_ids, pick the one with the oldest last_trained date."""
    best_group_id: int | None = None
    best_date: date | None = None
    found_none = False

    for group_id in candidates:
        last = _last_trained_date(group_id, session)
        if last is None:
            if not found_none:
                found_none = True
                best_group_id = group_id
                best_date = None
        elif not found_none:
            if best_group_id is None or last < best_date:
                best_group_id = group_id
                best_date = last

    group = session.get(MuscleGroup, best_group_id)
    return group


def _last_done_date_for_lift(lift_id: int, session: Session) -> date | None:
    """Return the most recent workout date for the given lift, or None."""
    workout_lifts = session.exec(select(WorkoutLift).where(WorkoutLift.lift_id == lift_id)).all()
    if not workout_lifts:
        return None
    workout_ids = [wl.workout_id for wl in workout_lifts]
    workouts = session.exec(select(Workout).where(Workout.id.in_(workout_ids))).all()
    if not workouts:
        return None
    return max(w.date for w in workouts)


def _select_lift_in_group(group_id: int, session: Session) -> int:
    """Among all lifts in the given muscle group, pick the least recently done one."""
    lmg_rows = session.exec(
        select(LiftMuscleGroup).where(LiftMuscleGroup.muscle_group_id == group_id)
    ).all()
    lift_ids = [row.lift_id for row in lmg_rows]
    if not lift_ids:
        raise HTTPException(status_code=404, detail="No lifts found for muscle group")

    best_lift_id: int | None = None
    best_date: date | None = None
    found_none = False

    for lift_id in lift_ids:
        last = _last_done_date_for_lift(lift_id, session)
        if last is None:
            if not found_none:
                found_none = True
                best_lift_id = lift_id
                best_date = None
        elif not found_none:
            if best_lift_id is None or last < best_date:
                best_lift_id = lift_id
                best_date = last

    return best_lift_id


def _get_previous_sets(lift_id: int, session: Session) -> list[SetData]:
    """Return the WorkoutSets from the most recent WorkoutLift for this lift."""
    workout_lifts = session.exec(select(WorkoutLift).where(WorkoutLift.lift_id == lift_id)).all()
    if not workout_lifts:
        return []

    # Find the most recent workout for this lift
    best_wl: WorkoutLift | None = None
    best_date: date | None = None
    for wl in workout_lifts:
        workout = session.get(Workout, wl.workout_id)
        if workout is None:
            continue
        if best_date is None or workout.date > best_date:
            best_date = workout.date
            best_wl = wl

    if best_wl is None:
        return []

    sets = session.exec(
        select(WorkoutSet)
        .where(WorkoutSet.workout_lift_id == best_wl.id)
        .order_by(WorkoutSet.set_number)
    ).all()

    return [
        SetData(
            id=s.id,
            set_number=s.set_number,
            reps=s.reps,
            weight=s.weight,
        )
        for s in sets
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def suggest_lift(workout_id: int, session: Session) -> SuggestResult:
    """Suggest the next lift for a workout using the intelligent selection algorithm."""
    # Steps 1-2: get muscle groups already used in this workout
    used_group_ids = _get_used_group_ids(workout_id, session)

    # Step 3: get conflicting groups (the other side of each conflict not in used)
    conflict_group_ids = _get_conflict_group_ids(used_group_ids, session)

    # Step 4-5: build candidate set
    all_groups = session.exec(select(MuscleGroup)).all()
    all_group_ids = {g.id for g in all_groups}

    # Step 6: candidates exclude used and conflicting groups
    excluded = used_group_ids | conflict_group_ids
    candidates = all_group_ids - excluded

    # Step 7: relax conflict constraint if no candidates
    if not candidates:
        candidates = all_group_ids - used_group_ids

    # Step 8: relax all constraints if still no candidates
    if not candidates:
        candidates = all_group_ids

    # Step 9: no muscle groups at all
    if not candidates:
        raise HTTPException(status_code=404, detail="No muscle groups found")

    # Steps 10-11: select candidate group with oldest last_trained date
    selected_group = _select_candidate_group(candidates, session)

    # Steps 12: select lift with oldest last_done date within the group
    selected_lift_id = _select_lift_in_group(selected_group.id, session)

    from backend.models import Lift

    selected_lift = session.get(Lift, selected_lift_id)

    # Step 13: get previous sets
    previous_sets = _get_previous_sets(selected_lift_id, session)

    # Step 14: return result
    return SuggestResult(
        muscle_group_id=selected_group.id,
        muscle_group_name=selected_group.name,
        lift_id=selected_lift.id,
        lift_name=selected_lift.name,
        previous_sets=previous_sets,
    )
