from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.enums import FollowUpStatus, OutreachReviewStatus, OutreachStatus
from app.models.outreach_log import OutreachLog
from app.repositories.base import Repository


class OutreachLogRepository(Repository):
    async def get_recent_for_lead(self, *, lead_id, cooldown_hours: int) -> OutreachLog | None:
        threshold = datetime.now(UTC) - timedelta(hours=max(cooldown_hours, 0))
        result = await self.session.execute(
            select(OutreachLog)
            .where(OutreachLog.lead_id == lead_id, OutreachLog.created_at >= threshold)
            .order_by(OutreachLog.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_draft_for_lead(self, *, lead_id) -> OutreachLog | None:
        result = await self.session.execute(
            select(OutreachLog)
            .where(
                OutreachLog.lead_id == lead_id,
                OutreachLog.status.in_(
                    [
                        OutreachStatus.prepared,
                        OutreachStatus.in_review,
                        OutreachStatus.pending,
                    ]
                ),
            )
            .order_by(OutreachLog.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_review_queue(self, *, limit: int = 50) -> list[OutreachLog]:
        result = await self.session.execute(
            select(OutreachLog)
            .where(OutreachLog.review_status == OutreachReviewStatus.pending)
            .order_by(OutreachLog.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_due_follow_ups(self, *, now: datetime | None = None, limit: int = 50) -> list[OutreachLog]:
        due_at = now or datetime.now(UTC)
        result = await self.session.execute(
            select(OutreachLog)
            .where(
                OutreachLog.follow_up_due_at.is_not(None),
                OutreachLog.follow_up_due_at <= due_at,
                OutreachLog.follow_up_status.in_(
                    [
                        FollowUpStatus.scheduled,
                        FollowUpStatus.failed,
                        FollowUpStatus.pending,
                    ]
                ),
            )
            .order_by(OutreachLog.follow_up_due_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
