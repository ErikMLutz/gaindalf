from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

from backend.database import get_session
from backend.models import Lift, LiftMuscleGroup, MuscleGroup

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


class LiftRead(SQLModel):
    id: int
    name: str
    muscle_group_ids: list[int]


class LiftCreate(SQLModel):
    name: str
    muscle_group_ids: list[int]


class LiftUpdate(SQLModel):
    name: str | None = None
    muscle_group_ids: list[int] | None = None


def _muscle_group_ids_for_lift(session: Session, lift_id: int) -> list[int]:
    rows = session.exec(select(LiftMuscleGroup).where(LiftMuscleGroup.lift_id == lift_id)).all()
    return [row.muscle_group_id for row in rows]


def _verify_muscle_groups_exist(session: Session, muscle_group_ids: list[int]) -> None:
    for mg_id in muscle_group_ids:
        if session.get(MuscleGroup, mg_id) is None:
            raise HTTPException(
                status_code=400,
                detail=f"Muscle group with id {mg_id} does not exist",
            )


@router.get("/", response_model=list[LiftRead])
def list_lifts(session: SessionDep):
    lifts = session.exec(select(Lift)).all()
    return [
        LiftRead(
            id=lift.id,
            name=lift.name,
            muscle_group_ids=_muscle_group_ids_for_lift(session, lift.id),
        )
        for lift in lifts
    ]


@router.post("/", response_model=LiftRead, status_code=201)
def create_lift(body: LiftCreate, session: SessionDep):
    _verify_muscle_groups_exist(session, body.muscle_group_ids)

    lift = Lift(name=body.name)
    session.add(lift)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Name already exists")
    session.refresh(lift)

    for mg_id in body.muscle_group_ids:
        link = LiftMuscleGroup(lift_id=lift.id, muscle_group_id=mg_id)
        session.add(link)
    session.commit()

    return LiftRead(
        id=lift.id,
        name=lift.name,
        muscle_group_ids=_muscle_group_ids_for_lift(session, lift.id),
    )


@router.patch("/{id}", response_model=LiftRead)
def update_lift(id: int, body: LiftUpdate, session: SessionDep):
    lift = session.get(Lift, id)
    if lift is None:
        raise HTTPException(status_code=404, detail="Lift not found")

    if body.name is not None:
        lift.name = body.name
        session.add(lift)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(status_code=400, detail="Name already exists")
        session.refresh(lift)

    if body.muscle_group_ids is not None:
        _verify_muscle_groups_exist(session, body.muscle_group_ids)

        existing = session.exec(select(LiftMuscleGroup).where(LiftMuscleGroup.lift_id == id)).all()
        for row in existing:
            session.delete(row)
        session.commit()

        for mg_id in body.muscle_group_ids:
            link = LiftMuscleGroup(lift_id=lift.id, muscle_group_id=mg_id)
            session.add(link)
        session.commit()

    return LiftRead(
        id=lift.id,
        name=lift.name,
        muscle_group_ids=_muscle_group_ids_for_lift(session, lift.id),
    )


@router.delete("/{id}", status_code=204)
def delete_lift(id: int, session: SessionDep):
    lift = session.get(Lift, id)
    if lift is None:
        raise HTTPException(status_code=404, detail="Lift not found")

    existing = session.exec(select(LiftMuscleGroup).where(LiftMuscleGroup.lift_id == id)).all()
    for row in existing:
        session.delete(row)
    session.commit()

    session.delete(lift)
    session.commit()


class PreviousSetRead(SQLModel):
    set_number: int
    reps: int | None
    weight: float | None


@router.get("/{lift_id}/last-sets", response_model=list[PreviousSetRead])
def get_last_sets(lift_id: int, session: SessionDep):
    """Return the sets from the most recent workout containing this lift."""
    from backend.models import Workout, WorkoutLift, WorkoutSet

    result = session.exec(
        select(WorkoutLift)
        .join(Workout, WorkoutLift.workout_id == Workout.id)
        .where(WorkoutLift.lift_id == lift_id)
        .order_by(Workout.date.desc(), WorkoutLift.id.desc())
    ).first()

    if result is None:
        return []

    sets = session.exec(
        select(WorkoutSet)
        .where(WorkoutSet.workout_lift_id == result.id)
        .order_by(WorkoutSet.set_number)
    ).all()

    return [PreviousSetRead(set_number=s.set_number, reps=s.reps, weight=s.weight) for s in sets]
