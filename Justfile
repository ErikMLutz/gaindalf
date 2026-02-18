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
