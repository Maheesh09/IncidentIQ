"""add admin_email to organisations

Revision ID: c3d8e2f10a44
Revises: b563f067332d
Create Date: 2026-07-18

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c3d8e2f10a44'
down_revision: Union[str, None] = 'b563f067332d'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'organisations',
        sa.Column('admin_email', sa.String(255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('organisations', 'admin_email')