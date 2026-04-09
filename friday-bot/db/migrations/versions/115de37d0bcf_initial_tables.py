"""initial_tables

Revision ID: 115de37d0bcf
Revises:
Create Date: 2026-04-08 19:14:58.276257

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '115de37d0bcf'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создание всех таблиц."""

    # Пользователи
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("telegram_id", sa.BigInteger, unique=True, nullable=False),
        sa.Column("timezone", sa.String(50), server_default="Europe/Moscow"),
        sa.Column("language", sa.String(10), server_default="ru"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Дефолтные значения уведомлений
    op.create_table(
        "notification_defaults",
        sa.Column("type", sa.String(50), primary_key=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("sound_enabled", sa.Boolean, nullable=False),
        sa.Column("remind_before_min", sa.Integer, nullable=True),
    )

    # Настройки уведомлений пользователя
    op.create_table(
        "notification_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=True),
        sa.Column("sound_enabled", sa.Boolean, nullable=True),
        sa.Column("remind_before_min", sa.Integer, nullable=True),
        sa.UniqueConstraint("user_id", "type"),
    )

    # Тихие дни
    op.create_table(
        "quiet_days",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_of_week", sa.Integer, nullable=True),
        sa.Column("specific_date", sa.Date, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.CheckConstraint("day_of_week IS NOT NULL OR specific_date IS NOT NULL"),
    )

    # Проекты
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("deadline", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Подзадачи проектов
    op.create_table(
        "project_subtasks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("duration_min", sa.Integer, nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("order_index", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Задачи (ежедневное расписание)
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("scheduled_at", sa.DateTime, nullable=True),
        sa.Column("duration_min", sa.Integer, nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("completion_pct", sa.Integer, nullable=True),
        sa.Column("project_subtask_id", sa.Integer, sa.ForeignKey("project_subtasks.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Напоминания
    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("task_id", sa.Integer, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("remind_at", sa.DateTime, nullable=False),
        sa.Column("is_sent", sa.Boolean, server_default=sa.text("false")),
        sa.Column("sound_enabled", sa.Boolean, server_default=sa.text("true")),
    )

    # Ежедневные рефлексии
    op.create_table(
        "daily_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("log_date", sa.Date, nullable=False),
        sa.Column("reflection_text", sa.Text, nullable=True),
        sa.Column("mood", sa.Integer, nullable=True),
        sa.Column("is_quiet_day", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "log_date"),
        sa.CheckConstraint("mood BETWEEN 1 AND 5"),
    )

    # Кэш статистики
    op.create_table(
        "stats_cache",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_type", sa.String(10), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("completion_rate", sa.Float, nullable=True),
        sa.Column("total_tasks", sa.Integer, nullable=True),
        sa.Column("completed_tasks", sa.Integer, nullable=True),
        sa.Column("trend_delta", sa.Float, nullable=True),
        sa.Column("generated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "period_type", "period_start"),
    )

    # Начальные данные notification_defaults
    op.bulk_insert(
        sa.table(
            "notification_defaults",
            sa.column("type", sa.String),
            sa.column("enabled", sa.Boolean),
            sa.column("sound_enabled", sa.Boolean),
            sa.column("remind_before_min", sa.Integer),
        ),
        [
            {"type": "morning_summary",    "enabled": True,  "sound_enabled": True,  "remind_before_min": None},
            {"type": "task_reminder",       "enabled": True,  "sound_enabled": True,  "remind_before_min": 15},
            {"type": "completion_check",    "enabled": True,  "sound_enabled": False, "remind_before_min": None},
            {"type": "window_suggestion",   "enabled": True,  "sound_enabled": False, "remind_before_min": None},
            {"type": "weekly_report",       "enabled": True,  "sound_enabled": False, "remind_before_min": None},
            {"type": "monthly_report",      "enabled": True,  "sound_enabled": False, "remind_before_min": None},
            {"type": "evening_reflection",  "enabled": True,  "sound_enabled": False, "remind_before_min": None},
            {"type": "quiet_day_summary",   "enabled": True,  "sound_enabled": False, "remind_before_min": None},
        ],
    )


def downgrade() -> None:
    """Удаление всех таблиц в обратном порядке."""
    op.drop_table("stats_cache")
    op.drop_table("daily_logs")
    op.drop_table("reminders")
    op.drop_table("tasks")
    op.drop_table("project_subtasks")
    op.drop_table("projects")
    op.drop_table("quiet_days")
    op.drop_table("notification_settings")
    op.drop_table("notification_defaults")
    op.drop_table("users")
