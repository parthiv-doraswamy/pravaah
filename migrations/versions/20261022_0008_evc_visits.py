"""Add EVC visit scheduling records.

Revision ID: 20261022_0008
Revises: 20261022_0007
"""

from alembic import op
import sqlalchemy as sa

revision = "20261022_0008"
down_revision = "20261022_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evc_visits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("location", sa.String(length=240), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evc_visits_application_id", "evc_visits", ["application_id"])
    op.create_index("ix_evc_visits_scheduled_for", "evc_visits", ["scheduled_for"])
    op.create_index("ix_evc_visits_status", "evc_visits", ["status"])


def downgrade() -> None:
    op.drop_index("ix_evc_visits_status", table_name="evc_visits")
    op.drop_index("ix_evc_visits_scheduled_for", table_name="evc_visits")
    op.drop_index("ix_evc_visits_application_id", table_name="evc_visits")
    op.drop_table("evc_visits")
