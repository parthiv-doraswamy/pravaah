"""Add compliance undertaking submission records.

Revision ID: 20261023_0013
Revises: 20261023_0012
"""

from alembic import op
import sqlalchemy as sa

revision = "20261023_0013"
down_revision = "20261023_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "compliance_submissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("submission_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("declaration", sa.Text(), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("submitted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_compliance_submissions_application_id", "compliance_submissions", ["application_id"])
    op.create_index("ix_compliance_submissions_submission_type", "compliance_submissions", ["submission_type"])
    op.create_index("ix_compliance_submissions_status", "compliance_submissions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_compliance_submissions_status", table_name="compliance_submissions")
    op.drop_index("ix_compliance_submissions_submission_type", table_name="compliance_submissions")
    op.drop_index("ix_compliance_submissions_application_id", table_name="compliance_submissions")
    op.drop_table("compliance_submissions")
