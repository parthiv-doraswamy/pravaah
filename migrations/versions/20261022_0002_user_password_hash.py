"""Add optional password hash to user records.

Revision ID: 20261022_0002
Revises: 20261022_0001
"""

from alembic import op
import sqlalchemy as sa

revision = "20261022_0002"
down_revision = "20261022_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
