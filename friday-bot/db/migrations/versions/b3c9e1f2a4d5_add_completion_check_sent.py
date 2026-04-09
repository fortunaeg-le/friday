"""add_completion_check_sent

Revision ID: b3c9e1f2a4d5
Revises: 115de37d0bcf
Create Date: 2026-04-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3c9e1f2a4d5'
down_revision: Union[str, Sequence[str], None] = '115de37d0bcf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'tasks',
        sa.Column(
            'completion_check_sent',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )


def downgrade() -> None:
    op.drop_column('tasks', 'completion_check_sent')
