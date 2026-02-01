"""add provider feature flags

Revision ID: 0006_add_provider_feature_flags
Revises: 0005_add_search_usage
Create Date: 2026-01-30 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_add_provider_feature_flags"
down_revision = "0005_add_search_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_feature_flags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("native_web_search_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("image_generation_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("audio_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("tool_use_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("browser_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("extra_params_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["provider_id"], ["provider.id"]),
        sa.UniqueConstraint(
            "user_id",
            "provider_id",
            "model",
            name="uq_provider_feature_flags_user_provider_model",
        ),
    )
    op.create_index("ix_provider_feature_flags_user_id", "provider_feature_flags", ["user_id"])
    op.create_index(
        "ix_provider_feature_flags_provider_id",
        "provider_feature_flags",
        ["provider_id"],
    )
    op.create_index("ix_provider_feature_flags_model", "provider_feature_flags", ["model"])


def downgrade() -> None:
    op.drop_index("ix_provider_feature_flags_model", table_name="provider_feature_flags")
    op.drop_index("ix_provider_feature_flags_provider_id", table_name="provider_feature_flags")
    op.drop_index("ix_provider_feature_flags_user_id", table_name="provider_feature_flags")
    op.drop_table("provider_feature_flags")
