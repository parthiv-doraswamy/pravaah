"""Add persistent in-app notification queue and retry metadata.

Revision ID: 20261022_0005
Revises: 20261022_0004
"""

from alembic import op
import sqlalchemy as sa

revision = "20261022_0005"
down_revision = "20261022_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=True),
        sa.Column("notification_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False),
        sa.Column("delivery_status", sa.String(length=30), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dedupe_key", sa.String(length=240), nullable=False),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["application_evidence.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_notification_dedupe_key"),
    )
    op.create_index("ix_notification_records_recipient_user_id", "notification_records", ["recipient_user_id"])
    op.create_index("ix_notification_records_application_id", "notification_records", ["application_id"])
    op.create_index("ix_notification_records_evidence_id", "notification_records", ["evidence_id"])
    op.create_index("ix_notification_records_notification_type", "notification_records", ["notification_type"])
    op.create_index("ix_notification_records_delivery_status", "notification_records", ["delivery_status"])
    op.create_index("ix_notification_records_next_attempt_at", "notification_records", ["next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_notification_records_next_attempt_at", table_name="notification_records")
    op.drop_index("ix_notification_records_delivery_status", table_name="notification_records")
    op.drop_index("ix_notification_records_notification_type", table_name="notification_records")
    op.drop_index("ix_notification_records_evidence_id", table_name="notification_records")
    op.drop_index("ix_notification_records_application_id", table_name="notification_records")
    op.drop_index("ix_notification_records_recipient_user_id", table_name="notification_records")
    op.drop_table("notification_records")
