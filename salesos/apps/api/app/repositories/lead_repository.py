from sqlalchemy import select

from app.models.lead import Lead
from app.repositories.base import Repository


class LeadRepository(Repository):
    async def get_by_fingerprint(self, fingerprint: str) -> Lead | None:
        result = await self.session.execute(
            select(Lead).where(Lead.normalized_fingerprint == fingerprint),
        )
        return result.scalar_one_or_none()

    async def list_recent(self, limit: int = 25) -> list[Lead]:
        result = await self.session.execute(select(Lead).order_by(Lead.created_at.desc()).limit(limit))
        return list(result.scalars().all())

    async def count_all(self) -> int:
        result = await self.session.execute(select(Lead.id))
        return len(list(result.scalars().all()))
