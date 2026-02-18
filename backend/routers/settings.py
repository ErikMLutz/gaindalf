from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel, and_, or_, select

from backend.database import get_session
from backend.models import MuscleGroup, MuscleGroupConflict

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


class ConflictRead(SQLModel):
    id: int
    muscle_group_a_id: int
    muscle_group_a_name: str
    muscle_group_b_id: int
    muscle_group_b_name: str


class ConflictCreate(SQLModel):
    muscle_group_a_id: int
    muscle_group_b_id: int


@router.get("/conflicts", response_model=list[ConflictRead])
def list_conflicts(session: SessionDep):
    conflicts = session.exec(select(MuscleGroupConflict)).all()
    result = []
    for conflict in conflicts:
        mg_a = session.get(MuscleGroup, conflict.muscle_group_a_id)
        mg_b = session.get(MuscleGroup, conflict.muscle_group_b_id)
        result.append(
            ConflictRead(
                id=conflict.id,
                muscle_group_a_id=conflict.muscle_group_a_id,
                muscle_group_a_name=mg_a.name,
                muscle_group_b_id=conflict.muscle_group_b_id,
                muscle_group_b_name=mg_b.name,
            )
        )
    return result


@router.post("/conflicts", response_model=ConflictRead, status_code=201)
def create_conflict(body: ConflictCreate, session: SessionDep):
    a_id = body.muscle_group_a_id
    b_id = body.muscle_group_b_id

    if a_id == b_id:
        raise HTTPException(status_code=400, detail="A muscle group cannot conflict with itself")

    mg_a = session.get(MuscleGroup, a_id)
    if mg_a is None:
        raise HTTPException(status_code=404, detail=f"Muscle group {a_id} not found")

    mg_b = session.get(MuscleGroup, b_id)
    if mg_b is None:
        raise HTTPException(status_code=404, detail=f"Muscle group {b_id} not found")

    existing = session.exec(
        select(MuscleGroupConflict).where(
            or_(
                and_(
                    MuscleGroupConflict.muscle_group_a_id == a_id,
                    MuscleGroupConflict.muscle_group_b_id == b_id,
                ),
                and_(
                    MuscleGroupConflict.muscle_group_a_id == b_id,
                    MuscleGroupConflict.muscle_group_b_id == a_id,
                ),
            )
        )
    ).first()

    if existing is not None:
        raise HTTPException(status_code=400, detail="Conflict already exists")

    conflict = MuscleGroupConflict(muscle_group_a_id=a_id, muscle_group_b_id=b_id)
    session.add(conflict)
    session.commit()
    session.refresh(conflict)

    return ConflictRead(
        id=conflict.id,
        muscle_group_a_id=conflict.muscle_group_a_id,
        muscle_group_a_name=mg_a.name,
        muscle_group_b_id=conflict.muscle_group_b_id,
        muscle_group_b_name=mg_b.name,
    )


@router.delete("/conflicts/{conflict_id}", status_code=204)
def delete_conflict(conflict_id: int, session: SessionDep):
    conflict = session.get(MuscleGroupConflict, conflict_id)
    if conflict is None:
        raise HTTPException(status_code=404, detail="Conflict not found")
    session.delete(conflict)
    session.commit()
