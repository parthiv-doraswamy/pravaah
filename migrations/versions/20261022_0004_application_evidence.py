"""Add application evidence metadata and expiry fields.

Revision ID: 20261022_0004
Revises: 20261022_0003
"""

from alembic import op
import sqlalchemy as sa

revision = "20261022_0004"
down_revision = "20261022_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("reference_number", sa.String(length=160), nullable=True),
        sa.Column("issued_on", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("policy_key", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_application_evidence_application_id", "application_evidence", ["application_id"])
    op.create_index("ix_application_evidence_category", "application_evidence", ["category"])
    op.create_index("ix_application_evidence_expires_on", "application_evidence", ["expires_on"])
    op.create_index("ix_application_evidence_policy_key", "application_evidence", ["policy_key"])


def downgrade() -> None:
    op.drop_index("ix_application_evidence_policy_key", table_name="application_evidence")
    op.drop_index("ix_application_evidence_expires_on", table_name="application_evidence")
    op.drop_index("ix_application_evidence_category", table_name="application_evidence")
    op.drop_index("ix_application_evidence_application_id", table_name="application_evidence")
    op.drop_table("application_evidence")
