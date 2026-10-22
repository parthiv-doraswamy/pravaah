"""Add structured EVC visit outcome reports.

Revision ID: 20261022_0009
Revises: 20261022_0008
"""

from alembic import op
import sqlalchemy as sa

revision = "20261022_0009"
down_revision = "20261022_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evc_visits", sa.Column("checklist", sa.JSON(), nullable=True))
    op.add_column("evc_visits", sa.Column("outcome_summary", sa.Text(), nullable=True))
    op.add_column("evc_visits", sa.Column("observations", sa.Text(), nullable=True))
    op.add_column(
        "evc_visits",
        sa.Column("report_status", sa.String(length=20), nullable=False, server_default="not_started"),
    )
    op.add_column("evc_visits", sa.Column("report_submitted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("evc_visits", "report_submitted_at")
    op.drop_column("evc_visits", "report_status")
    op.drop_column("evc_visits", "observations")
    op.drop_column("evc_visits", "outcome_summary")
    op.drop_column("evc_visits", "checklist")
