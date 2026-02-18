from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = "sqlite:///gaindalf.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Enable WAL mode for better read performance
with engine.connect() as _conn:
    _conn.exec_driver_sql("PRAGMA journal_mode=WAL")


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
