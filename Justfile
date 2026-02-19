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
    #!/usr/bin/env bash
    set -euo pipefail
    echo "WARNING: This will destroy all existing data."
    echo ""
    echo "  [1] Backup then seed (default)"
    echo "  [2] Delete and seed (no backup)"
    echo "  [3] Abort"
    echo ""
    read -r -p "Choice [3]: " CHOICE
    CHOICE="${CHOICE:-3}"
    case "$CHOICE" in
      1)
        if [ -f gaindalf.db ]; then
          BACKUP_DEST="${BACKUP_DIR:-./gaindalf-backup-$(date +%Y%m%d-%H%M%S).db}"
          sqlite3 gaindalf.db ".backup '$BACKUP_DEST'"
          echo "Backed up to $BACKUP_DEST"
        else
          echo "No database found, skipping backup."
        fi
        uv run python -m backend.seed
        ;;
      2)
        rm -f gaindalf.db gaindalf.db-shm gaindalf.db-wal
        uv run python -m backend.seed
        ;;
      3)
        echo "Aborted."
        exit 0
        ;;
      *)
        echo "Invalid choice. Aborting."
        exit 1
        ;;
    esac

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
