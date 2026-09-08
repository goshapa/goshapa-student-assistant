"""Resolves the effective schedule (recurring lessons + exceptions) for dates."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Course, Lesson, LessonException
from utils.datetime_utils import combine_date_time


@dataclass
class LessonOccurrence:
    lesson: Lesson
    course: Course
    occurrence_date: date
    start_time: time
    end_time: time
    building: str
    room: str
    rescheduled: bool = False
    original_date: date | None = None

    @property
    def start_dt(self) -> datetime:
        return combine_date_time(self.occurrence_date, self.start_time)

    @property
    def end_dt(self) -> datetime:
        return combine_date_time(self.occurrence_date, self.end_time)


async def _load_active_lessons(session: AsyncSession) -> list[Lesson]:
    result = await session.execute(
        select(Lesson).where(Lesson.is_active.is_(True))
    )
    return list(result.scalars().all())


async def get_lessons_for_date(
    session: AsyncSession, target_date: date
) -> list[LessonOccurrence]:
    """All lessons effectively happening on target_date, exceptions applied."""
    lessons = await _load_active_lessons(session)
    occurrences: list[LessonOccurrence] = []

    for lesson in lessons:
        if not (lesson.start_date <= target_date <= lesson.end_date):
            continue

        result = await session.execute(
            select(LessonException).where(
                LessonException.lesson_id == lesson.id,
            )
        )
        exceptions = list(result.scalars().all())
        exception = next((e for e in exceptions if e.date == target_date), None)

        course_result = await session.execute(
            select(Course).where(Course.id == lesson.course_id)
        )
        course = course_result.scalar_one()

        arrivals = [e for e in exceptions if e.type == "rescheduled"
                    and (e.new_date or e.date) == target_date
                    and lesson.start_date <= e.date <= lesson.end_date]
        for moved in arrivals:
            occurrences.append(
                LessonOccurrence(
                    lesson=lesson,
                    course=course,
                    occurrence_date=target_date,
                    start_time=moved.new_start_time or lesson.start_time,
                    end_time=moved.new_end_time or lesson.end_time,
                    building=moved.new_building or lesson.building,
                    room=moved.new_room or lesson.room,
                    rescheduled=True,
                    original_date=moved.date,
                )
            )
        if lesson.weekday == target_date.weekday() and exception is None:
            occurrences.append(
                LessonOccurrence(
                    lesson=lesson,
                    course=course,
                    occurrence_date=target_date,
                    start_time=lesson.start_time,
                    end_time=lesson.end_time,
                    building=lesson.building,
                    room=lesson.room,
                    original_date=target_date,
                )
            )

    occurrences.sort(key=lambda occ: occ.start_time)
    return occurrences


async def get_week_occurrences(
    session: AsyncSession, week_start: date
) -> dict[date, list[LessonOccurrence]]:
    """Monday..Sunday occurrences for the week containing week_start's Monday."""
    monday = week_start - timedelta(days=week_start.weekday())
    result: dict[date, list[LessonOccurrence]] = {}
    for i in range(7):
        day = monday + timedelta(days=i)
        occs = await get_lessons_for_date(session, day)
        if occs:
            result[day] = occs
    return result


async def get_next_occurrence_for_course(
    session: AsyncSession, course_id: int, after: datetime, horizon_days: int = 30
) -> LessonOccurrence | None:
    for offset in range(horizon_days):
        day = after.date() + timedelta(days=offset)
        occs = await get_lessons_for_date(session, day)
        for occ in occs:
            if occ.course.id == course_id and occ.start_dt > after:
                return occ
    return None


async def get_all_courses(session: AsyncSession) -> list[Course]:
    result = await session.execute(select(Course).order_by(Course.id))
    return list(result.scalars().all())


async def get_course_by_id(session: AsyncSession, course_id: int) -> Course | None:
    return await session.get(Course, course_id)
