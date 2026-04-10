"""add task_date column for timeless tasks

Revision ID: a3f7c2d1e804
Revises: c4d2f1e8a9b3
Create Date: 2026-04-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3f7c2d1e804'
down_revision: Union[str, Sequence[str], None] = 'c4d2f1e8a9b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавить колонку task_date для хранения даты задачи без времени
    op.add_column(
        "tasks",
        sa.Column("task_date", sa.Date, nullable=True),
    )
    # Заполнить task_date из scheduled_at для существующих задач
    op.execute(
        "UPDATE tasks SET task_date = DATE(scheduled_at) WHERE scheduled_at IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("tasks", "task_date")
