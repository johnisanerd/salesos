from sqlalchemy import select

from app.models.dead_letter_entry import DeadLetterEntry
from app.repositories.base import Repository


class DeadLetterRepository(Repository):
    async def list_recent(self, *, limit: int = 100) -> list[DeadLetterEntry]:
        result = await self.session.execute(
            select(DeadLetterEntry).order_by(DeadLetterEntry.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())
