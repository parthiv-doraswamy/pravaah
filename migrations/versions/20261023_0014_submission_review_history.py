"""Add review metadata and correction lineage to compliance submissions.

Revision ID: 20261023_0014
Revises: 20261023_0013
"""
from alembic import op
import sqlalchemy as sa

revision = "20261023_0014"
down_revision = "20261023_0013"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("compliance_submissions", sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True))
    op.add_column("compliance_submissions", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("compliance_submissions", sa.Column("review_notes", sa.Text(), nullable=True))
    op.add_column("compliance_submissions", sa.Column("supersedes_submission_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_compliance_submissions_reviewed_by_user_id_users", "compliance_submissions", "users", ["reviewed_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_compliance_submissions_supersedes_submission_id", "compliance_submissions", "compliance_submissions", ["supersedes_submission_id"], ["id"], ondelete="SET NULL")

def downgrade() -> None:
    op.drop_constraint("fk_compliance_submissions_supersedes_submission_id", "compliance_submissions", type_="foreignkey")
    op.drop_constraint("fk_compliance_submissions_reviewed_by_user_id_users", "compliance_submissions", type_="foreignkey")
    op.drop_column("compliance_submissions", "supersedes_submission_id")
    op.drop_column("compliance_submissions", "review_notes")
    op.drop_column("compliance_submissions", "reviewed_at")
    op.drop_column("compliance_submissions", "reviewed_by_user_id")
