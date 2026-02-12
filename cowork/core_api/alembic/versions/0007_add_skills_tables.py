"""add skills catalog and user skill state

Revision ID: 0007_add_skills_tables
Revises: 0006_add_provider_feature_flags
Create Date: 2026-02-11 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_add_skills_tables"
down_revision = "0006_add_provider_feature_flags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skill",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("skill_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.Column("source", sa.String(), nullable=False, server_default="built_in"),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("storage_path", sa.String(), nullable=True),
        sa.Column("enabled_by_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.UniqueConstraint("skill_id", name="uq_skill_skill_id"),
    )
    op.create_index("ix_skill_skill_id", "skill", ["skill_id"])
    op.create_index("ix_skill_source", "skill", ["source"])

    op.create_table(
        "user_skill_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.UniqueConstraint("user_id", "skill_id", name="uq_user_skill_state_user_skill"),
    )
    op.create_index("ix_user_skill_state_user_id", "user_skill_state", ["user_id"])
    op.create_index("ix_user_skill_state_skill_id", "user_skill_state", ["skill_id"])


def downgrade() -> None:
    op.drop_index("ix_user_skill_state_skill_id", table_name="user_skill_state")
    op.drop_index("ix_user_skill_state_user_id", table_name="user_skill_state")
    op.drop_table("user_skill_state")

    op.drop_index("ix_skill_source", table_name="skill")
    op.drop_index("ix_skill_skill_id", table_name="skill")
    op.drop_table("skill")
