"""add admin_email to organisations

Revision ID: c3d8e2f10a44
Revises: b563f067332d
Create Date: 2026-07-18

"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = 'c3d8e2f10a44'
down_revision: str | None = 'b563f067332d'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'organisations',
        sa.Column('admin_email', sa.String(255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('organisations', 'admin_email')