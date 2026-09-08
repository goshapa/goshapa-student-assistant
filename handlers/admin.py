"""Manual schedule management: add / edit / cancel / reschedule a lesson."""
from __future__ import annotations

import re
from datetime import date, datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from database import get_session
from database.models import Course, Lesson, LessonException
from keyboards.callback_data import ConfirmCB, ManageCB, ManageCourseCB, WeekdayCB
from keyboards.settings import (
    WEEKDAY_LABELS,
    cancel_fsm_keyboard,
    confirm_keyboard,
    manage_course_list_keyboard,
    weekday_keyboard,
)
from services.schedule_service import get_all_courses, get_lessons_for_date
from utils.datetime_utils import parse_time_str
from utils.logger import get_logger

logger = get_logger(__name__)
router = Router(name="admin")

DATE_RE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _parse_date(text: str) -> date | None:
    m = DATE_RE.match(text.strip())
    if not m:
        return None
    day, month, year = (int(g) for g in m.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_time(text: str) -> object | None:
    if not TIME_RE.match(text.strip()):
        return None
    return parse_time_str(text.strip())


class AddLessonStates(StatesGroup):
    title = State()
    course_code = State()
    weekday = State()
    start_time = State()
    end_time = State()
    building = State()
    room = State()
    start_date = State()
    end_date = State()


class EditLessonStates(StatesGroup):
    choose_course = State()
    weekday = State()
    start_time = State()
    end_time = State()
    building = State()
    room = State()
    start_date = State()
    end_date = State()
    confirm = State()


class CancelLessonStates(StatesGroup):
    choose_course = State()
    enter_date = State()
    confirm = State()


class RescheduleLessonStates(StatesGroup):
    choose_course = State()
    enter_original_date = State()
    enter_new_date = State()
    enter_new_start_time = State()
    enter_new_end_time = State()
    enter_new_building = State()
    enter_new_room = State()
    confirm = State()


# ---------------------------------------------------------------- ADD ----

@router.callback_query(ManageCB.filter(F.action == "add"))
async def start_add_lesson(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddLessonStates.title)
    await callback.message.answer("Введите название предмета:", reply_markup=cancel_fsm_keyboard())
    await callback.answer()


@router.message(AddLessonStates.title)
async def add_lesson_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(AddLessonStates.course_code)
    await message.answer("Введите course code (например COSC-1570-3T):", reply_markup=cancel_fsm_keyboard())


@router.message(AddLessonStates.course_code)
async def add_lesson_course_code(message: Message, state: FSMContext) -> None:
    await state.update_data(course_code=message.text.strip())
    await state.set_state(AddLessonStates.weekday)
    await message.answer("Выберите день недели:", reply_markup=weekday_keyboard())


@router.callback_query(AddLessonStates.weekday, WeekdayCB.filter())
async def add_lesson_weekday(callback: CallbackQuery, callback_data: WeekdayCB, state: FSMContext) -> None:
    await state.update_data(weekday=callback_data.weekday)
    await state.set_state(AddLessonStates.start_time)
    await callback.message.answer("Введите время начала (ЧЧ:ММ):", reply_markup=cancel_fsm_keyboard())
    await callback.answer()


@router.message(AddLessonStates.start_time)
async def add_lesson_start_time(message: Message, state: FSMContext) -> None:
    t = _parse_time(message.text)
    if t is None:
        await message.answer("Неверный формат. Введите время как ЧЧ:ММ.")
        return
    await state.update_data(start_time=message.text.strip())
    await state.set_state(AddLessonStates.end_time)
    await message.answer("Введите время окончания (ЧЧ:ММ):")


@router.message(AddLessonStates.end_time)
async def add_lesson_end_time(message: Message, state: FSMContext) -> None:
    t = _parse_time(message.text)
    if t is None:
        await message.answer("Неверный формат. Введите время как ЧЧ:ММ.")
        return
    await state.update_data(end_time=message.text.strip())
    await state.set_state(AddLessonStates.building)
    await message.answer("Введите корпус:")


@router.message(AddLessonStates.building)
async def add_lesson_building(message: Message, state: FSMContext) -> None:
    await state.update_data(building=message.text.strip())
    await state.set_state(AddLessonStates.room)
    await message.answer("Введите аудиторию:")


@router.message(AddLessonStates.room)
async def add_lesson_room(message: Message, state: FSMContext) -> None:
    await state.update_data(room=message.text.strip())
    await state.set_state(AddLessonStates.start_date)
    await message.answer("Введите дату начала (ДД.ММ.ГГГГ):")


@router.message(AddLessonStates.start_date)
async def add_lesson_start_date(message: Message, state: FSMContext) -> None:
    d = _parse_date(message.text)
    if d is None:
        await message.answer("Неверный формат. Введите дату как ДД.ММ.ГГГГ.")
        return
    await state.update_data(start_date=d.isoformat())
    await state.set_state(AddLessonStates.end_date)
    await message.answer("Введите дату окончания (ДД.ММ.ГГГГ):")


@router.message(AddLessonStates.end_date)
async def add_lesson_end_date(message: Message, state: FSMContext) -> None:
    d = _parse_date(message.text)
    if d is None:
        await message.answer("Неверный формат. Введите дату как ДД.ММ.ГГГГ.")
        return

    data = await state.get_data()
    await state.clear()

    async with get_session() as session:
        result = await session.execute(
            select(Course).where(Course.course_code == data["course_code"])
        )
        course = result.scalar_one_or_none()
        if course is None:
            course = Course(course_code=data["course_code"], title=data["title"])
            session.add(course)
            await session.flush()

        lesson = Lesson(
            course_id=course.id,
            course_code=data["course_code"],
            title=data["title"],
            weekday=data["weekday"],
            start_time=parse_time_str(data["start_time"]),
            end_time=parse_time_str(data["end_time"]),
            building=data["building"],
            room=data["room"],
            start_date=date.fromisoformat(data["start_date"]),
            end_date=d,
            is_active=True,
        )
        session.add(lesson)
        await session.commit()

    await message.answer(
        f"✅ Пара «{data['title']}» ({WEEKDAY_LABELS[data['weekday']]}) добавлена в расписание."
    )


# ------------------------------------------------------------- CANCEL ----

@router.callback_query(ManageCB.filter(F.action == "cancel"))
async def start_cancel_lesson(callback: CallbackQuery, state: FSMContext) -> None:
    async with get_session() as session:
        courses = await get_all_courses(session)
    await state.set_state(CancelLessonStates.choose_course)
    await callback.message.answer(
        "Выберите предмет:", reply_markup=manage_course_list_keyboard(courses, "cancel")
    )
    await callback.answer()


@router.callback_query(CancelLessonStates.choose_course, ManageCourseCB.filter(F.action == "cancel"))
async def cancel_lesson_choose_course(
    callback: CallbackQuery, callback_data: ManageCourseCB, state: FSMContext
) -> None:
    await state.update_data(course_id=callback_data.course_id)
    await state.set_state(CancelLessonStates.enter_date)
    await callback.message.answer("Введите дату пары для отмены (ДД.ММ.ГГГГ):", reply_markup=cancel_fsm_keyboard())
    await callback.answer()


@router.message(CancelLessonStates.enter_date)
async def cancel_lesson_enter_date(message: Message, state: FSMContext) -> None:
    d = _parse_date(message.text)
    if d is None:
        await message.answer("Неверный формат. Введите дату как ДД.ММ.ГГГГ.")
        return

    data = await state.get_data()
    async with get_session() as session:
        matches = [occ for occ in await get_lessons_for_date(session, d)
                   if occ.course.id == data["course_id"]]
        if len(matches) > 1:
            await message.answer("На эту дату несколько пар предмета. Отмена требует выбора конкретной пары.")
            return
        occurrence = matches[0] if matches else None
        lesson = occurrence.lesson if occurrence else None

    if lesson is None or not (lesson.start_date <= d <= lesson.end_date):
        await message.answer("На эту дату у выбранного предмета нет занятия. Попробуйте другую дату.")
        return

    await state.update_data(lesson_id=lesson.id, date=d.isoformat(),
                            original_date=(occurrence.original_date or d).isoformat())
    await state.set_state(CancelLessonStates.confirm)
    await message.answer(
        f"❌ CANCEL LESSON\n\n{lesson.title}\n\n{d.strftime('%B %d')}\n{lesson.start_time.strftime('%H:%M')}\n\nПодтвердить отмену?",
        reply_markup=confirm_keyboard("cancel_lesson"),
    )


@router.callback_query(CancelLessonStates.confirm, ConfirmCB.filter(F.action == "cancel_lesson"))
async def cancel_lesson_confirm(callback: CallbackQuery, callback_data: ConfirmCB, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    if callback_data.value != "yes":
        await callback.message.edit_text("Отменено.")
        await callback.answer()
        return

    d = date.fromisoformat(data["date"])
    async with get_session() as session:
        original_date = date.fromisoformat(data.get("original_date", data["date"]))
        result = await session.execute(select(LessonException).where(
            LessonException.lesson_id == data["lesson_id"],
            LessonException.date == original_date,
        ))
        exception = result.scalar_one_or_none()
        if exception is None:
            session.add(LessonException(lesson_id=data["lesson_id"], date=original_date, type="cancelled"))
        else:
            exception.type = "cancelled"
        await session.commit()

    await callback.message.edit_text(f"✅ Пара {d.strftime('%d.%m.%Y')} отменена.")
    await callback.answer()


# --------------------------------------------------------- RESCHEDULE ----

@router.callback_query(ManageCB.filter(F.action == "reschedule"))
async def start_reschedule_lesson(callback: CallbackQuery, state: FSMContext) -> None:
    async with get_session() as session:
        courses = await get_all_courses(session)
    await state.set_state(RescheduleLessonStates.choose_course)
    await callback.message.answer(
        "Выберите предмет:", reply_markup=manage_course_list_keyboard(courses, "reschedule")
    )
    await callback.answer()


@router.callback_query(
    RescheduleLessonStates.choose_course, ManageCourseCB.filter(F.action == "reschedule")
)
async def reschedule_choose_course(
    callback: CallbackQuery, callback_data: ManageCourseCB, state: FSMContext
) -> None:
    await state.update_data(course_id=callback_data.course_id)
    await state.set_state(RescheduleLessonStates.enter_original_date)
    await callback.message.answer(
        "Введите исходную дату пары (ДД.ММ.ГГГГ):", reply_markup=cancel_fsm_keyboard()
    )
    await callback.answer()


@router.message(RescheduleLessonStates.enter_original_date)
async def reschedule_enter_original_date(message: Message, state: FSMContext) -> None:
    d = _parse_date(message.text)
    if d is None:
        await message.answer("Неверный формат. Введите дату как ДД.ММ.ГГГГ.")
        return

    data = await state.get_data()
    async with get_session() as session:
        result = await session.execute(
            select(Lesson).where(
                Lesson.course_id == data["course_id"], Lesson.weekday == d.weekday(), Lesson.is_active.is_(True)
            )
        )
        lesson = result.scalar_one_or_none()

    if lesson is None or not (lesson.start_date <= d <= lesson.end_date):
        await message.answer("На эту дату у выбранного предмета нет занятия. Попробуйте другую дату.")
        return

    await state.update_data(lesson_id=lesson.id, original_date=d.isoformat())
    await state.set_state(RescheduleLessonStates.enter_new_date)
    await message.answer("Введите новую дату (ДД.ММ.ГГГГ):")


@router.message(RescheduleLessonStates.enter_new_date)
async def reschedule_enter_new_date(message: Message, state: FSMContext) -> None:
    d = _parse_date(message.text)
    if d is None:
        await message.answer("Неверный формат. Введите дату как ДД.ММ.ГГГГ.")
        return
    data = await state.get_data()
    async with get_session() as session:
        lesson = await session.get(Lesson, data["lesson_id"])
        if lesson is None or not (lesson.start_date <= d <= lesson.end_date):
            await message.answer("Новая дата должна быть в пределах периода занятий курса.")
            return
    await state.update_data(new_date=d.isoformat())
    await state.set_state(RescheduleLessonStates.enter_new_start_time)
    await message.answer("Введите новое время начала (ЧЧ:ММ):")


@router.message(RescheduleLessonStates.enter_new_start_time)
async def reschedule_enter_new_start_time(message: Message, state: FSMContext) -> None:
    if _parse_time(message.text) is None:
        await message.answer("Неверный формат. Введите время как ЧЧ:ММ.")
        return
    await state.update_data(new_start_time=message.text.strip())
    await state.set_state(RescheduleLessonStates.enter_new_end_time)
    await message.answer("Введите новое время окончания (ЧЧ:ММ):")


@router.message(RescheduleLessonStates.enter_new_end_time)
async def reschedule_enter_new_end_time(message: Message, state: FSMContext) -> None:
    if _parse_time(message.text) is None:
        await message.answer("Неверный формат. Введите время как ЧЧ:ММ.")
        return
    data = await state.get_data()
    if parse_time_str(message.text) <= parse_time_str(data["new_start_time"]):
        await message.answer("Время окончания должно быть позже времени начала.")
        return
    await state.update_data(new_end_time=message.text.strip())
    await state.set_state(RescheduleLessonStates.enter_new_building)
    await message.answer("Введите новый корпус:")


@router.message(RescheduleLessonStates.enter_new_building)
async def reschedule_enter_new_building(message: Message, state: FSMContext) -> None:
    await state.update_data(new_building=message.text.strip())
    await state.set_state(RescheduleLessonStates.enter_new_room)
    await message.answer("Введите новую аудиторию:")


@router.message(RescheduleLessonStates.enter_new_room)
async def reschedule_enter_new_room(message: Message, state: FSMContext) -> None:
    await state.update_data(new_room=message.text.strip())
    data = await state.get_data()
    await state.set_state(RescheduleLessonStates.confirm)
    await message.answer(
        "🔄 RESCHEDULE LESSON\n\n"
        f"{data['original_date']} → {data['new_date']}\n"
        f"{data['new_start_time']}–{data['new_end_time']}\n"
        f"{data['new_building']} {data['new_room']}\n\n"
        "Подтвердить перенос?",
        reply_markup=confirm_keyboard("reschedule_lesson"),
    )


@router.callback_query(RescheduleLessonStates.confirm, ConfirmCB.filter(F.action == "reschedule_lesson"))
async def reschedule_confirm(callback: CallbackQuery, callback_data: ConfirmCB, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    if callback_data.value != "yes":
        await callback.message.edit_text("Отменено.")
        await callback.answer()
        return

    original_date = date.fromisoformat(data["original_date"])
    async with get_session() as session:
        result = await session.execute(
            select(LessonException).where(
                LessonException.lesson_id == data["lesson_id"],
                LessonException.date == original_date,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            await session.delete(existing)
            await session.flush()

        session.add(
            LessonException(
                lesson_id=data["lesson_id"],
                date=original_date,
                type="rescheduled",
                new_date=date.fromisoformat(data["new_date"]),
                new_start_time=parse_time_str(data["new_start_time"]),
                new_end_time=parse_time_str(data["new_end_time"]),
                new_building=data["new_building"],
                new_room=data["new_room"],
            )
        )
        await session.commit()

    await callback.message.edit_text(
        f"✅ Пара перенесена: {data['original_date']} → {data['new_date']}, "
        f"{data['new_start_time']}–{data['new_end_time']}"
    )
    await callback.answer()


# --------------------------------------------------------------- EDIT ----

@router.callback_query(ManageCB.filter(F.action == "edit"))
async def start_edit_lesson(callback: CallbackQuery, state: FSMContext) -> None:
    async with get_session() as session:
        courses = await get_all_courses(session)
    await state.set_state(EditLessonStates.choose_course)
    await callback.message.answer(
        "Выберите предмет для изменения:", reply_markup=manage_course_list_keyboard(courses, "edit")
    )
    await callback.answer()


@router.callback_query(EditLessonStates.choose_course, ManageCourseCB.filter(F.action == "edit"))
async def edit_choose_course(callback: CallbackQuery, callback_data: ManageCourseCB, state: FSMContext) -> None:
    await state.update_data(course_id=callback_data.course_id)
    await state.set_state(EditLessonStates.weekday)
    await callback.message.answer("Выберите новый день недели:", reply_markup=weekday_keyboard())
    await callback.answer()


@router.callback_query(EditLessonStates.weekday, WeekdayCB.filter())
async def edit_lesson_weekday(callback: CallbackQuery, callback_data: WeekdayCB, state: FSMContext) -> None:
    await state.update_data(weekday=callback_data.weekday)
    await state.set_state(EditLessonStates.start_time)
    await callback.message.answer("Введите новое время начала (ЧЧ:ММ):", reply_markup=cancel_fsm_keyboard())
    await callback.answer()


@router.message(EditLessonStates.start_time)
async def edit_lesson_start_time(message: Message, state: FSMContext) -> None:
    if _parse_time(message.text) is None:
        await message.answer("Неверный формат. Введите время как ЧЧ:ММ.")
        return
    await state.update_data(start_time=message.text.strip())
    await state.set_state(EditLessonStates.end_time)
    await message.answer("Введите новое время окончания (ЧЧ:ММ):")


@router.message(EditLessonStates.end_time)
async def edit_lesson_end_time(message: Message, state: FSMContext) -> None:
    if _parse_time(message.text) is None:
        await message.answer("Неверный формат. Введите время как ЧЧ:ММ.")
        return
    await state.update_data(end_time=message.text.strip())
    await state.set_state(EditLessonStates.building)
    await message.answer("Введите новый корпус:")


@router.message(EditLessonStates.building)
async def edit_lesson_building(message: Message, state: FSMContext) -> None:
    await state.update_data(building=message.text.strip())
    await state.set_state(EditLessonStates.room)
    await message.answer("Введите новую аудиторию:")


@router.message(EditLessonStates.room)
async def edit_lesson_room(message: Message, state: FSMContext) -> None:
    await state.update_data(room=message.text.strip())
    await state.set_state(EditLessonStates.start_date)
    await message.answer("Введите новую дату начала (ДД.ММ.ГГГГ):")


@router.message(EditLessonStates.start_date)
async def edit_lesson_start_date(message: Message, state: FSMContext) -> None:
    d = _parse_date(message.text)
    if d is None:
        await message.answer("Неверный формат. Введите дату как ДД.ММ.ГГГГ.")
        return
    await state.update_data(start_date=d.isoformat())
    await state.set_state(EditLessonStates.end_date)
    await message.answer("Введите новую дату окончания (ДД.ММ.ГГГГ):")


@router.message(EditLessonStates.end_date)
async def edit_lesson_end_date(message: Message, state: FSMContext) -> None:
    d = _parse_date(message.text)
    if d is None:
        await message.answer("Неверный формат. Введите дату как ДД.ММ.ГГГГ.")
        return
    await state.update_data(end_date=d.isoformat())
    data = await state.get_data()
    await state.set_state(EditLessonStates.confirm)
    await message.answer(
        "✏️ EDIT LESSON\n\n"
        f"{WEEKDAY_LABELS[data['weekday']]}, {data['start_time']}–{data['end_time']}\n"
        f"{data['building']} {data['room']}\n"
        f"{data['start_date']} – {data['end_date']}\n\n"
        "Сохранить изменения?",
        reply_markup=confirm_keyboard("edit_lesson"),
    )


@router.callback_query(EditLessonStates.confirm, ConfirmCB.filter(F.action == "edit_lesson"))
async def edit_lesson_confirm(callback: CallbackQuery, callback_data: ConfirmCB, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    if callback_data.value != "yes":
        await callback.message.edit_text("Отменено.")
        await callback.answer()
        return

    async with get_session() as session:
        result = await session.execute(
            select(Lesson).where(Lesson.course_id == data["course_id"], Lesson.is_active.is_(True))
        )
        lesson = result.scalar_one_or_none()
        if lesson is None:
            await callback.message.edit_text("Пара не найдена.")
            await callback.answer()
            return

        lesson.weekday = data["weekday"]
        lesson.start_time = parse_time_str(data["start_time"])
        lesson.end_time = parse_time_str(data["end_time"])
        lesson.building = data["building"]
        lesson.room = data["room"]
        lesson.start_date = date.fromisoformat(data["start_date"])
        lesson.end_date = date.fromisoformat(data["end_date"])
        await session.commit()

    await callback.message.edit_text("✅ Изменения сохранены.")
    await callback.answer()


# --------------------------------------------------------------- MISC ----

@router.callback_query(ManageCB.filter(F.action == "fsm_cancel"))
async def cancel_fsm(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("✖️ Отменено.")
    await callback.answer()
