from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session
from ..settings import settings


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=8)
def engine_for(url):
    if url.startswith("sqlite:///"):
        file = url.removeprefix("sqlite:///")
        if file != ":memory:":
            Path(file).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"check_same_thread": False, "timeout": 20}
        if url.startswith("sqlite")
        else {},
    )
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def foreign_keys(dbapi, _):
            dbapi.execute("PRAGMA foreign_keys=ON")

    return engine


def engine():
    return engine_for(settings().database_url)


def initialize():
    if settings().env != "prod":
        Base.metadata.create_all(engine())


@contextmanager
def transaction():
    initialize()
    with Session(engine(), expire_on_commit=False) as session, session.begin():
        yield session
