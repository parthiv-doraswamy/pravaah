"""Add a schema version for policy rule JSON.

Revision ID: 20261023_0012
Revises: 20261022_0011
"""

from alembic import op
import sqlalchemy as sa

revision = "20261023_0012"
down_revision = "20261022_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "policy_versions",
        sa.Column("rules_schema_version", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("policy_versions", "rules_schema_version")
