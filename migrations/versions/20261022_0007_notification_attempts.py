"""Add notification delivery attempt audit table.

Revision ID: 20261022_0007
Revises: 20261022_0006
"""

from alembic import op
import sqlalchemy as sa

revision = "20261022_0007"
down_revision = "20261022_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["notification_id"], ["notification_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_attempts_notification_id", "notification_attempts", ["notification_id"])


def downgrade() -> None:
    op.drop_index("ix_notification_attempts_notification_id", table_name="notification_attempts")
    op.drop_table("notification_attempts")
