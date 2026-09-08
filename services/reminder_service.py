"""Polls for due lesson/assignment reminders and sends them.

Runs every minute via APScheduler. Uses window-crossing checks (has the
threshold been crossed since the last poll?) combined with the
notification_history dedup guard, so restarts never cause duplicates and a
missed tick simply skips a reminder instead of sending it late.
"""
from __future__ import annotations

from datetime import timedelta
from datetime import timezone as tzutc

from aiogram import Bot
from sqlalchemy import select

from database import async_session_maker
from database.models import Assignment, Course, Settings as SettingsModel
from services.notify import send_with_optional_banner
from services.schedule_service import get_lessons_for_date
from utils.datetime_utils import now_tz, today_tz
from utils.formatting import (
    format_deadline_reminder,
    format_evening_briefing,
    format_lesson_reminder,
    format_missed_deadline,
    format_morning_briefing,
)
from utils.logger import get_logger
from utils.notification_guard import try_record_notification

logger = get_logger(__name__)

POLL_INTERVAL_SECONDS = 60

_LESSON_WINDOWS = [(60, "lesson_reminder_1h"), (15, "lesson_reminder_15m")]
_ASSIGNMENT_WINDOWS = [
    (72 * 60, "assignment_reminder_3d", "3_days"),
    (24 * 60, "assignment_reminder_24h", "24_hours"),
    (6 * 60, "assignment_reminder_6h", "6_hours"),
    (1 * 60, "assignment_reminder_1h", "1_hour"),
]


def _in_window(seconds_left: float, target_minutes: int) -> bool:
    target_seconds = target_minutes * 60
    return target_seconds - POLL_INTERVAL_SECONDS < seconds_left <= target_seconds


async def check_lesson_reminders(bot: Bot) -> None:
    async with async_session_maker() as session:
        settings_row = await session.get(SettingsModel, 1)
        if settings_row is None:
            return

        today = today_tz()
        occurrences = await get_lessons_for_date(session, today)
        now = now_tz()

        for occ in occurrences:
            seconds_left = (occ.start_dt - now).total_seconds()
            if seconds_left <= 0:
                continue

            for minutes, setting_field in _LESSON_WINDOWS:
                if not getattr(settings_row, setting_field):
                    continue
                if not _in_window(seconds_left, minutes):
                    continue

                notification_type = "lesson_1h" if minutes == 60 else "lesson_15m"
                should_send = await try_record_notification(
                    session,
                    notification_type=notification_type,
                    lesson_id=occ.lesson.id,
                    ref_date=occ.occurrence_date,
                )
                if should_send:
                    text = format_lesson_reminder(occ, minutes)
                    await send_with_optional_banner(bot, session, text, occ.course)
                    logger.info(
                        "Sent lesson reminder (%s) for %s", notification_type, occ.course.title
                    )


async def check_assignment_reminders(bot: Bot) -> None:
    async with async_session_maker() as session:
        settings_row = await session.get(SettingsModel, 1)
        if settings_row is None:
            return

        result = await session.execute(
            select(Assignment).where(
                Assignment.is_active.is_(True),
                Assignment.is_submitted.is_(False),
                Assignment.due_at.is_not(None),
            )
        )
        assignments = list(result.scalars().all())
        now = now_tz()

        for assignment in assignments:
            # due_at is stored naive-UTC (SQLite drops tzinfo); compare via UTC-aware now.
            due_utc = (
                assignment.due_at.replace(tzinfo=tzutc.utc)
                if assignment.due_at.tzinfo is None
                else assignment.due_at
            )
            seconds_left = (due_utc - now.astimezone(tzutc.utc)).total_seconds()

            result_c = await session.execute(
                select(Course).where(Course.canvas_course_id == assignment.canvas_course_id)
            )
            course = result_c.scalar_one_or_none()

            if seconds_left <= 0:
                should_send = await try_record_notification(
                    session, notification_type="missed", assignment_id=assignment.id
                )
                if should_send:
                    text = format_missed_deadline(assignment, course)
                    await send_with_optional_banner(bot, session, text, course)
                    logger.info("Sent missed-deadline notice for %s", assignment.name)
                continue

            for minutes, setting_field, kind in _ASSIGNMENT_WINDOWS:
                if not getattr(settings_row, setting_field):
                    continue
                if not _in_window(seconds_left, minutes):
                    continue

                should_send = await try_record_notification(
                    session, notification_type=kind, assignment_id=assignment.id
                )
                if should_send:
                    text = format_deadline_reminder(assignment, course, kind)
                    await send_with_optional_banner(bot, session, text, course)
                    logger.info("Sent assignment reminder (%s) for %s", kind, assignment.name)


def _current_hhmm() -> str:
    return now_tz().strftime("%H:%M")


async def send_morning_briefing(bot: Bot) -> None:
    async with async_session_maker() as session:
        settings_row = await session.get(SettingsModel, 1)
        if settings_row is None or not settings_row.morning_briefing_enabled:
            return
        if settings_row.morning_briefing_time != _current_hhmm():
            return

        today = today_tz()
        should_send = await try_record_notification(
            session, notification_type="morning_briefing", ref_date=today
        )
        if not should_send:
            return

        occurrences = await get_lessons_for_date(session, today)

        result = await session.execute(
            select(Assignment).where(
                Assignment.is_active.is_(True), Assignment.is_submitted.is_(False)
            )
        )
        active = list(result.scalars().all())
        with_due = [a for a in active if a.due_at is not None]
        with_due.sort(key=lambda a: a.due_at)

        due_today = 0
        now = now_tz()
        for a in with_due:
            due_utc = a.due_at.replace(tzinfo=tzutc.utc) if a.due_at.tzinfo is None else a.due_at
            if due_utc.astimezone(now.tzinfo).date() == today:
                due_today += 1

        nearest = with_due[0] if with_due else None

        text = format_morning_briefing(occurrences, len(active), due_today, nearest)
        await send_with_optional_banner(
            bot, session, text, occurrences[0].course if len(occurrences) == 1 else None
        )
        logger.info("Sent morning briefing")


async def send_evening_briefing(bot: Bot) -> None:
    async with async_session_maker() as session:
        settings_row = await session.get(SettingsModel, 1)
        if settings_row is None or not settings_row.evening_briefing_enabled:
            return
        if settings_row.evening_briefing_time != _current_hhmm():
            return

        today = today_tz()
        should_send = await try_record_notification(
            session, notification_type="evening_briefing", ref_date=today
        )
        if not should_send:
            return

        tomorrow = today + timedelta(days=1)
        occurrences = await get_lessons_for_date(session, tomorrow)

        result = await session.execute(
            select(Assignment).where(
                Assignment.is_active.is_(True), Assignment.is_submitted.is_(False)
            )
        )
        active_count = len(list(result.scalars().all()))

        text = format_evening_briefing(occurrences, active_count)
        await send_with_optional_banner(
            bot, session, text, occurrences[0].course if len(occurrences) == 1 else None
        )
        logger.info("Sent evening briefing")
