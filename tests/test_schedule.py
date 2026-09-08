"""Schedule regressions against a disposable SQLite database."""
import os
os.environ.setdefault("BOT_TOKEN", "123:test")
os.environ.setdefault("OWNER_TELEGRAM_ID", "1")

from datetime import date, time
import unittest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from database.models import Base, Course, Lesson, LessonException
from services.schedule_service import get_lessons_for_date, get_week_occurrences


class ScheduleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session = async_sessionmaker(self.engine, expire_on_commit=False)()
        course = Course(course_code="TEST", title="Test")
        self.session.add(course)
        await self.session.flush()
        self.lesson = Lesson(course_id=course.id, course_code="TEST", title="Test",
            weekday=0, start_time=time(16, 30), end_time=time(18, 50),
            building="North", room="305", start_date=date(2026, 8, 24),
            end_date=date(2026, 12, 18))
        self.session.add(self.lesson)
        await self.session.commit()

    async def asyncTearDown(self):
        await self.session.close()
        await self.engine.dispose()

    async def move(self, destination):
        exception = LessonException(lesson_id=self.lesson.id, date=date(2026, 9, 14),
            type="rescheduled", new_date=destination, new_start_time=time(11),
            new_end_time=time(12), new_building="West", new_room="202")
        self.session.add(exception)
        await self.session.commit()
        return exception

    async def test_other_weekday_and_regular_following_week(self):
        await self.move(date(2026, 9, 16))
        self.assertEqual(await get_lessons_for_date(self.session, date(2026, 9, 14)), [])
        moved = await get_lessons_for_date(self.session, date(2026, 9, 16))
        self.assertEqual(len(moved), 1)
        self.assertEqual((moved[0].start_time, moved[0].room), (time(11), "202"))
        self.assertEqual(moved[0].start_dt.date(), date(2026, 9, 16))
        regular = await get_lessons_for_date(self.session, date(2026, 9, 21))
        self.assertEqual(regular[0].start_time, time(16, 30))
        week = await get_week_occurrences(self.session, date(2026, 9, 14))
        self.assertEqual(list(week), [date(2026, 9, 16)])

    async def test_same_day_and_legacy_exception(self):
        exception = await self.move(date(2026, 9, 14))
        for destination in [date(2026, 9, 14), None]:
            exception.new_date = destination
            await self.session.commit()
            items = await get_lessons_for_date(self.session, date(2026, 9, 14))
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].start_time, time(11))

    async def test_cancel_moved_lesson(self):
        exception = await self.move(date(2026, 9, 16))
        exception.type = "cancelled"
        await self.session.commit()
        for day in [14, 16]:
            self.assertEqual(await get_lessons_for_date(self.session, date(2026, 9, day)), [])

    async def test_course_end_excludes_moved_lesson(self):
        await self.move(date(2026, 12, 19))
        self.assertEqual(await get_lessons_for_date(self.session, date(2026, 12, 19)), [])
