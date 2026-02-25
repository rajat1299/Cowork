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


_SQLITE_COMPAT_COLUMNS: dict[str, dict[str, str]] = {
    "skill": {
        "trust_state": "TEXT NOT NULL DEFAULT 'trusted'",
        "security_scan_status": "TEXT NOT NULL DEFAULT 'not_scanned'",
        "security_warnings": "TEXT NOT NULL DEFAULT '[]'",
        "provenance": "TEXT",
        "last_scanned_at": "DATETIME",
    },
    "memorynote": {
        "confidence": "FLOAT NOT NULL DEFAULT 1.0",
        "provenance": "TEXT",
        "auto_generated": "BOOLEAN NOT NULL DEFAULT 0",
        "expires_at": "DATETIME",
    },
}

_SQLITE_COMPAT_INDEXES: dict[str, tuple[str, ...]] = {
    "skill": (
        "CREATE INDEX IF NOT EXISTS ix_skill_trust_state ON skill (trust_state)",
        "CREATE INDEX IF NOT EXISTS ix_skill_security_scan_status ON skill (security_scan_status)",
    ),
    "memorynote": (
        "CREATE INDEX IF NOT EXISTS ix_memorynote_auto_generated ON memorynote (auto_generated)",
        "CREATE INDEX IF NOT EXISTS ix_memorynote_expires_at ON memorynote (expires_at)",
    ),
}


def _sqlite_table_exists(conn, table_name: str) -> bool:
    row = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _sqlite_existing_columns(conn, table_name: str) -> set[str]:
    rows = conn.exec_driver_sql(f"PRAGMA table_info('{table_name}')").fetchall()
    return {str(row[1]) for row in rows}


def ensure_sqlite_schema_compatibility(target_engine=None) -> None:
    resolved_engine = target_engine or engine
    if resolved_engine.dialect.name != "sqlite":
        return

    with resolved_engine.begin() as conn:
        for table_name, required_columns in _SQLITE_COMPAT_COLUMNS.items():
            if not _sqlite_table_exists(conn, table_name):
                continue
            existing = _sqlite_existing_columns(conn, table_name)
            for column_name, ddl in required_columns.items():
                if column_name in existing:
                    continue
                conn.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")
            for index_ddl in _SQLITE_COMPAT_INDEXES.get(table_name, ()):
                conn.exec_driver_sql(index_ddl)


def get_session():
    with Session(engine) as session:
        yield session
