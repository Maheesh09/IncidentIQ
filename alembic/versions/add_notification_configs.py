"""add notification_configs table

Revision ID: e4a1c83b2f97
Revises: d7f2b91c3e56
Create Date: 2026-07-18

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 'e4a1c83b2f97'
down_revision: Union[str, None] = 'd7f2b91c3e56'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notification_configs',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True),
                  primary_key=True),
        sa.Column('organisation_id', sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('organisations.id'), nullable=False, index=True),
        sa.Column('notification_type', sa.String(20), nullable=False),
        sa.Column('secret_name', sa.String(255), nullable=False),
        sa.Column('config_metadata', JSONB, nullable=True),
        sa.Column('is_active', sa.Integer, nullable=False, default=1),
        sa.Column('created_at', sa.String(50), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.String(50), nullable=True),
        sa.Column('last_notified_at', sa.String(50), nullable=True),
        sa.Column('last_notification_status', sa.String(20), nullable=True),
        sa.UniqueConstraint(
            'organisation_id', 'notification_type',
            name='uq_notification_org_type'
        ),
    )


def downgrade() -> None:
    op.drop_table('notification_configs')