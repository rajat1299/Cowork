"""add chat messages

Revision ID: 0002_add_chat_messages
Revises: 0001_init_schema
Create Date: 2026-01-26 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_add_chat_messages"
down_revision = "0001_init_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chatmessage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("message_type", sa.String(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chatmessage_user_id", "chatmessage", ["user_id"], unique=False)
    op.create_index("ix_chatmessage_project_id", "chatmessage", ["project_id"], unique=False)
    op.create_index("ix_chatmessage_task_id", "chatmessage", ["task_id"], unique=False)
    op.create_index("ix_chatmessage_role", "chatmessage", ["role"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_chatmessage_role", table_name="chatmessage")
    op.drop_index("ix_chatmessage_task_id", table_name="chatmessage")
    op.drop_index("ix_chatmessage_project_id", table_name="chatmessage")
    op.drop_index("ix_chatmessage_user_id", table_name="chatmessage")
    op.drop_table("chatmessage")
