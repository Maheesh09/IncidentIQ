"""add error_message to incidents

Revision ID: d7f2b91c3e56
Revises: c3d8e2f10a44
Create Date: 2026-07-18

"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = 'd7f2b91c3e56'
down_revision: str | None = 'c3d8e2f10a44'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'incidents',
        sa.Column('error_message', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('incidents', 'error_message')