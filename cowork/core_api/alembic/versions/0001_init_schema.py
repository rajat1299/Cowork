"""init schema

Revision ID: 0001_init_schema
Revises: 
Create Date: 2025-02-14 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_init_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)

    op.create_table(
        "refreshtoken",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_refreshtoken_user_id", "refreshtoken", ["user_id"], unique=False)
    op.create_index("ix_refreshtoken_token", "refreshtoken", ["token"], unique=True)

    op.create_table(
        "config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("group", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_config_user_id", "config", ["user_id"], unique=False)
    op.create_index("ix_config_group", "config", ["group"], unique=False)
    op.create_index("ix_config_name", "config", ["name"], unique=False)

    op.create_table(
        "session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_session_user_id", "session", ["user_id"], unique=False)
    op.create_index("ix_session_project_id", "session", ["project_id"], unique=True)

    op.create_table(
        "oauthaccount",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_user_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("avatar_url", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_oauthaccount_user_id", "oauthaccount", ["user_id"], unique=False)
    op.create_index("ix_oauthaccount_provider", "oauthaccount", ["provider"], unique=False)
    op.create_index("ix_oauthaccount_provider_user_id", "oauthaccount", ["provider_user_id"], unique=False)

    op.create_table(
        "provider",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider_name", sa.String(), nullable=False),
        sa.Column("model_type", sa.String(), nullable=False),
        sa.Column("api_key", sa.String(), nullable=False),
        sa.Column("endpoint_url", sa.String(), nullable=False),
        sa.Column("encrypted_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("prefer", sa.Boolean(), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provider_user_id", "provider", ["user_id"], unique=False)
    op.create_index("ix_provider_provider_name", "provider", ["provider_name"], unique=False)

    op.create_table(
        "chathistory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=True),
        sa.Column("question", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("model_platform", sa.String(), nullable=False),
        sa.Column("model_type", sa.String(), nullable=False),
        sa.Column("api_key", sa.String(), nullable=True),
        sa.Column("api_url", sa.String(), nullable=True),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("file_save_path", sa.String(), nullable=True),
        sa.Column("installed_mcp", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("project_name", sa.String(), nullable=True),
        sa.Column("summary", sa.String(), nullable=True),
        sa.Column("tokens", sa.Integer(), nullable=False),
        sa.Column("spend", sa.Float(), nullable=False),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chathistory_user_id", "chathistory", ["user_id"], unique=False)
    op.create_index("ix_chathistory_task_id", "chathistory", ["task_id"], unique=True)
    op.create_index("ix_chathistory_project_id", "chathistory", ["project_id"], unique=False)

    op.create_table(
        "chatsnapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("browser_url", sa.String(), nullable=False),
        sa.Column("image_path", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chatsnapshot_user_id", "chatsnapshot", ["user_id"], unique=False)
    op.create_index("ix_chatsnapshot_task_id", "chatsnapshot", ["task_id"], unique=False)

    op.create_table(
        "mcpserver",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("home_page", sa.String(), nullable=True),
        sa.Column("mcp_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("install_command", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mcpserver_key", "mcpserver", ["key"], unique=True)

    op.create_table(
        "mcpuser",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mcp_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("mcp_name", sa.String(), nullable=False),
        sa.Column("mcp_key", sa.String(), nullable=False),
        sa.Column("mcp_desc", sa.String(), nullable=True),
        sa.Column("command", sa.String(), nullable=True),
        sa.Column("args", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("env", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("mcp_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("server_url", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["mcp_id"], ["mcpserver.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mcpuser_user_id", "mcpuser", ["user_id"], unique=False)

    op.create_table(
        "step",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("step", sa.String(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("timestamp", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_step_task_id", "step", ["task_id"], unique=False)
    op.create_index("ix_step_step", "step", ["step"], unique=False)

    op.create_table(
        "artifact",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("artifact_type", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("content_url", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_artifact_task_id", "artifact", ["task_id"], unique=False)
    op.create_index("ix_artifact_artifact_type", "artifact", ["artifact_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_artifact_artifact_type", table_name="artifact")
    op.drop_index("ix_artifact_task_id", table_name="artifact")
    op.drop_table("artifact")

    op.drop_index("ix_step_step", table_name="step")
    op.drop_index("ix_step_task_id", table_name="step")
    op.drop_table("step")

    op.drop_index("ix_mcpuser_user_id", table_name="mcpuser")
    op.drop_table("mcpuser")

    op.drop_index("ix_mcpserver_key", table_name="mcpserver")
    op.drop_table("mcpserver")

    op.drop_index("ix_chatsnapshot_task_id", table_name="chatsnapshot")
    op.drop_index("ix_chatsnapshot_user_id", table_name="chatsnapshot")
    op.drop_table("chatsnapshot")

    op.drop_index("ix_chathistory_project_id", table_name="chathistory")
    op.drop_index("ix_chathistory_task_id", table_name="chathistory")
    op.drop_index("ix_chathistory_user_id", table_name="chathistory")
    op.drop_table("chathistory")

    op.drop_index("ix_provider_provider_name", table_name="provider")
    op.drop_index("ix_provider_user_id", table_name="provider")
    op.drop_table("provider")

    op.drop_index("ix_oauthaccount_provider_user_id", table_name="oauthaccount")
    op.drop_index("ix_oauthaccount_provider", table_name="oauthaccount")
    op.drop_index("ix_oauthaccount_user_id", table_name="oauthaccount")
    op.drop_table("oauthaccount")

    op.drop_index("ix_session_project_id", table_name="session")
    op.drop_index("ix_session_user_id", table_name="session")
    op.drop_table("session")

    op.drop_index("ix_config_name", table_name="config")
    op.drop_index("ix_config_group", table_name="config")
    op.drop_index("ix_config_user_id", table_name="config")
    op.drop_table("config")

    op.drop_index("ix_refreshtoken_token", table_name="refreshtoken")
    op.drop_index("ix_refreshtoken_user_id", table_name="refreshtoken")
    op.drop_table("refreshtoken")

    op.drop_index("ix_user_email", table_name="user")
    op.drop_table("user")
