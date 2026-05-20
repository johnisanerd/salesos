from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.models.enums import FollowUpStatus, OutreachStatus
from app.models.outreach_log import OutreachLog
from app.repositories.base import Repository
from app.repositories.outreach_repository import OutreachLogRepository


class FollowUpService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = Repository(session)
        self.outreach = OutreachLogRepository(session)

    async def schedule(self, outreach_id, *, due_at: datetime, actor: str) -> OutreachLog:
        outreach = await self._get(outreach_id)
        outreach.follow_up_due_at = due_at
        outreach.follow_up_status = FollowUpStatus.scheduled
        metadata = dict(outreach.metadata_json or {})
        metadata["follow_up"] = {"scheduled_by": actor, "due_at": due_at.isoformat()}
        outreach.metadata_json = metadata
        await self.session.commit()
        return outreach

    async def process_due(self, *, now: datetime | None = None, limit: int = 50) -> list[OutreachLog]:
        due_items = await self.outreach.list_due_follow_ups(now=now, limit=limit)
        current_time = now or datetime.now(UTC)
        for outreach in due_items:
            outreach.follow_up_attempts += 1
            if outreach.follow_up_attempts >= settings.follow_up_max_attempts:
                outreach.follow_up_status = FollowUpStatus.failed
                outreach.status = OutreachStatus.failed
                continue
            outreach.follow_up_status = FollowUpStatus.due
            outreach.follow_up_due_at = current_time + timedelta(hours=settings.follow_up_default_delay_hours)
        await self.session.commit()
        return due_items

    async def mark_replied(self, outreach_id) -> None:
        outreach = await self._get(outreach_id)
        outreach.follow_up_status = FollowUpStatus.replied
        await self.session.commit()

    async def _get(self, outreach_id) -> OutreachLog:
        outreach = await self.repository.get_by_id(OutreachLog, outreach_id)
        if outreach is None:
            raise ValueError("Outreach not found")
        return outreach
