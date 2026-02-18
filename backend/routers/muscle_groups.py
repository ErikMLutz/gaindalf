from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

from backend.database import get_session
from backend.models import MuscleGroup

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


class MuscleGroupRead(SQLModel):
    id: int
    name: str


@router.get("", response_model=list[MuscleGroupRead])
def list_muscle_groups(session: SessionDep):
    return session.exec(select(MuscleGroup)).all()


@router.post("", response_model=MuscleGroupRead, status_code=201)
def create_muscle_group(body: MuscleGroupRead, session: SessionDep):
    muscle_group = MuscleGroup(name=body.name)
    session.add(muscle_group)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Name already exists")
    session.refresh(muscle_group)
    return muscle_group


@router.patch("/{id}", response_model=MuscleGroupRead)
def rename_muscle_group(id: int, body: MuscleGroupRead, session: SessionDep):
    muscle_group = session.get(MuscleGroup, id)
    if muscle_group is None:
        raise HTTPException(status_code=404, detail="Muscle group not found")
    muscle_group.name = body.name
    session.add(muscle_group)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Name already exists")
    session.refresh(muscle_group)
    return muscle_group


@router.delete("/{id}", status_code=204)
def delete_muscle_group(id: int, session: SessionDep):
    muscle_group = session.get(MuscleGroup, id)
    if muscle_group is None:
        raise HTTPException(status_code=404, detail="Muscle group not found")
    session.delete(muscle_group)
    session.commit()
