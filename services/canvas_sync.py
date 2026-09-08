"""Canvas synchronization: fetch courses/assignments, diff against local DB,
notify the owner about new/changed/submitted assignments."""
from __future__ import annotations

import re
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings as app_settings
from database import async_session_maker
from database.models import Assignment, CanvasCourse, Course, Settings as SettingsModel
from keyboards.schedule import open_canvas_keyboard
from services.canvas_api import CanvasAPI, CanvasAPIError, CanvasNotConfigured
from services.notify import send_with_optional_banner
from services.submission_service import apply_submission_update
from utils.datetime_utils import now_tz, parse_canvas_datetime, same_instant
from utils.formatting import (
    format_deadline_changed,
    format_new_assignment,
    format_submitted_notification,
)
from utils.logger import get_logger
from utils.notification_guard import try_record_notification

logger = get_logger(__name__)

_last_sync_failed = False
_sync_lock = asyncio.Lock()


@dataclass
class SyncResult:
    ok: bool
    courses: int = 0
    active_assignments: int = 0
    new_assignments: int = 0
    submitted: int = 0
    error: str | None = None


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


async def _match_local_course(session: AsyncSession, canvas_course: dict) -> Course | None:
    course_code = (canvas_course.get("course_code") or "").strip()
    canvas_course_id = canvas_course.get("id")
    name = (canvas_course.get("name") or "").strip()

    if course_code:
        result = await session.execute(select(Course).where(Course.course_code == course_code))
        match = result.scalar_one_or_none()
        if match:
            return match

    if canvas_course_id:
        result = await session.execute(
            select(Course).where(Course.canvas_course_id == canvas_course_id)
        )
        match = result.scalar_one_or_none()
        if match:
            return match

    if name:
        normalized = _normalize_name(name)
        result = await session.execute(select(Course))
        for course in result.scalars().all():
            if _normalize_name(course.title) == normalized:
                return course

    # Webster includes spaces and a term suffix: COSC 1520 3T FA 2026.
    code_parts = re.split(r"[\s-]+", course_code.upper())
    if len(code_parts) >= 3:
        local_code = "-".join(code_parts[:3])
        result = await session.execute(select(Course).where(Course.course_code == local_code))
        return result.scalar_one_or_none()

    return None


async def sync_canvas(bot: Bot) -> SyncResult:
    async with _sync_lock:
        return await _sync_canvas(bot)


async def _sync_canvas(bot: Bot) -> SyncResult:
    global _last_sync_failed

    try:
        api = CanvasAPI()
    except CanvasNotConfigured:
        logger.info("Canvas sync skipped: not configured")
        return SyncResult(ok=False, error="not_configured")

    async with async_session_maker() as session:
        try:
            canvas_courses_raw = await api.get_active_courses()
        except CanvasAPIError as exc:
            logger.error("Canvas sync failed: %s", exc)
            if not _last_sync_failed:
                _last_sync_failed = True
                await bot.send_message(
                    app_settings.owner_telegram_id,
                    "⚠️ Canvas synchronization failed.\n\n"
                    "Your schedule and existing assignments are still available.\n\n"
                    "Next automatic sync will try again.",
                )
            return SyncResult(ok=False, error=str(exc))

        _last_sync_failed = False

        new_assignments_count = 0
        seen_canvas_assignment_ids: set[int] = set()
        synced_canvas_course_ids: list[int] = []
        partial_failure = False

        for cc_raw in canvas_courses_raw:
            canvas_course_id = cc_raw["id"]
            result = await session.execute(
                select(CanvasCourse).where(CanvasCourse.canvas_course_id == canvas_course_id)
            )
            canvas_course = result.scalar_one_or_none()
            if canvas_course is None:
                canvas_course = CanvasCourse(canvas_course_id=canvas_course_id)
                session.add(canvas_course)

            canvas_course.course_name = cc_raw.get("name") or ""
            canvas_course.course_code = cc_raw.get("course_code")
            canvas_course.enrollment_state = cc_raw.get("workflow_state")

            local_course = await _match_local_course(session, cc_raw)
            if local_course is not None:
                canvas_course.local_course_id = local_course.id
                if local_course.canvas_course_id != canvas_course_id:
                    local_course.canvas_course_id = canvas_course_id

            await session.flush()

            try:
                assignments_raw = await api.get_assignments(canvas_course_id)
            except CanvasAPIError as exc:
                logger.error("Failed to fetch assignments for course %s: %s", canvas_course_id, exc)
                partial_failure = True
                continue
            synced_canvas_course_ids.append(canvas_course_id)

            for a_raw in assignments_raw:
                canvas_assignment_id = a_raw["id"]
                seen_canvas_assignment_ids.add(canvas_assignment_id)

                result = await session.execute(
                    select(Assignment).where(
                        Assignment.canvas_assignment_id == canvas_assignment_id
                    )
                )
                assignment = result.scalar_one_or_none()
                is_new = assignment is None

                old_due_at = assignment.due_at if assignment else None

                if assignment is None:
                    assignment = Assignment(
                        canvas_assignment_id=canvas_assignment_id,
                        canvas_course_id=canvas_course_id,
                    )
                    session.add(assignment)

                assignment.name = a_raw.get("name") or "Untitled assignment"
                assignment.description = a_raw.get("description")
                assignment.due_at = parse_canvas_datetime(a_raw.get("due_at"))
                assignment.unlock_at = parse_canvas_datetime(a_raw.get("unlock_at"))
                assignment.lock_at = parse_canvas_datetime(a_raw.get("lock_at"))
                assignment.html_url = a_raw.get("html_url")
                assignment.points_possible = a_raw.get("points_possible")
                submission_types = a_raw.get("submission_types") or []
                assignment.submission_types = ",".join(submission_types)
                assignment.status = "active"
                assignment.is_active = True

                await session.flush()

                submission_raw = a_raw.get("submission")
                if submission_raw is None:
                    try:
                        submission_raw = await api.get_submission(canvas_course_id, canvas_assignment_id)
                    except CanvasAPIError:
                        submission_raw = None
                        partial_failure = True

                just_submitted = False
                if submission_raw is not None:
                    just_submitted = await apply_submission_update(session, assignment, submission_raw)
                await session.commit()

                local_course = None
                if canvas_course.local_course_id:
                    local_course = await session.get(Course, canvas_course.local_course_id)

                if is_new:
                    new_assignments_count += 1
                    should_send = await try_record_notification(
                        session, notification_type="new_assignment", assignment_id=assignment.id
                    )
                    if should_send:
                        text = format_new_assignment(assignment, local_course)
                        markup = None
                        if assignment.html_url:
                            markup = open_canvas_keyboard(assignment.html_url)
                        await send_with_optional_banner(
                            bot, session, text, local_course, reply_markup=markup
                        )
                elif not same_instant(old_due_at, assignment.due_at):
                    text = format_deadline_changed(assignment, old_due_at, assignment.due_at)
                    await send_with_optional_banner(bot, session, text, local_course)

                if just_submitted:
                    should_send = await try_record_notification(
                        session, notification_type="submitted", assignment_id=assignment.id
                    )
                    if should_send:
                        text = format_submitted_notification(assignment)
                        await send_with_optional_banner(bot, session, text, local_course)

        # Soft-delete assignments that disappeared from Canvas for courses we just synced.
        if synced_canvas_course_ids:
            result = await session.execute(
                select(Assignment).where(
                    Assignment.canvas_course_id.in_(synced_canvas_course_ids),
                    Assignment.is_active.is_(True),
                )
            )
            for assignment in result.scalars().all():
                if assignment.canvas_assignment_id not in seen_canvas_assignment_ids:
                    assignment.is_active = False
                    logger.info(
                        "Assignment %s disappeared from Canvas, marked inactive", assignment.name
                    )

        result = await session.execute(
            select(Assignment).where(
                Assignment.is_active.is_(True), Assignment.is_submitted.is_(False)
            )
        )
        active_assignments = len(result.scalars().all())

        result = await session.execute(
            select(Assignment).where(
                Assignment.is_active.is_(True), Assignment.is_submitted.is_(True)
            )
        )
        submitted_count = len(result.scalars().all())

        settings_row = await session.get(SettingsModel, 1)
        if settings_row is not None and not partial_failure:
            settings_row.last_canvas_sync_at = datetime.now(timezone.utc)

        await session.commit()

        return SyncResult(
            ok=not partial_failure,
            error="partial_sync" if partial_failure else None,
            courses=len(canvas_courses_raw),
            active_assignments=active_assignments,
            new_assignments=new_assignments_count,
            submitted=submitted_count,
        )
