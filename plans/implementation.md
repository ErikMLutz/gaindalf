# Gaindalf — Implementation Plan

> Reference: `plans/product.md`

---

## Overview

This document defines the technical implementation strategy for Gaindalf. Every decision is optimized for simplicity, maintainability, and the single-user local use case.

---

## Project Layout

```
gaindalf/
├── Justfile
├── pyproject.toml
├── plans/
│   ├── product.md
│   └── implementation.md
├── backend/
│   ├── __init__.py
│   ├── main.py           # FastAPI app, static file mount, lifespan
│   ├── database.py       # Engine, session factory, table creation
│   ├── models.py         # SQLModel table definitions (single source of truth)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── muscle_groups.py
│   │   ├── lifts.py
│   │   ├── workouts.py
│   │   └── settings.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── algorithm.py  # Intelligent lift selection
│   │   └── indexes.py    # Strength / endurance index calculation
│   └── seed.py           # `just seed` entry point
├── frontend/
│   ├── index.html
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── api.js         # All fetch wrappers (single place to change base URL)
│       ├── app.js         # Tab routing, global init
│       ├── home.js        # Home tab
│       ├── lifts.js       # Lifts tab
│       ├── workouts.js    # Workouts tab
│       └── utils.js       # debounce, formatDate, etc.
└── tests/
    ├── conftest.py         # TestClient, in-memory DB fixture
    ├── test_muscle_groups.py
    ├── test_lifts.py
    ├── test_workouts.py
    ├── test_settings.py
    ├── test_algorithm.py
    └── test_indexes.py
```

---

## Dependency Stack

### Python dependencies (`pyproject.toml`)

```toml
[project]
name = "gaindalf"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlmodel>=0.0.21",         # SQLAlchemy + Pydantic in one, made by FastAPI author
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "httpx>=0.27",              # required by FastAPI TestClient
    "ruff>=0.5",                # linter + formatter (replaces flake8/black/isort)
    "faker>=25",                # realistic fake data for seed script
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]  # errors, pyflakes, isort, pyupgrade

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Why SQLModel over raw `sqlite3`:** SQLModel unifies Pydantic validation (for API I/O) with SQLAlchemy (for DB access) into one class definition. This eliminates the need for separate schema/model layers and gets us free type checking. For a project this size, it's the right level of abstraction.

**Why `uv`:** Fastest resolver, lockfile support, single tool replaces pip + venv + pip-tools.

**Why `ruff`:** Replaces flake8, isort, and black in one binary — 10-100x faster.

### Frontend dependencies (CDN, no build step)

```html
<!-- Chart.js for all graphs -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>

<!-- Google Fonts for the scroll aesthetic -->
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600&family=Lora:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
```

All JS files are loaded as ES modules (`<script type="module" src="js/app.js">`). This allows `import`/`export` without a bundler.

---

## Backend Architecture

### `backend/main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.database import create_db_and_tables
from backend.routers import muscle_groups, lifts, workouts, settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()  # idempotent — creates tables if missing
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(muscle_groups.router, prefix="/api/muscle-groups")
app.include_router(lifts.router, prefix="/api/lifts")
app.include_router(workouts.router, prefix="/api/workouts")
app.include_router(settings.router, prefix="/api/settings")

# Serve frontend static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/{full_path:path}")
async def serve_spa(_: str):
    return FileResponse("frontend/index.html")
```

FastAPI serves both the API and the HTML page. One server, zero CORS complexity.

### `backend/database.py`

```python
from sqlmodel import SQLModel, Session, create_engine

DATABASE_URL = "sqlite:///gaindalf.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Enable WAL mode for better read performance (single-user, still good practice)
with engine.connect() as conn:
    conn.exec_driver_sql("PRAGMA journal_mode=WAL")

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
```

### `backend/models.py`

All SQLModel table classes. These serve as both the ORM models and the Pydantic validation schemas.

```python
from datetime import date
from typing import Optional
from sqlmodel import Field, Relationship, SQLModel

class MuscleGroup(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)

class Lift(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)

class LiftMuscleGroup(SQLModel, table=True):
    lift_id: int = Field(foreign_key="lift.id", primary_key=True)
    muscle_group_id: int = Field(foreign_key="musclegroup.id", primary_key=True)

class Workout(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: date
    subtitle: str = ""

class WorkoutLift(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    workout_id: int = Field(foreign_key="workout.id")
    lift_id: int = Field(foreign_key="lift.id")
    display_order: int = 0

class WorkoutSet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    workout_lift_id: int = Field(foreign_key="workoutlift.id")
    set_number: int
    reps: Optional[int] = None
    weight: Optional[float] = None  # stored in kg; UI can display either unit

class MuscleGroupConflict(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    muscle_group_a_id: int = Field(foreign_key="musclegroup.id")
    muscle_group_b_id: int = Field(foreign_key="musclegroup.id")
```

Separate Pydantic "create/update/read" schemas live alongside or inline in each router file to keep the surface area small.

---

## API Design

All endpoints are prefixed with `/api/`.

### Muscle Groups

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/muscle-groups` | List all |
| `POST` | `/api/muscle-groups` | Create |
| `PATCH` | `/api/muscle-groups/{id}` | Rename |
| `DELETE` | `/api/muscle-groups/{id}` | Delete (cascade) |

### Lifts

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/lifts` | List all with muscle groups |
| `POST` | `/api/lifts` | Create + assign muscle groups |
| `PATCH` | `/api/lifts/{id}` | Rename or update muscle groups |
| `DELETE` | `/api/lifts/{id}` | Delete |

### Workouts

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/workouts` | List (date, subtitle, lift summary) |
| `POST` | `/api/workouts` | Create new (defaults date to today) |
| `GET` | `/api/workouts/{id}` | Full detail (lifts + sets) |
| `PATCH` | `/api/workouts/{id}` | Update subtitle |
| `DELETE` | `/api/workouts/{id}` | Delete |
| `POST` | `/api/workouts/{id}/lifts` | Add a lift to a workout |
| `DELETE` | `/api/workouts/{id}/lifts/{wl_id}` | Remove a lift + its sets |
| `POST` | `/api/workouts/{id}/suggest` | Run intelligent selection algorithm |

### Sets

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/workout-lifts/{wl_id}/sets` | Add a set |
| `PATCH` | `/api/sets/{id}` | Update reps/weight |
| `DELETE` | `/api/sets/{id}` | Delete |

### Settings

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/settings/conflicts` | List conflict pairs |
| `POST` | `/api/settings/conflicts` | Add a conflict pair |
| `DELETE` | `/api/settings/conflicts/{id}` | Remove |

### Analytics

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/analytics/progress` | All workouts with strength + endurance index |
| `GET` | `/api/analytics/lifts/{id}` | Single lift's index history |

---

## Intelligent Lift Selection Algorithm

Lives in `backend/services/algorithm.py`.

```
suggest_lift(workout_id, db):

  1. Get all muscle groups used by lifts already in this workout → used_groups
  2. Get all conflict pairs where either side is in used_groups → conflict_groups
  3. excluded = used_groups ∪ conflict_groups
  4. candidates = all_muscle_groups − excluded
  5. If candidates is empty: candidates = all_muscle_groups − used_groups  (relax conflict constraint)
  6. If candidates is still empty: candidates = all_muscle_groups            (relax all constraints)
  7. For each candidate group, find the date of its most recent workout appearance
  8. Select the group with the oldest (or null) last-trained date
  9. Within that group, find the lift with the oldest last-workout date
  10. Return { muscle_group, lift, previous_sets }  (previous_sets pre-fills the set table)
```

The algorithm is a pure function (takes only DB session + workout_id) making it easy to unit test.

---

## Index Calculation

Lives in `backend/services/indexes.py`.

**Strength Index for a workout:**
```
for each WorkoutLift in workout:
    baseline_weight = max weight recorded in the FIRST ever WorkoutLift for that lift
    current_weight  = max weight in the current WorkoutLift
    if baseline_weight > 0:
        normalized = current_weight / baseline_weight
        add to list

strength_index = mean(list)  # 1.0 = same as baseline, >1.0 = improvement
```

**Endurance Index:** same, but replace weight with `sets × avg_reps × avg_weight` (volume).

Both return `None` if no lifts have a baseline (e.g., the very first workout). The chart handles `None` as a gap in the line.

The analytics endpoints call these services and return arrays of `{ date, strength_index, endurance_index }` ready for Chart.js.

---

## Frontend Architecture

### Single Page Structure (`index.html`)

```html
<body>
  <header>  <!-- logo, nav tabs, settings icon -->
  <main>
    <section id="tab-home">...</section>
    <section id="tab-lifts">...</section>
    <section id="tab-workouts">...</section>
  </main>
  <dialog id="settings-dialog">...</dialog>

  <script type="module" src="js/app.js"></script>
</body>
```

Tab switching: toggle a `.active` class on `<section>` elements. No routing library needed.

### JS Module Structure

**`js/api.js`** — every `fetch` call lives here. One place to change the base URL or add auth later.
```js
const BASE = "/api";
export const api = {
  getWorkouts: () => fetch(`${BASE}/workouts`).then(r => r.json()),
  createWorkout: () => fetch(`${BASE}/workouts`, { method: "POST" }).then(r => r.json()),
  // ... etc
};
```

**`js/utils.js`** — shared helpers:
```js
export function debounce(fn, ms = 400) { ... }
export function formatDate(isoStr) { ... }
```

**`js/app.js`** — entry point:
```js
import { initHome } from "./home.js";
import { initLifts } from "./lifts.js";
import { initWorkouts } from "./workouts.js";

document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  initHome();
  initLifts();
  initWorkouts();
});
```

Each tab module exports a single `init*()` function that wires up event listeners and does the initial data load.

### Auto-save Pattern

All auto-saving uses a debounce. No save button. Visual feedback with a subtle "Saving..." / "Saved" indicator in the corner.

```js
// Example: subtitle field in workout editor
subtitleInput.addEventListener("input", debounce(async (e) => {
  await api.updateWorkout(currentWorkoutId, { subtitle: e.target.value });
  showSavedIndicator();
}, 400));
```

### Searchable Lift Dropdown

Use native `<input>` + `<datalist>`. This gives keyboard navigation and filter-as-you-type for free, degrades gracefully, and requires zero JS beyond populating the datalist options. Style limitations of datalist are acceptable for this internal tool.

If datalist proves too visually limited for the scroll theme, a lightweight custom dropdown (input + filtered ul below) can replace it — but start with datalist.

### Charts (Chart.js)

Both charts (home progress, lift history) are line charts with:
- X axis: `type: 'time'` (Chart.js built-in)
- Y axis: starts at 0, reference line at y=1.0 (`annotations` plugin or a manual dataset)
- Two datasets per chart (strength index, endurance index)
- `spanGaps: false` so missing data shows as a break in the line

```js
new Chart(ctx, {
  type: "line",
  data: {
    datasets: [
      { label: "Strength Index", data: strengthPoints, borderColor: "#8B6914" },
      { label: "Endurance Index", data: endurancePoints, borderColor: "#5C4A1E" },
    ]
  },
  options: {
    scales: {
      x: { type: "time", time: { unit: "week" } },
      y: { min: 0 }
    }
  }
});
```

---

## Visual Theme

CSS variables define the palette:

```css
:root {
  --parchment:     #f5ecd7;
  --parchment-dark: #e8d5b0;
  --ink:           #2c1e0f;
  --ink-light:     #5c4a1e;
  --accent-gold:   #8b6914;
  --accent-red:    #7a2020;
  --border:        #c4a55a;
}
```

Aged paper texture via pure CSS (no image file needed):
```css
body {
  background-color: var(--parchment);
  background-image:
    url("data:image/svg+xml,..."); /* inline SVG noise pattern */
}
```

Headings: `font-family: 'Cinzel', serif` (classical, strong)
Body text: `font-family: 'Lora', serif` (readable, slightly antique)

Decorative dividers: `<hr>` styled with a CSS border pattern or a simple SVG flourish inline in HTML.

---

## Database Notes

- **No migrations framework** (Alembic). `SQLModel.metadata.create_all()` is idempotent and sufficient for a single-user local app. Schema changes are made by dropping and re-seeding the dev DB, or by manual `ALTER TABLE` for production data.
- **WAL mode** enabled at startup for better read concurrency.
- **`check_same_thread=False`** is safe because FastAPI + uvicorn handle concurrency at the async level, not raw threads.
- Weight is stored as `REAL` (float) in kg. The UI can display in lbs with a simple multiplier; no unit conversion stored in the DB.

---

## Seed Script (`backend/seed.py`)

Uses the `Faker` library for names, `random` for variation.

```
Muscle groups (10):
  Chest, Back, Shoulders, Biceps, Triceps, Legs (Quads),
  Legs (Hamstrings), Legs (Glutes), Core, Calves

Lifts (~25): 2-3 per muscle group, realistic names

Conflicts: Biceps ↔ Triceps, Chest ↔ Shoulders (default examples)

Workouts (20):
  - Spread over last 6 months (one every ~9 days)
  - 3-5 lifts per workout, selected to exercise the algorithm
  - Weight follows: base_weight × (1 + 0.02 × workout_number + random(-0.05, 0.05))
  - 5 lifts introduced mid-series (to test empty-state graphs)
```

Run with: `just seed` → calls `python -m backend.seed`. The script drops all data and re-creates it fresh (safe for dev, never run against real data).

---

## Testing Strategy

### `tests/conftest.py`

```python
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from backend.main import app
from backend.database import get_session

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(session):
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()
```

### Test Coverage Targets

**API tests** (`test_workouts.py`, `test_lifts.py`, etc.):
- CRUD happy paths for every resource
- Delete cascades (deleting a workout removes its lifts and sets)
- Input validation (missing required fields → 422)

**Algorithm tests** (`test_algorithm.py`):
- Correct muscle group chosen given known workout history
- Conflict avoidance works; falls back when all groups conflict
- Falls back gracefully with zero workout history
- Within a group, selects least recently used lift

**Index tests** (`test_indexes.py`):
- Correct baseline (first workout = 1.0)
- Handles lifts with no baseline (excluded from average, not crash)
- Handles single-set vs multi-set lifts
- Endurance index increases with more sets × reps × weight

---

## Justfile

```makefile
serve:
    uv run uvicorn backend.main:app --reload --port 8000

test:
    uv run pytest

lint:
    uv run ruff check .
    uv run ruff format --check .

fmt:
    uv run ruff format .

seed:
    uv run python -m backend.seed

backup:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -z "${BACKUP_DIR:-}" ]; then
        echo "Error: BACKUP_DIR environment variable is not set."
        exit 1
    fi
    DEST="$BACKUP_DIR/gaindalf-$(date +%Y%m%d-%H%M%S).db"
    cp gaindalf.db "$DEST"
    echo "Backed up to $DEST"

install:
    uv sync --all-extras
```

---

## Build Order (Suggested Implementation Sequence)

1. **Scaffold** — `pyproject.toml`, `Justfile`, `backend/__init__.py`, `backend/database.py`
2. **Models** — `backend/models.py` (all SQLModel tables)
3. **Core CRUD routers** — muscle groups, lifts, workouts, sets, settings
4. **Services** — `algorithm.py`, `indexes.py`
5. **Analytics endpoints** — uses the services above
6. **Tests** — write alongside or immediately after each layer
7. **Seed script** — `backend/seed.py`
8. **Frontend skeleton** — `index.html`, `style.css`, tab switching
9. **Frontend: Home tab** — progress chart + workout list
10. **Frontend: Lifts tab** — lift history chart + table
11. **Frontend: Workouts tab** — workout editor, lift cards, auto-save
12. **Frontend: Settings dialog** — conflict pair management
13. **Polish** — scroll theme CSS, empty states, error handling

---

## Key Decisions Summary

| Decision | Choice | Rationale |
|---|---|---|
| ORM | SQLModel | Pydantic + SQLAlchemy unified; made for FastAPI |
| Migrations | None (create_all) | Single-user local app; overkill otherwise |
| Linter | ruff | Replaces flake8/black/isort; fastest option |
| JS modules | Native ES modules | No build step required |
| Dropdown | `<datalist>` first | Zero-JS filter-as-you-type; revisit if too limiting |
| Weight unit | kg in DB, UI-agnostic | Single source of truth; easy to add unit toggle later |
| Auto-save delay | 400ms debounce | Fast enough to feel instant; slow enough to batch keystrokes |
| Chart CDN | jsdelivr Chart.js v4 | No build step; pinned major version for stability |
| Static serving | FastAPI StaticFiles | Single server; no CORS; simpler dev setup |
