"""
Seed the database with realistic fake progression data.
Run with: just seed

WARNING: Drops all existing data before inserting.
"""

import random
from datetime import date, timedelta

from sqlmodel import Session, SQLModel, create_engine, select

from backend.models import (
    Lift,
    LiftMuscleGroup,
    MuscleGroup,
    MuscleGroupConflict,
    Workout,
    WorkoutLift,
    WorkoutSet,
)

# Reproducible data
RANDOM_SEED = 42

# ---------------------------------------------------------------------------
# Lift catalogue
# ---------------------------------------------------------------------------

MUSCLE_GROUPS = [
    "Chest",
    "Back",
    "Shoulders",
    "Biceps",
    "Triceps",
    "Quads",
    "Hamstrings",
    "Glutes",
    "Core",
    "Calves",
]

# Lifts per muscle group. Lifts marked with "*" are introduced mid-series
# (after workout 10) to test empty-state graph behaviour.
LIFTS: dict[str, list[tuple[str, bool]]] = {
    "Chest": [("Bench Press", False), ("Incline Dumbbell Press", False), ("Cable Fly", True)],
    "Back": [("Deadlift", False), ("Pull-up", False), ("Barbell Row", False)],
    "Shoulders": [
        ("Overhead Press", False),
        ("Lateral Raise", False),
        ("Face Pull", True),
    ],
    "Biceps": [("Barbell Curl", False), ("Hammer Curl", True)],
    "Triceps": [("Tricep Pushdown", False), ("Skull Crusher", False)],
    "Quads": [("Squat", False), ("Leg Press", False), ("Bulgarian Split Squat", False)],
    "Hamstrings": [("Romanian Deadlift", False), ("Leg Curl", False)],
    "Glutes": [("Hip Thrust", False), ("Cable Kickback", True)],
    "Core": [("Ab Wheel Rollout", False), ("Hanging Leg Raise", False)],
    "Calves": [("Standing Calf Raise", False), ("Seated Calf Raise", True)],
}

# Base weights in kg (None = bodyweight / reps-only)
BASE_WEIGHTS: dict[str, float | None] = {
    "Bench Press": 80.0,
    "Incline Dumbbell Press": 24.0,
    "Cable Fly": 15.0,
    "Deadlift": 120.0,
    "Pull-up": None,
    "Barbell Row": 70.0,
    "Overhead Press": 50.0,
    "Lateral Raise": 10.0,
    "Face Pull": 20.0,
    "Barbell Curl": 30.0,
    "Hammer Curl": 14.0,
    "Tricep Pushdown": 35.0,
    "Skull Crusher": 25.0,
    "Squat": 100.0,
    "Leg Press": 150.0,
    "Bulgarian Split Squat": 20.0,
    "Romanian Deadlift": 80.0,
    "Leg Curl": 40.0,
    "Hip Thrust": 80.0,
    "Cable Kickback": 15.0,
    "Ab Wheel Rollout": None,
    "Hanging Leg Raise": None,
    "Standing Calf Raise": 60.0,
    "Seated Calf Raise": 40.0,
}

# Muscle group conflict pairs
CONFLICTS = [
    ("Biceps", "Triceps"),
    ("Chest", "Shoulders"),
]

# Workout templates: each entry is a list of muscle group names.
# 20 workouts cycle through these templates.
WORKOUT_TEMPLATES = [
    ["Chest", "Back", "Core"],
    ["Quads", "Hamstrings", "Glutes", "Calves"],
    ["Shoulders", "Biceps", "Triceps"],
    ["Back", "Chest", "Core"],
    ["Quads", "Glutes", "Calves"],
    ["Shoulders", "Triceps", "Biceps"],
    ["Chest", "Back", "Core"],
    ["Hamstrings", "Quads", "Calves", "Glutes"],
    ["Biceps", "Back", "Shoulders"],
    ["Chest", "Triceps", "Core"],
    ["Quads", "Hamstrings", "Glutes"],
    ["Back", "Biceps", "Calves"],
    ["Chest", "Shoulders", "Core"],
    ["Quads", "Glutes", "Hamstrings", "Calves"],
    ["Triceps", "Back", "Shoulders"],
    ["Chest", "Core", "Back"],
    ["Quads", "Calves", "Glutes"],
    ["Shoulders", "Biceps", "Triceps"],
    ["Chest", "Back", "Core"],
    ["Quads", "Hamstrings", "Calves"],
]

SUBTITLES = [
    "Heavy push day",
    "Leg destroyer",
    "Arm pump",
    "Back and chest",
    "Lower body",
    "Upper body",
    "Full send",
    "Deload day",
    "",
    "PR attempt",
    "",
    "Volume day",
    "Hypertrophy focus",
    "",
    "Strength focus",
    "Quick session",
    "",
    "Pre-holiday grind",
    "Back at it",
    "Season finale",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _progression_weight(base: float, workout_idx: int, rng: random.Random) -> float:
    """Progressive overload with realistic noise. Rounds to nearest 2.5 kg."""
    factor = 1.0 + 0.025 * workout_idx + rng.uniform(-0.05, 0.05)
    return round(base * factor / 2.5) * 2.5


def _progression_reps(workout_idx: int, rng: random.Random) -> int:
    """Reps for bodyweight lifts — starts at 5, trends up."""
    base = 5 + workout_idx // 3
    return max(1, base + rng.randint(-1, 1))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def seed() -> None:
    rng = random.Random(RANDOM_SEED)

    engine = create_engine("sqlite:///gaindalf.db", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # ------------------------------------------------------------------
        # Wipe existing data (order matters for FK constraints)
        # ------------------------------------------------------------------
        for model in [
            WorkoutSet,
            WorkoutLift,
            Workout,
            MuscleGroupConflict,
            LiftMuscleGroup,
            Lift,
            MuscleGroup,
        ]:
            for row in session.exec(select(model)).all():
                session.delete(row)
        session.commit()
        print("Cleared existing data.")

        # ------------------------------------------------------------------
        # Muscle groups
        # ------------------------------------------------------------------
        mg_map: dict[str, MuscleGroup] = {}
        for name in MUSCLE_GROUPS:
            mg = MuscleGroup(name=name)
            session.add(mg)
            mg_map[name] = mg
        session.commit()
        for mg in mg_map.values():
            session.refresh(mg)
        print(f"Created {len(mg_map)} muscle groups.")

        # ------------------------------------------------------------------
        # Lifts
        # ------------------------------------------------------------------
        lift_map: dict[str, Lift] = {}
        lift_late: set[str] = set()  # lifts introduced after workout 10

        for group_name, lifts in LIFTS.items():
            for lift_name, is_late in lifts:
                lift = Lift(name=lift_name)
                session.add(lift)
                lift_map[lift_name] = lift
                if is_late:
                    lift_late.add(lift_name)
        session.commit()
        for lift in lift_map.values():
            session.refresh(lift)

        for group_name, lifts in LIFTS.items():
            for lift_name, _ in lifts:
                link = LiftMuscleGroup(
                    lift_id=lift_map[lift_name].id,
                    muscle_group_id=mg_map[group_name].id,
                )
                session.add(link)
        session.commit()
        print(f"Created {len(lift_map)} lifts.")

        # ------------------------------------------------------------------
        # Conflicts
        # ------------------------------------------------------------------
        for name_a, name_b in CONFLICTS:
            conflict = MuscleGroupConflict(
                muscle_group_a_id=mg_map[name_a].id,
                muscle_group_b_id=mg_map[name_b].id,
            )
            session.add(conflict)
        session.commit()
        print(f"Created {len(CONFLICTS)} muscle group conflicts.")

        # ------------------------------------------------------------------
        # Workouts (20 spread over ~6 months)
        # ------------------------------------------------------------------
        start_date = date.today() - timedelta(days=180)
        interval_days = 9  # ~one every 9 days

        # Map: lift_name → list of lifts available for early workouts (non-late)
        early_lifts_by_group: dict[str, list[str]] = {}
        all_lifts_by_group: dict[str, list[str]] = {}
        for group_name, lifts in LIFTS.items():
            early_lifts_by_group[group_name] = [n for n, late in lifts if not late]
            all_lifts_by_group[group_name] = [n for n, _ in lifts]

        for workout_idx, template in enumerate(WORKOUT_TEMPLATES):
            workout_date = start_date + timedelta(days=workout_idx * interval_days)
            is_late = workout_idx >= 10  # after workout 10, all lifts are available
            subtitle = SUBTITLES[workout_idx]

            workout = Workout(date=workout_date, subtitle=subtitle)
            session.add(workout)
            session.commit()
            session.refresh(workout)

            for order, group_name in enumerate(template):
                pool = (
                    all_lifts_by_group[group_name] if is_late else early_lifts_by_group[group_name]
                )
                if not pool:
                    continue
                lift_name = rng.choice(pool)
                lift = lift_map[lift_name]

                wl = WorkoutLift(
                    workout_id=workout.id,
                    lift_id=lift.id,
                    display_order=order,
                )
                session.add(wl)
                session.commit()
                session.refresh(wl)

                base = BASE_WEIGHTS.get(lift_name)
                num_sets = rng.randint(3, 4)

                for set_num in range(1, num_sets + 1):
                    if base is None:
                        # Bodyweight lift
                        ws = WorkoutSet(
                            workout_lift_id=wl.id,
                            set_number=set_num,
                            reps=_progression_reps(workout_idx, rng),
                            weight=None,
                        )
                    else:
                        ws = WorkoutSet(
                            workout_lift_id=wl.id,
                            set_number=set_num,
                            reps=rng.randint(5, 10),
                            weight=_progression_weight(base, workout_idx, rng),
                        )
                    session.add(ws)

            session.commit()

        print(f"Created {len(WORKOUT_TEMPLATES)} workouts.")
        print("Seed complete! ✦")


if __name__ == "__main__":
    seed()
