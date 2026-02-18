from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel

from backend.database import get_session
from backend.services.indexes import get_all_workout_indexes, get_lift_index_history

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


class WorkoutIndexesRead(SQLModel):
    workout_id: int
    date: str
    strength_index: float | None
    endurance_index: float | None


@router.get("/progress", response_model=list[WorkoutIndexesRead])
def get_progress(session: SessionDep):
    results = get_all_workout_indexes(session)
    return [
        WorkoutIndexesRead(
            workout_id=r.workout_id,
            date=r.date,
            strength_index=r.strength_index,
            endurance_index=r.endurance_index,
        )
        for r in results
    ]


@router.get("/lifts/{lift_id}", response_model=list[WorkoutIndexesRead])
def get_lift_history(lift_id: int, session: SessionDep):
    results = get_lift_index_history(lift_id, session)
    if not results:
        # Return empty list if lift exists but has no history; 404 only if lift_id is unknown
        from sqlmodel import select

        from backend.models import Lift

        if session.exec(select(Lift).where(Lift.id == lift_id)).first() is None:
            raise HTTPException(status_code=404, detail="Lift not found")
    return [
        WorkoutIndexesRead(
            workout_id=r.workout_id,
            date=r.date,
            strength_index=r.strength_index,
            endurance_index=r.endurance_index,
        )
        for r in results
    ]
