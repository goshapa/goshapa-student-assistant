"""Deduplicates notifications via the notification_history unique constraint."""
from __future__ import annotations

from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import NotificationHistory


async def try_record_notification(
    session: AsyncSession,
    *,
    notification_type: str,
    assignment_id: int | None = None,
    lesson_id: int | None = None,
    ref_date: date | None = None,
) -> bool:
    """Attempts to record that a notification was sent. Returns True if this
    is the first time (caller should send it), False if it was already sent
    (caller must skip, to avoid duplicates after restarts/re-runs)."""
    dedup_key = (
        f"{notification_type}:a{assignment_id or 0}:l{lesson_id or 0}:{ref_date.isoformat() if ref_date else '-'}"
    )
    record = NotificationHistory(
        assignment_id=assignment_id,
        lesson_id=lesson_id,
        ref_date=ref_date,
        notification_type=notification_type,
        dedup_key=dedup_key,
    )
    session.add(record)
    try:
        await session.commit()
        return True
    except IntegrityError:
        await session.rollback()
        return False
