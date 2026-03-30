from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = "sqlite:///gaindalf.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Enable WAL mode for better read performance
with engine.connect() as _conn:
    _conn.exec_driver_sql("PRAGMA journal_mode=WAL")


def _run_migrations(engine) -> None:
    with engine.connect() as conn:
        for stmt in [
            "ALTER TABLE workoutlift ADD COLUMN notes TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE workoutset ADD COLUMN done INTEGER NOT NULL DEFAULT 0",
        ]:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass  # column already exists


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _run_migrations(engine)


def get_session():
    with Session(engine) as session:
        yield session
