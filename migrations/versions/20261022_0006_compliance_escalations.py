"""Add compliance escalation records.

Revision ID: 20261022_0006
Revises: 20261022_0005
"""

from alembic import op
import sqlalchemy as sa

revision = "20261022_0006"
down_revision = "20261022_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "compliance_escalations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=240), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("escalation_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["application_evidence.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_compliance_escalation_dedupe_key"),
    )
    op.create_index("ix_compliance_escalations_application_id", "compliance_escalations", ["application_id"])
    op.create_index("ix_compliance_escalations_evidence_id", "compliance_escalations", ["evidence_id"])
    op.create_index("ix_compliance_escalations_status", "compliance_escalations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_compliance_escalations_status", table_name="compliance_escalations")
    op.drop_index("ix_compliance_escalations_evidence_id", table_name="compliance_escalations")
    op.drop_index("ix_compliance_escalations_application_id", table_name="compliance_escalations")
    op.drop_table("compliance_escalations")
