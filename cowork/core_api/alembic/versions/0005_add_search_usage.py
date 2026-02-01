"""add search usage table

Revision ID: 0005_add_search_usage
Revises: 0004_add_chatmessage_fts_index
Create Date: 2026-01-30 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_add_search_usage"
down_revision = "0004_add_chatmessage_fts_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("requests_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("results_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd_estimate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.UniqueConstraint(
            "user_id",
            "provider",
            "date",
            name="uq_search_usage_user_provider_date",
        ),
    )
    op.create_index("ix_search_usage_user_id", "search_usage", ["user_id"])
    op.create_index("ix_search_usage_provider", "search_usage", ["provider"])
    op.create_index("ix_search_usage_date", "search_usage", ["date"])


def downgrade() -> None:
    op.drop_index("ix_search_usage_date", table_name="search_usage")
    op.drop_index("ix_search_usage_provider", table_name="search_usage")
    op.drop_index("ix_search_usage_user_id", table_name="search_usage")
    op.drop_table("search_usage")
