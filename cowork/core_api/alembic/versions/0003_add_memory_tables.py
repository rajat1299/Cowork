"""add memory tables

Revision ID: 0003_add_memory_tables
Revises: 0002_add_chat_messages
Create Date: 2026-01-27 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_add_memory_tables"
down_revision = "0002_add_chat_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "threadsummary",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("summary", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_threadsummary_user_id", "threadsummary", ["user_id"], unique=False)
    op.create_index("ix_threadsummary_project_id", "threadsummary", ["project_id"], unique=False)

    op.create_table(
        "tasksummary",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=True),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("summary", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasksummary_user_id", "tasksummary", ["user_id"], unique=False)
    op.create_index("ix_tasksummary_project_id", "tasksummary", ["project_id"], unique=False)
    op.create_index("ix_tasksummary_task_id", "tasksummary", ["task_id"], unique=False)

    op.create_table(
        "memorynote",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memorynote_user_id", "memorynote", ["user_id"], unique=False)
    op.create_index("ix_memorynote_project_id", "memorynote", ["project_id"], unique=False)
    op.create_index("ix_memorynote_task_id", "memorynote", ["task_id"], unique=False)
    op.create_index("ix_memorynote_category", "memorynote", ["category"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_memorynote_category", table_name="memorynote")
    op.drop_index("ix_memorynote_task_id", table_name="memorynote")
    op.drop_index("ix_memorynote_project_id", table_name="memorynote")
    op.drop_index("ix_memorynote_user_id", table_name="memorynote")
    op.drop_table("memorynote")

    op.drop_index("ix_tasksummary_task_id", table_name="tasksummary")
    op.drop_index("ix_tasksummary_project_id", table_name="tasksummary")
    op.drop_index("ix_tasksummary_user_id", table_name="tasksummary")
    op.drop_table("tasksummary")

    op.drop_index("ix_threadsummary_project_id", table_name="threadsummary")
    op.drop_index("ix_threadsummary_user_id", table_name="threadsummary")
    op.drop_table("threadsummary")
