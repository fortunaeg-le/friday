"""SQLAlchemy модели — все таблицы из схемы БД."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


class User(Base):
    """Пользователи и их настройки."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow")
    language: Mapped[str] = mapped_column(String(10), default="ru")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Связи
    notification_settings: Mapped[list["NotificationSetting"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    quiet_days: Mapped[list["QuietDay"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    projects: Mapped[list["Project"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    daily_logs: Mapped[list["DailyLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    stats_cache: Mapped[list["StatsCache"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class NotificationDefault(Base):
    """Дефолтные значения уведомлений — системная таблица, заполняется при миграции."""
    __tablename__ = "notification_defaults"

    type: Mapped[str] = mapped_column(String(50), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sound_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    remind_before_min: Mapped[int | None] = mapped_column(Integer, nullable=True)


class NotificationSetting(Base):
    """Настройки уведомлений пользователя. NULL = берётся из notification_defaults."""
    __tablename__ = "notification_settings"
    __table_args__ = (
        UniqueConstraint("user_id", "type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sound_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    remind_before_min: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship(back_populates="notification_settings")


class QuietDay(Base):
    """Тихие дни — по дню недели или конкретной дате."""
    __tablename__ = "quiet_days"
    __table_args__ = (
        CheckConstraint("day_of_week IS NOT NULL OR specific_date IS NOT NULL"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0=пн, 6=вс
    specific_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="quiet_days")


class Project(Base):
    """Проекты пользователя."""
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | completed | archived
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="projects")
    subtasks: Mapped[list["ProjectSubtask"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ProjectSubtask(Base):
    """Подзадачи проектов — ЕДИНСТВЕННОЕ место хранения подзадач."""
    __tablename__ = "project_subtasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | done | skipped
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="subtasks")
    tasks: Mapped[list["Task"]] = relationship(back_populates="project_subtask")


class Task(Base):
    """Задачи ежедневного расписания (НЕ подзадачи проектов)."""
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    task_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # дата задачи (для задач без времени)
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)  # работа | здоровье | личное | другое
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | done | partial | skipped
    completion_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100
    subtask_of: Mapped[int | None] = mapped_column(
        ForeignKey("project_subtasks.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="tasks")
    project_subtask: Mapped["ProjectSubtask | None"] = relationship(back_populates="tasks", foreign_keys=[subtask_of])
    reminders: Mapped[list["Reminder"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class Reminder(Base):
    """Напоминания о задачах."""
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    remind_at: Mapped[datetime] = mapped_column(nullable=False)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    sound_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    task: Mapped["Task"] = relationship(back_populates="reminders")


class DailyLog(Base):
    """Ежедневные рефлексии / итоги тихого дня."""
    __tablename__ = "daily_logs"
    __table_args__ = (
        UniqueConstraint("user_id", "log_date"),
        CheckConstraint("mood BETWEEN 1 AND 5"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    reflection_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    mood: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5
    is_quiet_day: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="daily_logs")


class StatsCache(Base):
    """Кэш статистики — предрассчитанные данные по периодам."""
    __tablename__ = "stats_cache"
    __table_args__ = (
        UniqueConstraint("user_id", "period_type", "period_start"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)  # week | month
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    completion_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_tasks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_tasks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trend_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="stats_cache")
