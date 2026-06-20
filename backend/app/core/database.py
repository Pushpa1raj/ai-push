from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_DB_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{_DB_DIR / 'chat.db'}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Safe to call multiple times."""
    import app.models.conversation  # noqa: F401 — ensure models are registered
    import app.models.message  # noqa: F401
    import app.models.memory  # noqa: F401
    import app.models.document  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Migrate existing memories table: add category and importance columns if missing
    from sqlalchemy import text, inspect
    inspector = inspect(engine)
    existing_columns = {col["name"] for col in inspector.get_columns("memories")}
    with engine.connect() as conn:
        if "category" not in existing_columns:
            conn.execute(text("ALTER TABLE memories ADD COLUMN category VARCHAR DEFAULT 'other'"))
            conn.commit()
        if "importance" not in existing_columns:
            conn.execute(text("ALTER TABLE memories ADD COLUMN importance INTEGER DEFAULT 5"))
            conn.commit()
