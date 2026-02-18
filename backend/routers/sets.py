from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel, select

from backend.database import get_session
from backend.models import WorkoutLift, WorkoutSet

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


class SetRead(SQLModel):
    id: int
    set_number: int
    reps: int | None
    weight: float | None


class SetCreate(SQLModel):
    reps: int | None = None
    weight: float | None = None


class SetUpdate(SQLModel):
    reps: int | None = None
    weight: float | None = None


@router.post("/workout-lifts/{wl_id}/sets", response_model=SetRead, status_code=201)
def add_set(wl_id: int, body: SetCreate, session: SessionDep):
    if session.get(WorkoutLift, wl_id) is None:
        raise HTTPException(status_code=404, detail="WorkoutLift not found")

    existing = session.exec(select(WorkoutSet).where(WorkoutSet.workout_lift_id == wl_id)).all()
    set_number = len(existing) + 1

    workout_set = WorkoutSet(
        workout_lift_id=wl_id,
        set_number=set_number,
        reps=body.reps,
        weight=body.weight,
    )
    session.add(workout_set)
    session.commit()
    session.refresh(workout_set)
    return workout_set


@router.patch("/sets/{set_id}", response_model=SetRead)
def update_set(set_id: int, body: SetUpdate, session: SessionDep):
    workout_set = session.get(WorkoutSet, set_id)
    if workout_set is None:
        raise HTTPException(status_code=404, detail="Set not found")

    if body.reps is not None:
        workout_set.reps = body.reps
    if body.weight is not None:
        workout_set.weight = body.weight

    session.add(workout_set)
    session.commit()
    session.refresh(workout_set)
    return workout_set


@router.delete("/sets/{set_id}", status_code=204)
def delete_set(set_id: int, session: SessionDep):
    workout_set = session.get(WorkoutSet, set_id)
    if workout_set is None:
        raise HTTPException(status_code=404, detail="Set not found")

    session.delete(workout_set)
    session.commit()
