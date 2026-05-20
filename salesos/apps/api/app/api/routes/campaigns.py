from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.campaign import CampaignRead
from app.db.session import get_db_session
from app.services.campaign_service import CampaignService


router = APIRouter()


@router.get("/", response_model=list[CampaignRead])
async def list_campaigns(session: AsyncSession = Depends(get_db_session)) -> list[CampaignRead]:
    service = CampaignService(session)
    return await service.list_campaigns()
