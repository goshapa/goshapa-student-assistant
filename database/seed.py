"""Seeds the real, fixed schedule from the spec (idempotent)."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Course, Lesson
from utils.datetime_utils import parse_time_str
from utils.logger import get_logger

logger = get_logger(__name__)

# weekday: 0 = Monday .. 6 = Sunday
REAL_SCHEDULE = [
    {
        "course_code": "COSC-1570-3T",
        "title": "Mathematics for Computer Science",
        "image_path": "assets/courses/course_math.png",
        "weekday": 0,
        "start_time": "16:30",
        "end_time": "18:50",
        "building": "Tashkent North Hall",
        "room": "305",
        "start_date": date(2026, 8, 24),
        "end_date": date(2026, 12, 18),
    },
    {
        "course_code": "EDEX-1500-5T",
        "title": "Webster 101",
        "image_path": "assets/courses/course_webster101.png",
        "weekday": 1,
        "start_time": "19:00",
        "end_time": "20:30",
        "building": "Tashkent North Hall",
        "room": "407",
        "start_date": date(2026, 8, 24),
        "end_date": date(2026, 10, 16),
    },
    {
        "course_code": "COSC-1520-3T",
        "title": "Computer Programming Concepts",
        "image_path": "assets/courses/course_programming.png",
        "weekday": 2,
        "start_time": "19:00",
        "end_time": "21:20",
        "building": "Tashkent North Hall",
        "room": "115",
        "start_date": date(2026, 8, 24),
        "end_date": date(2026, 12, 18),
    },
    {
        "course_code": "GLBC-1200-5K",
        "title": "Global Cornerstone Seminar",
        "image_path": "assets/courses/course_global_cornerstone.png",
        "weekday": 3,
        "start_time": "11:30",
        "end_time": "13:50",
        "building": "Tashkent West Hall",
        "room": "202",
        "start_date": date(2026, 8, 24),
        "end_date": date(2026, 12, 18),
    },
    {
        "course_code": "SPCM-1040-9T",
        "title": "Public Speaking",
        "image_path": "assets/courses/course_public_speaking.png",
        "weekday": 4,
        "start_time": "11:30",
        "end_time": "13:50",
        "building": "Tashkent West Hall",
        "room": "202",
        "start_date": date(2026, 8, 24),
        "end_date": date(2026, 12, 18),
    },
]


async def seed_initial_schedule(session: AsyncSession) -> None:
    for entry in REAL_SCHEDULE:
        result = await session.execute(
            select(Course).where(Course.course_code == entry["course_code"])
        )
        course = result.scalar_one_or_none()

        if course is None:
            course = Course(
                course_code=entry["course_code"],
                title=entry["title"],
                image_path=entry["image_path"],
            )
            session.add(course)
            await session.flush()
            logger.info("Seeded course %s (%s)", course.title, course.course_code)

        result = await session.execute(
            select(Lesson).where(Lesson.course_id == course.id)
        )
        existing_lesson = result.scalar_one_or_none()

        if existing_lesson is None:
            lesson = Lesson(
                course_id=course.id,
                course_code=entry["course_code"],
                title=entry["title"],
                weekday=entry["weekday"],
                start_time=parse_time_str(entry["start_time"]),
                end_time=parse_time_str(entry["end_time"]),
                building=entry["building"],
                room=entry["room"],
                start_date=entry["start_date"],
                end_date=entry["end_date"],
                is_active=True,
            )
            session.add(lesson)
            logger.info("Seeded lesson for %s", course.title)

    await session.commit()
