serve:
    uv run uvicorn backend.main:app --reload --port 8000

test:
    #!/usr/bin/env bash
    uv run pytest
    EXIT=$?
    # exit code 5 = no tests collected (acceptable during scaffolding)
    [ $EXIT -eq 5 ] && exit 0 || exit $EXIT

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
    sqlite3 gaindalf.db ".backup '$DEST'"
    echo "Backed up to $DEST"

install:
    uv sync --all-extras
