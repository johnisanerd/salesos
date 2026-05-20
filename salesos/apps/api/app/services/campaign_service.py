from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.campaign_repository import CampaignRepository


class CampaignService:
    def __init__(self, session: AsyncSession) -> None:
        self.campaigns = CampaignRepository(session)

    async def list_campaigns(self):
        return await self.campaigns.list_campaigns()
