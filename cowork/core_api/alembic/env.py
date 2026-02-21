from __future__ import annotations

import pathlib
import sys
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

load_dotenv()

CORE_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SHARED_ROOT = REPO_ROOT / "shared"
if str(SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_ROOT))

from app import models  # noqa: F401, E402
from app.config import settings  # noqa: E402

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _dialect_name(url: str) -> str:
    return url.split(":", 1)[0].lower()


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    dialect_name = _dialect_name(url)
    config.attributes["dialect_name"] = dialect_name
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        config.attributes["dialect_name"] = connection.dialect.name
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
