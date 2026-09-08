"""SQLAlchemy ORM models (SQLite, async)."""
from __future__ import annotations

import enum
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """The single owner of this private bot."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    """Telegram user id."""
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Course(Base):
    """A local course, used to drive the fixed schedule and course banners."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_code: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    banner_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    canvas_course_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )


class Lesson(Base):
    """A recurring weekly lesson slot for a course."""

    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    course_code: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))

    weekday: Mapped[int] = mapped_column(Integer)
    """0 = Monday .. 6 = Sunday."""
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    building: Mapped[str] = mapped_column(String(255))
    room: Mapped[str] = mapped_column(String(64))

    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    course: Mapped["Course"] = relationship(back_populates="lessons")
    exceptions: Mapped[list["LessonException"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan"
    )


class LessonExceptionType(str, enum.Enum):
    cancelled = "cancelled"
    rescheduled = "rescheduled"


class LessonException(Base):
    """A one-off change (cancellation or reschedule) to a lesson on a specific date."""

    __tablename__ = "lesson_exceptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    date: Mapped[date] = mapped_column(Date)
    type: Mapped[str] = mapped_column(String(32))
    new_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    new_start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    new_end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    new_building: Mapped[str | None] = mapped_column(String(255), nullable=True)
    new_room: Mapped[str | None] = mapped_column(String(64), nullable=True)

    lesson: Mapped["Lesson"] = relationship(back_populates="exceptions")

    __table_args__ = (UniqueConstraint("lesson_id", "date", name="uq_lesson_exception_date"),)


class CanvasCourse(Base):
    """A course as reported by the Canvas API."""

    __tablename__ = "canvas_courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canvas_course_id: Mapped[int] = mapped_column(Integer, unique=True)
    course_name: Mapped[str] = mapped_column(String(255))
    course_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enrollment_state: Mapped[str | None] = mapped_column(String(32), nullable=True)

    local_course_id: Mapped[int | None] = mapped_column(
        ForeignKey("courses.id"), nullable=True
    )


class Assignment(Base):
    """A Canvas assignment mirrored into the local database."""

    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canvas_assignment_id: Mapped[int] = mapped_column(Integer, unique=True)
    canvas_course_id: Mapped[int] = mapped_column(Integer)

    name: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    unlock_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lock_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    html_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    points_possible: Mapped[float | None] = mapped_column(Float, nullable=True)
    submission_types: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    status: Mapped[str] = mapped_column(String(32), default="active")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    """False when the assignment disappeared from Canvas (soft delete)."""

    is_submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_missing: Mapped[bool] = mapped_column(Boolean, default=False)
    is_late: Mapped[bool] = mapped_column(Boolean, default=False)
    is_graded: Mapped[bool] = mapped_column(Boolean, default=False)


class Submission(Base):
    """Latest known submission state for an assignment."""

    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), unique=True)

    workflow_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    late: Mapped[bool] = mapped_column(Boolean, default=False)
    missing: Mapped[bool] = mapped_column(Boolean, default=False)
    graded: Mapped[bool] = mapped_column(Boolean, default=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class NotificationHistory(Base):
    """Record of every notification sent, so restarts never duplicate them."""

    __tablename__ = "notification_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    assignment_id: Mapped[int | None] = mapped_column(
        ForeignKey("assignments.id"), nullable=True
    )
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id"), nullable=True)
    ref_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    """The lesson occurrence date, for lesson reminders."""

    notification_type: Mapped[str] = mapped_column(String(32))

    dedup_key: Mapped[str] = mapped_column(String(255), unique=True)
    """Deterministic key enforcing dedup. NULL columns above cannot be used
    directly in a composite UNIQUE constraint (SQLite treats NULL != NULL),
    so this fully-populated string is the real dedup guard."""

    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Settings(Base):
    """Single-row table holding the owner's preferences."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=1)

    lesson_reminder_1h: Mapped[bool] = mapped_column(Boolean, default=True)
    lesson_reminder_15m: Mapped[bool] = mapped_column(Boolean, default=True)

    assignment_reminder_3d: Mapped[bool] = mapped_column(Boolean, default=True)
    assignment_reminder_24h: Mapped[bool] = mapped_column(Boolean, default=True)
    assignment_reminder_6h: Mapped[bool] = mapped_column(Boolean, default=True)
    assignment_reminder_1h: Mapped[bool] = mapped_column(Boolean, default=True)

    morning_briefing_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    evening_briefing_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    morning_briefing_time: Mapped[str] = mapped_column(String(5), default="09:00")
    evening_briefing_time: Mapped[str] = mapped_column(String(5), default="21:00")

    last_canvas_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
