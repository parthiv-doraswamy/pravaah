"""Add policy versions and application event timeline.

Revision ID: 20261022_0003
Revises: 20261022_0002
"""

from alembic import op
import sqlalchemy as sa

revision = "20261022_0003"
down_revision = "20261022_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policy_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("policy_key", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("source_label", sa.String(length=240), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("policy_key", "version", name="uq_policy_key_version"),
    )
    op.create_index("ix_policy_versions_policy_key", "policy_versions", ["policy_key"])
    op.create_index("ix_policy_versions_is_active", "policy_versions", ["is_active"])
    op.create_table(
        "application_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("from_status", sa.String(length=60), nullable=True),
        sa.Column("to_status", sa.String(length=60), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_hash"),
        sa.UniqueConstraint("application_id", "sequence", name="uq_application_event_sequence"),
    )
    op.create_index("ix_application_events_application_id", "application_events", ["application_id"])


def downgrade() -> None:
    op.drop_index("ix_application_events_application_id", table_name="application_events")
    op.drop_table("application_events")
    op.drop_index("ix_policy_versions_is_active", table_name="policy_versions")
    op.drop_index("ix_policy_versions_policy_key", table_name="policy_versions")
    op.drop_table("policy_versions")
