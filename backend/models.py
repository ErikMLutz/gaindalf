from datetime import date

from sqlmodel import Field, SQLModel


class MuscleGroup(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)


class Lift(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)


class LiftMuscleGroup(SQLModel, table=True):
    lift_id: int = Field(foreign_key="lift.id", primary_key=True)
    muscle_group_id: int = Field(foreign_key="musclegroup.id", primary_key=True)


class Workout(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    date: date
    subtitle: str = ""


class WorkoutLift(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    workout_id: int = Field(foreign_key="workout.id")
    lift_id: int = Field(foreign_key="lift.id")
    display_order: int = 0


class WorkoutSet(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    workout_lift_id: int = Field(foreign_key="workoutlift.id")
    set_number: int
    reps: int | None = None
    weight: float | None = None  # stored in kg


class MuscleGroupConflict(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    muscle_group_a_id: int = Field(foreign_key="musclegroup.id")
    muscle_group_b_id: int = Field(foreign_key="musclegroup.id")
