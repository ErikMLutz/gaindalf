# ✦ Gaindalf ✦

A personal weight training tracker with an ancient magic scroll aesthetic. Single-user, runs locally on macOS.

## Stack

- **Backend:** Python + FastAPI + SQLModel (SQLite, WAL mode)
- **Frontend:** Vanilla JS ES modules, Chart.js 4 (CDN), no build step
- **Task runner:** Justfile

## Setup

```bash
just install   # install dependencies
just seed      # populate DB with sample data (destructive)
just serve     # start the dev server at http://localhost:8000
```

## Other commands

```bash
just test      # run pytest
just lint      # ruff check
just fmt       # ruff format
just backup    # copy gaindalf.db to a timestamped backup
```

## Features

- **Home** — strength/endurance progress chart + workout history
- **Lifts** — per-lift progression chart, filterable table, inline name editing, muscle group tagging
- **Workouts** — workout editor with sets/reps/weight, auto-save, and Auto Magic Add (suggests lifts based on muscle group conflicts and recency)
- **Settings** — define muscle group conflicts to inform lift suggestions
