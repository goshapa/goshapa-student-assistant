"""Today / Tomorrow / Week / My Courses / course card."""
from __future__ import annotations

from datetime import timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from database import get_session
from keyboards.callback_data import CourseCB, NavCB
from keyboards.main import BTN_MY_COURSES, BTN_TODAY, BTN_TOMORROW, BTN_WEEK
from keyboards.schedule import course_card_keyboard, my_courses_keyboard
from services.notify import send_with_optional_banner
from services.schedule_service import (
    get_all_courses,
    get_course_by_id,
    get_lessons_for_date,
    get_next_occurrence_for_course,
    get_week_occurrences,
)
from utils.datetime_utils import now_tz, today_tz
from utils.formatting import format_course_card, format_today_message, format_tomorrow_message, format_week_message

router = Router(name="schedule")


@router.message(Command("today"))
@router.message(F.text == BTN_TODAY)
async def show_today(message: Message) -> None:
    today = today_tz()
    async with get_session() as session:
        occurrences = await get_lessons_for_date(session, today)
        text = format_today_message(occurrences, today)
        course = occurrences[0].course if len(occurrences) == 1 else None
        await send_with_optional_banner(message.bot, session, text, course)


@router.message(Command("tomorrow"))
@router.message(F.text == BTN_TOMORROW)
async def show_tomorrow(message: Message) -> None:
    tomorrow = today_tz() + timedelta(days=1)
    async with get_session() as session:
        occurrences = await get_lessons_for_date(session, tomorrow)
        text = format_tomorrow_message(occurrences)
        course = occurrences[0].course if len(occurrences) == 1 else None
        await send_with_optional_banner(message.bot, session, text, course)


@router.message(Command("week"))
@router.message(F.text == BTN_WEEK)
async def show_week(message: Message) -> None:
    async with get_session() as session:
        week = await get_week_occurrences(session, today_tz())
        text = format_week_message(week)
    await message.answer(text)


@router.message(F.text == BTN_MY_COURSES)
async def show_my_courses(message: Message) -> None:
    async with get_session() as session:
        courses = await get_all_courses(session)
    await message.answer("🎓 MY COURSES", reply_markup=my_courses_keyboard(courses))


async def _send_course_card(callback: CallbackQuery, course_id: int) -> None:
    async with get_session() as session:
        course = await get_course_by_id(session, course_id)
        if course is None:
            await callback.answer("Course not found", show_alert=True)
            return
        occ = await get_next_occurrence_for_course(session, course_id, now_tz())
        text = format_course_card(course, occ)
        await send_with_optional_banner(
            callback.bot, session, text, course, reply_markup=course_card_keyboard(course_id)
        )
    await callback.answer()


@router.callback_query(CourseCB.filter(F.action == "view"))
async def on_course_view(callback: CallbackQuery, callback_data: CourseCB) -> None:
    await _send_course_card(callback, callback_data.course_id)


@router.callback_query(CourseCB.filter(F.action == "next"))
async def on_course_next(callback: CallbackQuery, callback_data: CourseCB) -> None:
    async with get_session() as session:
        course = await get_course_by_id(session, callback_data.course_id)
        occ = await get_next_occurrence_for_course(session, callback_data.course_id, now_tz())
        if occ is None:
            await callback.message.answer(f"У курса {course.title} нет предстоящих занятий.")
        else:
            text = format_course_card(course, occ)
            await send_with_optional_banner(callback.bot, session, text, course)
    await callback.answer()


@router.callback_query(NavCB.filter(F.target == "my_courses"))
async def on_back_to_courses(callback: CallbackQuery) -> None:
    async with get_session() as session:
        courses = await get_all_courses(session)
    await callback.message.answer("🎓 MY COURSES", reply_markup=my_courses_keyboard(courses))
    await callback.answer()
