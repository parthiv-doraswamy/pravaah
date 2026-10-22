"""Add metadata table for private evidence attachments.

Revision ID: 20261022_0011
Revises: 20261022_0010
"""

from alembic import op
import sqlalchemy as sa

revision = "20261022_0011"
down_revision = "20261022_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=80), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256_hex", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["application_evidence.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_evidence_attachments_application_id", "evidence_attachments", ["application_id"])
    op.create_index("ix_evidence_attachments_evidence_id", "evidence_attachments", ["evidence_id"])


def downgrade() -> None:
    op.drop_index("ix_evidence_attachments_evidence_id", table_name="evidence_attachments")
    op.drop_index("ix_evidence_attachments_application_id", table_name="evidence_attachments")
    op.drop_table("evidence_attachments")
