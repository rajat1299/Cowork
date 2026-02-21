from pathlib import Path

from sqlmodel import Session, create_engine

from app.config import settings

engine_kwargs: dict = {"echo": False}
if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    if settings.database_url.startswith("sqlite:///"):
        db_path = settings.database_url.removeprefix("sqlite:///")
        if db_path and db_path != ":memory:":
            Path(db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.database_url, **engine_kwargs)


def get_session():
    with Session(engine) as session:
        yield session
