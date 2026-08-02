"""SQLAlchemy engine and transaction helpers."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session


DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://trading:trading@localhost:5434/trading_statistics"
)


def database_url() -> str:
    """Return the configured PostgreSQL URL with a local-development default."""
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def create_db_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    """Create an application engine without opening a connection eagerly."""
    return create_engine(url or database_url(), echo=echo, pool_pre_ping=True)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Commit a unit of work atomically and roll it back on failure."""
    with Session(engine) as session:
        with session.begin():
            yield session
