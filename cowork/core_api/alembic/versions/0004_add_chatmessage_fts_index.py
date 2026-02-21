"""add chatmessage fts index

Revision ID: 0004_add_chatmessage_fts_index
Revises: 0003_add_memory_tables
Create Date: 2026-01-28 00:00:00.000000

"""
from __future__ import annotations

from alembic import context, op

revision = "0004_add_chatmessage_fts_index"
down_revision = "0003_add_memory_tables"
branch_labels = None
depends_on = None


def _dialect_name() -> str:
    migration_context = context.get_context()
    if migration_context is not None and migration_context.dialect is not None:
        return migration_context.dialect.name
    bind = op.get_bind()
    if bind is None:
        return "unknown"
    return bind.dialect.name


def upgrade() -> None:
    dialect_name = _dialect_name()
    if dialect_name == "postgresql":
        op.execute(
            "CREATE INDEX ix_chatmessage_content_fts "
            "ON chatmessage USING GIN (to_tsvector('english', content))"
        )
        return

    if dialect_name == "sqlite":
        op.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS chatmessage_fts
            USING fts5(content)
            """
        )
        op.execute(
            """
            CREATE TRIGGER IF NOT EXISTS chatmessage_fts_ai
            AFTER INSERT ON chatmessage
            BEGIN
                INSERT INTO chatmessage_fts(rowid, content) VALUES (new.id, new.content);
            END
            """
        )
        op.execute(
            """
            CREATE TRIGGER IF NOT EXISTS chatmessage_fts_ad
            AFTER DELETE ON chatmessage
            BEGIN
                DELETE FROM chatmessage_fts WHERE rowid = old.id;
            END
            """
        )
        op.execute(
            """
            CREATE TRIGGER IF NOT EXISTS chatmessage_fts_au
            AFTER UPDATE OF content ON chatmessage
            BEGIN
                DELETE FROM chatmessage_fts WHERE rowid = old.id;
                INSERT INTO chatmessage_fts(rowid, content) VALUES (new.id, new.content);
            END
            """
        )
        op.execute(
            """
            INSERT INTO chatmessage_fts(rowid, content)
            SELECT id, content
            FROM chatmessage
            """
        )


def downgrade() -> None:
    dialect_name = _dialect_name()
    if dialect_name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_chatmessage_content_fts")
        return

    if dialect_name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS chatmessage_fts_ai")
        op.execute("DROP TRIGGER IF EXISTS chatmessage_fts_ad")
        op.execute("DROP TRIGGER IF EXISTS chatmessage_fts_au")
        op.execute("DROP TABLE IF EXISTS chatmessage_fts")
