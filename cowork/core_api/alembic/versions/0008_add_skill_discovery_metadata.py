"""add discovery metadata columns for skills

Revision ID: 0008_add_skill_discovery_metadata
Revises: 0007_add_skills_tables
Create Date: 2026-02-12 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_add_skill_discovery_metadata"
down_revision = "0007_add_skills_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "skill",
        sa.Column("domains", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.add_column(
        "skill",
        sa.Column("trigger_keywords", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.add_column(
        "skill",
        sa.Column("trigger_extensions", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.alter_column("skill", "domains", server_default=None)
    op.alter_column("skill", "trigger_keywords", server_default=None)
    op.alter_column("skill", "trigger_extensions", server_default=None)


def downgrade() -> None:
    op.drop_column("skill", "trigger_extensions")
    op.drop_column("skill", "trigger_keywords")
    op.drop_column("skill", "domains")
