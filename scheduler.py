"""APScheduler wiring. All jobs are idempotent polls, so a restart simply
resumes polling — no per-event jobs need to be persisted or recreated."""
from __future__ import annotations

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import settings
from services.canvas_sync import sync_canvas
from services.reminder_service import (
    check_assignment_reminders,
    check_lesson_reminders,
    send_evening_briefing,
    send_morning_briefing,
)
from utils.logger import get_logger

logger = get_logger(__name__)


def _job_error_listener(scheduler: AsyncIOScheduler) -> None:
    from apscheduler.events import EVENT_JOB_ERROR, JobExecutionEvent

    def listener(event: JobExecutionEvent) -> None:
        logger.error("Scheduler job %s raised an exception: %s", event.job_id, event.exception)

    scheduler.add_listener(listener, EVENT_JOB_ERROR)


def create_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)

    scheduler.add_job(
        check_lesson_reminders,
        trigger=IntervalTrigger(seconds=60),
        args=[bot],
        id="lesson_reminders",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        check_assignment_reminders,
        trigger=IntervalTrigger(seconds=60),
        args=[bot],
        id="assignment_reminders",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        send_morning_briefing,
        trigger=IntervalTrigger(seconds=60),
        args=[bot],
        id="morning_briefing",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        send_evening_briefing,
        trigger=IntervalTrigger(seconds=60),
        args=[bot],
        id="evening_briefing",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        sync_canvas,
        trigger=IntervalTrigger(minutes=settings.canvas_sync_interval_minutes),
        args=[bot],
        id="canvas_sync",
        max_instances=1,
        coalesce=True,
    )

    _job_error_listener(scheduler)
    return scheduler
