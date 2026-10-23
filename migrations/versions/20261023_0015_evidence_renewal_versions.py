"""Add evidence renewal version lineage and lifecycle state.

Revision ID: 20261023_0015
Revises: 20261023_0014
"""
from alembic import op
import sqlalchemy as sa

revision = "20261023_0015"
down_revision = "20261023_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("application_evidence", sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    op.add_column("application_evidence", sa.Column("supersedes_evidence_id", sa.Uuid(), nullable=True))
    op.add_column("application_evidence", sa.Column("lifecycle_status", sa.String(length=20), server_default="current", nullable=False))
    op.create_foreign_key(
        "fk_application_evidence_supersedes_evidence_id",
        "application_evidence",
        "application_evidence",
        ["supersedes_evidence_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_application_evidence_supersedes_evidence_id", "application_evidence", ["supersedes_evidence_id"])
    op.create_index("ix_application_evidence_lifecycle_status", "application_evidence", ["lifecycle_status"])


def downgrade() -> None:
    op.drop_index("ix_application_evidence_lifecycle_status", table_name="application_evidence")
    op.drop_index("ix_application_evidence_supersedes_evidence_id", table_name="application_evidence")
    op.drop_constraint("fk_application_evidence_supersedes_evidence_id", "application_evidence", type_="foreignkey")
    op.drop_column("application_evidence", "lifecycle_status")
    op.drop_column("application_evidence", "supersedes_evidence_id")
    op.drop_column("application_evidence", "version")
