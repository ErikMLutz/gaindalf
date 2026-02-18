# Agent Guidelines

Before considering any task done, always validate your work by running:

```
just fmt
just lint
just test
```

Fix any errors before finishing.

---

## Project Overview

**Gaindalf** — a personal weight training tracker, single-user, runs locally on macOS.
Theme: "Ancient magic scroll" (parchment/sepia palette, Cinzel/Lora fonts).

Stack:
- **Backend:** Python + FastAPI + SQLModel (SQLite, WAL mode)
- **Frontend:** Vanilla JS ES modules, Chart.js 4 (CDN), no build step
- **Task runner:** Justfile (`just serve`, `just test`, `just lint`, `just fmt`, `just seed`, `just backup`, `just install`)
- **Linter:** ruff (`E`, `F`, `I`, `UP` rules — `UP045` means use `X | None` not `Optional[X]`)

## Key Files

| Path | Purpose |
|---|---|
| `backend/main.py` | FastAPI app, router mounts, SPA catch-all |
| `backend/models.py` | All SQLModel table definitions |
| `backend/database.py` | Engine creation, `get_session` dependency |
| `backend/routers/` | `muscle_groups`, `lifts`, `workouts`, `sets`, `settings`, `analytics` |
| `backend/services/algorithm.py` | `suggest_lift()` — intelligent lift selection |
| `backend/services/indexes.py` | Strength/endurance index calculation |
| `backend/seed.py` | Deterministic seed data (`random.seed(42)`) |
| `frontend/index.html` | Single HTML page; loads Chart.js + date adapter from CDN |
| `frontend/css/style.css` | All styles (parchment theme, ~1300 lines) |
| `frontend/js/api.js` | All fetch wrappers for every API endpoint |
| `frontend/js/utils.js` | `debounce`, `formatDate`, `showSaved` |
| `frontend/js/app.js` | Tab switching, settings dialog, bootstrap |
| `frontend/js/home.js` | Progress chart + workout history list |
| `frontend/js/lifts.js` | Lift selector, per-lift chart, lifts table |
| `frontend/js/workouts.js` | Workout editor (sets, auto-save, Auto Magic Add) |
| `tests/conftest.py` | Global `session` fixture using `StaticPool` |

## Architecture Patterns

### Backend tests
Each test file creates its own isolated `FastAPI()` app with a `client` fixture that overrides `get_session` with the shared in-memory session. **Must use `StaticPool`** (see `conftest.py`) — TestClient runs in a thread pool and plain `:memory:` would create a separate DB per connection.

```python
@pytest.fixture(name="client")
def client_fixture(session: Session):
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/...")
    test_app.dependency_overrides[get_session] = lambda: session
    return TestClient(test_app)
```

### Router pattern
All routers use:
```python
SessionDep = Annotated[Session, Depends(get_session)]
```

### SPA catch-all
`serve_spa()` in `main.py` takes **no parameters** — adding path params causes FastAPI to treat them as required query params (422 errors).

### Frontend tab refresh
Each JS module registers a refresh callback via `registerTabRefresh(tabName, fn)` from `app.js`. Registered in `DOMContentLoaded` in `app.js`.

### Chart.js time axis
Both charts use `type: 'time'` — requires `chartjs-adapter-date-fns` (loaded from CDN in `index.html` after Chart.js). The `_baseline` dataset convention hides a reference line from legend/tooltip via label prefix filter.

### Auto-save
Set reps/weight and workout subtitle use `debounce(fn, 500)` from `utils.js`. `showSaved()` flashes the `#saved-indicator` element.

### Cross-tab navigation
Home tab dispatches `new CustomEvent('open-workout', { detail: { workoutId } })`. Workouts module listens and loads the workout, then a `.click()` on the workouts tab button activates the tab.

## Common Gotchas

- Ruff `I001`: always sort imports. Run `just fmt` to fix automatically.
- Ruff `UP045`: use `X | None` instead of `Optional[X]`.
- `pytest` exit code 5 (no tests collected) is treated as success in the Justfile.
- The DB file (`gaindalf.db`) is gitignored.
- `just seed` is destructive — drops and recreates all tables.
