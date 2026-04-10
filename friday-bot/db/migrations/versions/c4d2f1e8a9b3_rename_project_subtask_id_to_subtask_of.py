"""rename_project_subtask_id_to_subtask_of

Revision ID: c4d2f1e8a9b3
Revises: 115de37d0bcf
Create Date: 2026-04-10 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = 'c4d2f1e8a9b3'
down_revision: Union[str, Sequence[str], None] = '115de37d0bcf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('tasks', 'project_subtask_id', new_column_name='subtask_of')


def downgrade() -> None:
    op.alter_column('tasks', 'subtask_of', new_column_name='project_subtask_id')
