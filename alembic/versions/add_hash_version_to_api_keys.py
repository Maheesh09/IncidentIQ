"""add hash_version to api_keys

Revision ID: f8b3d24c9e71
Revises: e4a1c83b2f97
Create Date: 2026-08-01

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f8b3d24c9e71'
down_revision: Union[str, None] = 'e4a1c83b2f97'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    # server_default="1" backfills all existing rows with version 1
    # (the SHA-256 scheme they were created under). New HMAC keys will
    # be written with version 2 by the application.
    op.add_column(
        'api_keys',
        sa.Column(
            'hash_version',
            sa.Integer(),
            nullable=False,
            server_default="1",
        )
    )


def downgrade() -> None:
    op.drop_column('api_keys', 'hash_version')