"""Thin async client for the Canvas LMS REST API."""
from __future__ import annotations

from typing import Any

import aiohttp

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class CanvasAPIError(Exception):
    """Raised when Canvas is unreachable or returns an error."""


class CanvasNotConfigured(CanvasAPIError):
    """Raised when CANVAS_BASE_URL / CANVAS_ACCESS_TOKEN are not set."""


def _parse_next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        segments = part.split(";")
        if len(segments) < 2:
            continue
        url_part = segments[0].strip()
        rel_part = segments[1].strip()
        if rel_part == 'rel="next"':
            return url_part.strip("<>")
    return None


class CanvasAPI:
    def __init__(self) -> None:
        if not settings.canvas_base_url or not settings.canvas_access_token:
            raise CanvasNotConfigured("Canvas is not configured in .env")
        self.base_url = settings.canvas_base_url
        self.token = settings.canvas_access_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def _get_paginated(
        self, session: aiohttp.ClientSession, url: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        next_url: str | None = url
        next_params: dict[str, Any] | None = {**(params or {}), "per_page": 100}

        while next_url:
            try:
                async with session.get(
                    next_url, headers=self._headers(), params=next_params, timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise CanvasAPIError(f"Canvas returned {resp.status} for {next_url}: {body[:200]}")
                    data = await resp.json()
                    items.extend(data)
                    next_url = _parse_next_link(resp.headers.get("Link"))
                    next_params = None  # next_url already contains query params
            except (aiohttp.ClientError, TimeoutError) as exc:
                raise CanvasAPIError(f"Network error calling Canvas: {exc}") from exc

        return items

    async def get_active_courses(self) -> list[dict[str, Any]]:
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/api/v1/courses"
            return await self._get_paginated(
                session, url, params={"enrollment_state": "active"}
            )

    async def get_assignments(self, course_id: int) -> list[dict[str, Any]]:
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/api/v1/courses/{course_id}/assignments"
            return await self._get_paginated(
                session, url, params={"include[]": "submission", "order_by": "due_at"}
            )

    async def get_submission(
        self, course_id: int, assignment_id: int
    ) -> dict[str, Any] | None:
        async with aiohttp.ClientSession() as session:
            url = (
                f"{self.base_url}/api/v1/courses/{course_id}"
                f"/assignments/{assignment_id}/submissions/self"
            )
            try:
                async with session.get(
                    url, headers=self._headers(), timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    if resp.status == 404:
                        return None
                    if resp.status != 200:
                        body = await resp.text()
                        raise CanvasAPIError(f"Canvas returned {resp.status} for {url}: {body[:200]}")
                    return await resp.json()
            except (aiohttp.ClientError, TimeoutError) as exc:
                raise CanvasAPIError(f"Network error calling Canvas: {exc}") from exc
