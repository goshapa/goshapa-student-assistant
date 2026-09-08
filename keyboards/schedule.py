"""Inline keyboards for courses, course cards and assignments."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.models import Course
from keyboards.callback_data import AssignmentCB, CourseCB, NavCB
from utils.formatting import course_emoji


def my_courses_keyboard(courses: list[Course]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{course_emoji(c.course_code)} {c.title}",
                callback_data=CourseCB(action="view", course_id=c.id).pack(),
            )
        ]
        for c in courses
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def course_card_keyboard(course_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📚 Assignments",
                    callback_data=CourseCB(action="assignments", course_id=course_id).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="⏰ Deadlines",
                    callback_data=CourseCB(action="deadlines", course_id=course_id).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗓 Next lesson",
                    callback_data=CourseCB(action="next", course_id=course_id).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Back",
                    callback_data=NavCB(target="my_courses").pack(),
                )
            ],
        ]
    )


def open_canvas_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔗 Open Canvas", url=url)]]
    )


def back_keyboard(target: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data=NavCB(target=target).pack())]]
    )
