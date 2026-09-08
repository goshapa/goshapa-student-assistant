"""Deadlines and Submitted lists."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from database import get_session
from database.models import Assignment, Course
from keyboards.callback_data import CourseCB
from keyboards.main import BTN_DEADLINES, BTN_SUBMITTED
from keyboards.schedule import back_keyboard
from utils.formatting import format_deadlines, format_submitted

router = Router(name="deadlines")


async def _load_upcoming(session, canvas_course_id: int | None = None) -> list[Assignment]:
    query = select(Assignment).where(
        Assignment.is_active.is_(True),
        Assignment.is_submitted.is_(False),
        Assignment.due_at.is_not(None),
    )
    if canvas_course_id is not None:
        query = query.where(Assignment.canvas_course_id == canvas_course_id)
    result = await session.execute(query)
    assignments = list(result.scalars().all())
    assignments.sort(key=lambda a: a.due_at)
    return assignments


@router.message(Command("deadlines"))
@router.message(F.text == BTN_DEADLINES)
async def show_deadlines(message: Message) -> None:
    async with get_session() as session:
        items = await _load_upcoming(session)
    await message.answer(format_deadlines(items))


@router.callback_query(CourseCB.filter(F.action == "deadlines"))
async def show_course_deadlines(callback: CallbackQuery, callback_data: CourseCB) -> None:
    async with get_session() as session:
        course = await session.get(Course, callback_data.course_id)
        if course is None or course.canvas_course_id is None:
            await callback.message.answer("Для этого курса нет привязанных Canvas-заданий.")
            await callback.answer()
            return
        items = await _load_upcoming(session, course.canvas_course_id)

    await callback.message.answer(format_deadlines(items), reply_markup=back_keyboard("my_courses"))
    await callback.answer()


@router.message(F.text == BTN_SUBMITTED)
async def show_submitted(message: Message) -> None:
    async with get_session() as session:
        result = await session.execute(
            select(Assignment).where(
                Assignment.is_active.is_(True), Assignment.is_submitted.is_(True)
            )
        )
        assignments = list(result.scalars().all())
        assignments.sort(key=lambda a: a.updated_at, reverse=True)

        items = []
        for a in assignments:
            course_result = await session.execute(
                select(Course).where(Course.canvas_course_id == a.canvas_course_id)
            )
            items.append((a, course_result.scalar_one_or_none()))

    await message.answer(format_submitted(items))
