import uuid

from sqlalchemy import select

from app.models.review_signal import ReviewSignal
from app.repositories.base import Repository


class ReviewSignalRepository(Repository):
    async def get_by_dedup_key(
        self,
        *,
        lead_id: uuid.UUID,
        category: str,
        evidence_hash: str,
    ) -> ReviewSignal | None:
        result = await self.session.execute(
            select(ReviewSignal).where(
                ReviewSignal.lead_id == lead_id,
                ReviewSignal.category == category,
                ReviewSignal.evidence_hash == evidence_hash,
            ),
        )
        return result.scalar_one_or_none()
