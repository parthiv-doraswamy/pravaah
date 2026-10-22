"""Create initial institution, user, and application registry tables.

Revision ID: 20261022_0001
Revises:
Create Date: 2026-10-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261022_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "institutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("region_code", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_institutions_name", "institutions", ["name"], unique=False)
    op.create_index("ix_institutions_code", "institutions", ["code"], unique=True)
    op.create_index("ix_institutions_region_code", "institutions", ["region_code"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=60), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"], unique=False)
    op.create_index("ix_users_institution_id", "users", ["institution_id"], unique=False)

    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_number", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_number"),
    )
    op.create_index("ix_applications_application_number", "applications", ["application_number"], unique=True)
    op.create_index("ix_applications_status", "applications", ["status"], unique=False)
    op.create_index("ix_applications_institution_id", "applications", ["institution_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_applications_institution_id", table_name="applications")
    op.drop_index("ix_applications_status", table_name="applications")
    op.drop_index("ix_applications_application_number", table_name="applications")
    op.drop_table("applications")
    op.drop_index("ix_users_institution_id", table_name="users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_institutions_region_code", table_name="institutions")
    op.drop_index("ix_institutions_code", table_name="institutions")
    op.drop_index("ix_institutions_name", table_name="institutions")
    op.drop_table("institutions")
