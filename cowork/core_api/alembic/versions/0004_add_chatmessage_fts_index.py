"""add chatmessage fts index

Revision ID: 0004_add_chatmessage_fts_index
Revises: 0003_add_memory_tables
Create Date: 2026-01-28 00:00:00.000000

"""
from __future__ import annotations

from alembic import op

revision = "0004_add_chatmessage_fts_index"
down_revision = "0003_add_memory_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_chatmessage_content_fts "
        "ON chatmessage USING GIN (to_tsvector('english', content))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chatmessage_content_fts")
