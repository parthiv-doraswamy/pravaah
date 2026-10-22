"""Add links from EVC reports to registered application evidence.

Revision ID: 20261022_0010
Revises: 20261022_0009
"""

from alembic import op
import sqlalchemy as sa

revision = "20261022_0010"
down_revision = "20261022_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evc_visits", sa.Column("linked_evidence_ids", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("evc_visits", "linked_evidence_ids")
