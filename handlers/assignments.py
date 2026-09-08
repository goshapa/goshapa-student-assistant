"""Active assignments list, overall and per-course."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from database import get_session
from database.models import Assignment, Course
from keyboards.callback_data import CourseCB, AssignmentCB, AssignmentListCB
from keyboards.main import BTN_ASSIGNMENTS
from utils.datetime_utils import to_tz, deadline_status_emoji
from services.assignment_details import assignment_pages
from services.notify import send_with_optional_banner
from html import escape

router = Router(name="assignments")


async def send_list(message, course_id=0, page=0):
    async with get_session() as session:
        course = await session.get(Course, course_id) if course_id else None
        if course_id and (course is None or course.canvas_course_id is None):
            await message.answer("Для этого курса нет привязанных Canvas-заданий.")
            return
        items = await _load_active_with_courses(session, course.canvas_course_id if course else None)
    page = min(max(0, page), max(0, (len(items) - 1) // 6))
    selected = items[page * 6:(page + 1) * 6]
    lines = [f'📚 Активные задания: {len(items)}', 'Выбери задание — покажу, что нужно сделать.', '']
    rows = []
    for number, (assignment, _) in enumerate(selected, page * 6 + 1):
        lines.append(f'{number}. {escape(assignment.name[:150])}')
        if assignment.due_at:
            lines.append(f'{deadline_status_emoji(assignment.due_at)} {to_tz(assignment.due_at).strftime("%d.%m %H:%M")}')
        else:
            lines.append('📅 Дедлайн не указан')
        rows.append([InlineKeyboardButton(text=f'{number}. {assignment.name[:60]}',
            callback_data=AssignmentCB(assignment_id=assignment.id, course_id=course_id, list_page=page).pack())])
    navigation = []
    if page:
        navigation.append(InlineKeyboardButton(text='⬅️', callback_data=AssignmentListCB(page=page-1, course_id=course_id).pack()))
    if (page + 1) * 6 < len(items):
        navigation.append(InlineKeyboardButton(text='➡️', callback_data=AssignmentListCB(page=page+1, course_id=course_id).pack()))
    if navigation:
        rows.append(navigation)
    await message.answer('\n'.join(lines) if items else 'Нет активных заданий 😎',
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=rows) if rows else None)


async def _load_active_with_courses(session, canvas_course_id: int | None = None):
    query = select(Assignment).where(
        Assignment.is_active.is_(True), Assignment.is_submitted.is_(False)
    )
    if canvas_course_id is not None:
        query = query.where(Assignment.canvas_course_id == canvas_course_id)

    result = await session.execute(query)
    assignments = list(result.scalars().all())
    assignments.sort(key=lambda a: (a.due_at is None, a.due_at))

    items = []
    for a in assignments:
        course_result = await session.execute(
            select(Course).where(Course.canvas_course_id == a.canvas_course_id)
        )
        items.append((a, course_result.scalar_one_or_none()))
    return items


@router.message(Command("assignments"))
@router.message(F.text == BTN_ASSIGNMENTS)
async def show_assignments(message: Message) -> None:
    await send_list(message)


@router.callback_query(CourseCB.filter(F.action == "assignments"))
async def show_course_assignments(callback: CallbackQuery, callback_data: CourseCB) -> None:
    await callback.answer()
    await send_list(callback.message, course_id=callback_data.course_id)


@router.callback_query(AssignmentListCB.filter())
async def assignment_list_page(callback: CallbackQuery, callback_data: AssignmentListCB):
    await callback.answer()
    await send_list(callback.message, callback_data.course_id, callback_data.page)


@router.callback_query(AssignmentCB.filter())
async def show_assignment(callback: CallbackQuery, callback_data: AssignmentCB):
    await callback.answer()
    async with get_session() as session:
        assignment = await session.get(Assignment, callback_data.assignment_id)
        if assignment is None:
            await callback.message.answer('Задание не найдено. Обнови список.')
            return
        result = await session.execute(select(Course).where(Course.canvas_course_id == assignment.canvas_course_id))
        course = result.scalar_one_or_none()
        pages = assignment_pages(assignment, course)
        page = min(max(0, callback_data.page), len(pages)-1)
        navigation = []
        for target, label in [(page-1, '⬅️'), (page+1, 'Далее ➡️')]:
            if 0 <= target < len(pages):
                navigation.append(InlineKeyboardButton(text=label,
                    callback_data=callback_data.model_copy(update={'page': target}).pack()))
        rows = [navigation] if navigation else []
        if assignment.html_url and assignment.html_url.startswith(('https://', 'http://')):
            rows.append([InlineKeyboardButton(text='🔗 Open Canvas', url=assignment.html_url)])
        rows.append([InlineKeyboardButton(text='⬅️ К списку заданий', callback_data=AssignmentListCB(
            course_id=callback_data.course_id, page=callback_data.list_page).pack())])
        text = f'📄 Задание · {page+1}/{len(pages)}\n\n' + pages[page]
        await send_with_optional_banner(callback.bot, session, text, course if page == 0 else None,
                                       reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
