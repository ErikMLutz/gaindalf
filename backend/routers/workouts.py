from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel, select

from backend.database import get_session
from backend.models import Lift, Workout, WorkoutLift, WorkoutSet

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class SetRead(SQLModel):
    id: int
    set_number: int
    reps: int | None
    weight: float | None


class WorkoutLiftRead(SQLModel):
    id: int
    lift_id: int
    lift_name: str
    display_order: int
    sets: list[SetRead]


class WorkoutRead(SQLModel):
    id: int
    date: str  # ISO format
    subtitle: str
    workout_lifts: list[WorkoutLiftRead]


class WorkoutSummary(SQLModel):
    id: int
    date: str  # ISO format
    subtitle: str
    lift_names: list[str]


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class SubtitleUpdate(SQLModel):
    subtitle: str


class AddLiftBody(SQLModel):
    lift_id: int
    display_order: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_workout_read(workout: Workout, session: Session) -> WorkoutRead:
    workout_lifts_db = session.exec(
        select(WorkoutLift).where(WorkoutLift.workout_id == workout.id)
    ).all()

    workout_lift_reads: list[WorkoutLiftRead] = []
    for wl in workout_lifts_db:
        lift = session.get(Lift, wl.lift_id)
        lift_name = lift.name if lift else ""
        sets_db = session.exec(select(WorkoutSet).where(WorkoutSet.workout_lift_id == wl.id)).all()
        sets = [
            SetRead(
                id=s.id,
                set_number=s.set_number,
                reps=s.reps,
                weight=s.weight,
            )
            for s in sets_db
        ]
        workout_lift_reads.append(
            WorkoutLiftRead(
                id=wl.id,
                lift_id=wl.lift_id,
                lift_name=lift_name,
                display_order=wl.display_order,
                sets=sets,
            )
        )

    return WorkoutRead(
        id=workout.id,
        date=workout.date.isoformat(),
        subtitle=workout.subtitle,
        workout_lifts=workout_lift_reads,
    )


def _delete_workout_cascade(workout: Workout, session: Session) -> None:
    """Delete WorkoutSets -> WorkoutLifts -> Workout (SQLite has no auto-cascade)."""
    workout_lifts = session.exec(
        select(WorkoutLift).where(WorkoutLift.workout_id == workout.id)
    ).all()
    wl_ids = [wl.id for wl in workout_lifts]

    if wl_ids:
        sets = session.exec(select(WorkoutSet).where(WorkoutSet.workout_lift_id.in_(wl_ids))).all()
        for s in sets:
            session.delete(s)
        for wl in workout_lifts:
            session.delete(wl)

    session.delete(workout)
    session.commit()


def _delete_workout_lift_cascade(wl: WorkoutLift, session: Session) -> None:
    """Delete WorkoutSets for a WorkoutLift, then the WorkoutLift itself."""
    sets = session.exec(select(WorkoutSet).where(WorkoutSet.workout_lift_id == wl.id)).all()
    for s in sets:
        session.delete(s)
    session.delete(wl)
    session.commit()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[WorkoutSummary])
def list_workouts(session: SessionDep):
    workouts = session.exec(select(Workout).order_by(Workout.date.desc())).all()
    result: list[WorkoutSummary] = []
    for workout in workouts:
        workout_lifts = session.exec(
            select(WorkoutLift).where(WorkoutLift.workout_id == workout.id)
        ).all()
        lift_names: list[str] = []
        for wl in workout_lifts:
            lift = session.get(Lift, wl.lift_id)
            if lift:
                lift_names.append(lift.name)
        result.append(
            WorkoutSummary(
                id=workout.id,
                date=workout.date.isoformat(),
                subtitle=workout.subtitle,
                lift_names=lift_names,
            )
        )
    return result


@router.post("/", response_model=WorkoutRead, status_code=201)
def create_workout(session: SessionDep):
    workout = Workout(date=date.today(), subtitle="")
    session.add(workout)
    session.commit()
    session.refresh(workout)
    return _build_workout_read(workout, session)


@router.get("/{id}", response_model=WorkoutRead)
def get_workout(id: int, session: SessionDep):
    workout = session.get(Workout, id)
    if workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    return _build_workout_read(workout, session)


@router.patch("/{id}", response_model=WorkoutRead)
def update_workout(id: int, body: SubtitleUpdate, session: SessionDep):
    workout = session.get(Workout, id)
    if workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    workout.subtitle = body.subtitle
    session.add(workout)
    session.commit()
    session.refresh(workout)
    return _build_workout_read(workout, session)


@router.delete("/{id}", status_code=204)
def delete_workout(id: int, session: SessionDep):
    workout = session.get(Workout, id)
    if workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    _delete_workout_cascade(workout, session)


@router.post("/{id}/lifts", response_model=WorkoutLiftRead, status_code=201)
def add_lift_to_workout(id: int, body: AddLiftBody, session: SessionDep):
    workout = session.get(Workout, id)
    if workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    lift = session.get(Lift, body.lift_id)
    if lift is None:
        raise HTTPException(status_code=404, detail="Lift not found")
    wl = WorkoutLift(
        workout_id=id,
        lift_id=body.lift_id,
        display_order=body.display_order,
    )
    session.add(wl)
    session.commit()
    session.refresh(wl)
    return WorkoutLiftRead(
        id=wl.id,
        lift_id=wl.lift_id,
        lift_name=lift.name,
        display_order=wl.display_order,
        sets=[],
    )


@router.delete("/{id}/lifts/{wl_id}", status_code=204)
def remove_lift_from_workout(id: int, wl_id: int, session: SessionDep):
    wl = session.get(WorkoutLift, wl_id)
    if wl is None or wl.workout_id != id:
        raise HTTPException(status_code=404, detail="WorkoutLift not found")
    _delete_workout_lift_cascade(wl, session)


# ---------------------------------------------------------------------------
# Suggest endpoint
# ---------------------------------------------------------------------------

from backend.services.algorithm import suggest_lift  # noqa: E402


class SuggestResponse(SQLModel):
    muscle_group_id: int
    muscle_group_name: str
    lift_id: int
    lift_name: str
    previous_sets: list[SetRead]


@router.post("/{workout_id}/suggest", response_model=SuggestResponse, status_code=200)
def suggest_lift_for_workout(workout_id: int, session: SessionDep):
    if session.get(Workout, workout_id) is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    result = suggest_lift(workout_id, session)
    return SuggestResponse(
        muscle_group_id=result.muscle_group_id,
        muscle_group_name=result.muscle_group_name,
        lift_id=result.lift_id,
        lift_name=result.lift_name,
        previous_sets=[
            SetRead(
                id=s.id if s.id is not None else s.set_number,
                set_number=s.set_number,
                reps=s.reps,
                weight=s.weight,
            )
            for s in result.previous_sets
        ],
    )
