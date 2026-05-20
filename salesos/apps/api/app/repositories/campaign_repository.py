from sqlalchemy import select

from app.models.campaign import Campaign
from app.repositories.base import Repository


class CampaignRepository(Repository):
    async def list_campaigns(self) -> list[Campaign]:
        result = await self.session.execute(select(Campaign).order_by(Campaign.created_at.desc()))
        return list(result.scalars().all())
