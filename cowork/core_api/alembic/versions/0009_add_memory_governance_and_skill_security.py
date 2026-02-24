"""add memory governance fields and skill security metadata

Revision ID: 0009_add_memory_governance_and_skill_security
Revises: 0008_add_skill_discovery_metadata
Create Date: 2026-02-24 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_add_memory_governance_and_skill_security"
down_revision = "0008_add_skill_discovery_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "memorynote",
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("1.0")),
    )
    op.add_column(
        "memorynote",
        sa.Column("provenance", sa.JSON(), nullable=True),
    )
    op.add_column(
        "memorynote",
        sa.Column("auto_generated", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "memorynote",
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_memorynote_auto_generated", "memorynote", ["auto_generated"])
    op.create_index("ix_memorynote_expires_at", "memorynote", ["expires_at"])

    op.add_column(
        "skill",
        sa.Column("trust_state", sa.String(), nullable=False, server_default="trusted"),
    )
    op.add_column(
        "skill",
        sa.Column("security_scan_status", sa.String(), nullable=False, server_default="not_scanned"),
    )
    op.add_column(
        "skill",
        sa.Column("security_warnings", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.add_column(
        "skill",
        sa.Column("provenance", sa.JSON(), nullable=True),
    )
    op.add_column(
        "skill",
        sa.Column("last_scanned_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_skill_trust_state", "skill", ["trust_state"])
    op.create_index("ix_skill_security_scan_status", "skill", ["security_scan_status"])

    op.alter_column("memorynote", "confidence", server_default=None)
    op.alter_column("memorynote", "auto_generated", server_default=None)
    op.alter_column("skill", "trust_state", server_default=None)
    op.alter_column("skill", "security_scan_status", server_default=None)
    op.alter_column("skill", "security_warnings", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_skill_security_scan_status", table_name="skill")
    op.drop_index("ix_skill_trust_state", table_name="skill")
    op.drop_column("skill", "last_scanned_at")
    op.drop_column("skill", "provenance")
    op.drop_column("skill", "security_warnings")
    op.drop_column("skill", "security_scan_status")
    op.drop_column("skill", "trust_state")

    op.drop_index("ix_memorynote_expires_at", table_name="memorynote")
    op.drop_index("ix_memorynote_auto_generated", table_name="memorynote")
    op.drop_column("memorynote", "expires_at")
    op.drop_column("memorynote", "auto_generated")
    op.drop_column("memorynote", "provenance")
    op.drop_column("memorynote", "confidence")
