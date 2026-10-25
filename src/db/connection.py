"""Database Engine & Session Management with SQLite PRAGMA enforcement."""
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from src.db.models import Base

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "nse_platform.db"


def get_engine(db_url: str = None):
    if db_url is None:
        DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{DEFAULT_DB_PATH}"

    engine = create_engine(db_url, echo=False)

    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.close()

    return engine


def get_session_factory(engine=None):
    if engine is None:
        engine = get_engine()
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db(engine=None):
    """Initializes tables using declarative metadata."""
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(bind=engine)
