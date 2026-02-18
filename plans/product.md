# Gaindalf — Product Plan

Gaindalf is a personal weight training tracker for one user, themed as an ancient magic scroll (the wise workout wizard). It runs locally on macOS, accessed primarily via laptop browser, with a responsive layout for future mobile use.

---

## Tech Stack

- **Backend:** Python + FastAPI
- **Database:** SQLite (single file — easy to back up)
- **Frontend:** Vanilla JS + HTML/CSS, no build step
- **Charts:** Chart.js
- **Task runner:** Justfile
- **Dependency management:** uv (Python)

---

## Justfile Operations

| Command | Description |
|---|---|
| `just serve` | Start the dev server |
| `just test` | Run test suite |
| `just lint` | Run linter |
| `just seed` | Seed DB with fake progression data |
| `just backup` | Copy DB file to `$BACKUP_DIR` (errors if unset) |
| `just install` | Install Python dependencies |

### Backup

The `just backup` command copies the SQLite file to the path in `$BACKUP_DIR`. If that variable is not set, it exits with a clear error message. Intended for use with iCloud Drive or any folder.

---

## App Structure

Single HTML page with three tabs. No page reloads.

### Tab 1 — Home (default)

**Top section: Normalized Progress Chart**

Two lines plotted over time (one per workout):
- **Strength index:** For each lift in the workout, divide the recorded weight by the first-ever recorded weight for that lift (baseline = 1.0). Average the normalized values across all lifts. Plot per workout.
- **Endurance index:** Same, but using `sets × reps × weight` instead of weight alone.

Both lines baseline at 1.0. Values above 1.0 mean improvement; below means regression. Only lifts with a recorded baseline (first workout) contribute to the average.

**Bottom section: Workout History List**

Each row shows:
- Date (primary title)
- Optional subtitle (e.g. "Heavy leg day")
- Summary of lifts performed
- Button/click to open in the Workouts tab

---

### Tab 2 — Lifts

**Top section: Lift History Graph**

- Dropdown to select a lift (searchable/filterable)
- Graph showing that lift's strength index and endurance index over time
- If no data yet, shows an empty graph with axes ready

**Bottom section: Lifts Table**

- Filterable table of all lifts
- Columns: name, muscle groups
- Inline editing to rename a lift or change its muscle groups

---

### Tab 3 — Workouts

The workout editor. Displays any workout — past or current. There is no distinction between "active" and "past" workouts; all are equally editable.

**Workout header:**
- Date (auto-set to creation date, not editable)
- Subtitle field (blank by default, free-text, e.g. "Heavy leg day")

**Lift cards:**

Each lift added to the workout appears as a card with:
- **Muscle group dropdown** (pre-filled by intelligent selection, changeable)
- **Lift dropdown** (searchable/filterable, pre-filled by intelligent selection)
  - Changing the muscle group re-runs intelligent lift selection (lift dropdown updates)
  - Changing the lift directly just loads that lift's previous sets/reps/weight
- **Inline lift creation:** If a lift name is typed that doesn't exist, offer to create it (and assign muscle groups on the spot)
- **Sets table:** rows of `reps | weight | delete-button`
  - Auto-populated from the last recorded workout for this lift
  - If no prior data: empty, with just a `+ Set` button
  - `+ Set` adds a new blank row
  - All fields editable inline
- **Mini history graph:** shows this lift's endurance and strength index over time (collapsible or always visible)

**Buttons:**
- `✦ Auto Magic Add` — runs the intelligent algorithm to add a new lift card (muscle group + lift pre-filled)
- `New Workout` — creates a new blank workout and opens it here (also accessible from the Home tab)

**Auto-save:** All changes (subtitle edits, set values, lift additions) are saved automatically in the background with no explicit save button.

---

## Intelligent Lift Selection Algorithm

When `Auto Magic Add` is clicked (or when the muscle group dropdown changes), the algorithm selects a lift using these factors in order:

1. **Avoid already-used muscle groups** in the current workout
2. **Avoid muscle groups that conflict** with already-used ones (user-configured)
3. **Prefer least recently trained muscle group** (by date of last workout containing a lift from that group)
4. **Within that muscle group, prefer least recently done lift**

When the muscle group dropdown is changed manually by the user, only step 4 applies (lift selected for that muscle group).

When the lift dropdown is changed manually, no algorithm runs — the UI just loads that lift's previous sets/reps/weight.

---

## Settings Page

Accessible from a settings icon/link (not a main tab). Contains:

### Muscle Group Conflicts

- List of conflict pairs (e.g. "Arms ↔ Shoulders")
- Add/remove conflict pairs freely
- Default: no conflicts
- Conflicts are bidirectional (A conflicts with B = B conflicts with A)

---

## Data Model (conceptual)

```
MuscleGroup       id, name
Lift              id, name
LiftMuscleGroup   lift_id, muscle_group_id  (many-to-many)
Workout           id, date, subtitle
WorkoutLift       id, workout_id, lift_id, display_order
WorkoutSet        id, workout_lift_id, set_number, reps, weight
MuscleGroupConflict  id, muscle_group_a_id, muscle_group_b_id
```

---

## Seeded Test Data

A `just seed` command populates a fresh database with realistic fake data:

- ~10 muscle groups, ~25 lifts across those groups
- 20 workouts spread over ~6 months
- Each workout has 3–5 lifts
- Clear progression: weight and volume generally increase over time with minor variation
- Some lifts are new mid-way through (to test empty-state graphs)
- Some muscle group conflicts configured
- Designed to exercise all app features: normalization chart, lift history, auto-add algorithm, etc.

---

## Test Coverage

- API endpoint tests (CRUD for workouts, lifts, sets, muscle groups, settings)
- Intelligent selection algorithm unit tests
  - Correct muscle group chosen given workout history
  - Conflict avoidance works
  - Falls back gracefully with no data
- Normalization calculation unit tests
  - Correct baseline
  - Handles missing data
- Seed data generator produces consistent valid data

---

## Visual Theme

"Ancient magic scroll" aesthetic:
- Parchment/sepia color palette
- Serif or fantasy-adjacent font for headings
- Decorative scroll-like borders and dividers
- Subtle aged-paper texture via CSS
- Dark mode not required initially
