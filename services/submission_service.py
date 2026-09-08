"""Interprets Canvas submission payloads and applies them to local state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Assignment, Submission
from utils.datetime_utils import parse_canvas_datetime


@dataclass
class SubmissionState:
    is_submitted: bool
    is_missing: bool
    is_late: bool
    is_graded: bool
    submitted_at: Any
    workflow_state: str | None


def interpret_submission(raw: dict | None) -> SubmissionState:
    if not raw:
        return SubmissionState(False, False, False, False, None, None)

    workflow_state = raw.get("workflow_state")
    submitted_at = parse_canvas_datetime(raw.get("submitted_at"))
    is_submitted = bool(submitted_at) or workflow_state in ("submitted", "graded", "pending_review")
    is_missing = bool(raw.get("missing", False))
    is_late = bool(raw.get("late", False))
    is_graded = workflow_state == "graded"

    return SubmissionState(
        is_submitted=is_submitted,
        is_missing=is_missing and not is_submitted,
        is_late=is_late,
        is_graded=is_graded,
        submitted_at=submitted_at,
        workflow_state=workflow_state,
    )


async def apply_submission_update(
    session: AsyncSession, assignment: Assignment, raw: dict | None
) -> bool:
    """Persists submission state onto `assignment`. Returns True if the
    assignment transitioned from not-submitted to submitted just now."""
    state = interpret_submission(raw)

    was_submitted = assignment.is_submitted

    assignment.is_submitted = state.is_submitted
    assignment.is_missing = state.is_missing
    assignment.is_late = state.is_late
    assignment.is_graded = state.is_graded

    result = await session.execute(
        select(Submission).where(Submission.assignment_id == assignment.id)
    )
    submission = result.scalar_one_or_none()
    if submission is None:
        submission = Submission(assignment_id=assignment.id)
        session.add(submission)

    submission.workflow_state = state.workflow_state
    submission.submitted_at = state.submitted_at
    submission.late = state.is_late
    submission.missing = state.is_missing
    submission.graded = state.is_graded

    return state.is_submitted and not was_submitted
