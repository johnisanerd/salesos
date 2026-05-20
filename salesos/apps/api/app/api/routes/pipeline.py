from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.pipeline import (
    EnrichmentPayload,
    LeadAnalysisRequest,
    OutreachPreparationRequest,
    ReplyClassificationRequest,
)
from app.services.analysis_service import AnalysisService
from app.services.enrichment_service import EnrichmentService
from app.services.personalization_service import PersonalizationService
from app.services.reply_service import ReplyService


router = APIRouter()


@router.post("/enrichment")
async def store_enrichment(
    payload: EnrichmentPayload,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    enrichment = await EnrichmentService(session).store_enrichment(payload)
    return {"id": str(enrichment.id), "lead_id": str(enrichment.lead_id), "provider": enrichment.provider}


@router.post("/analyze")
async def analyze_lead(
    payload: LeadAnalysisRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    score = await AnalysisService(session).analyze_lead(
        lead_id=payload.lead_id,
        business_name=payload.business_name,
        context=payload.context,
    )
    return {"id": str(score.id), "lead_id": str(score.lead_id), "score": str(score.score)}


@router.post("/replies/classify")
async def classify_reply(
    payload: ReplyClassificationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await ReplyService(session).classify_reply(payload)


@router.post("/outreach/prepare")
async def prepare_outreach(
    payload: OutreachPreparationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    outreach = await PersonalizationService(session).prepare_outreach(
        campaign_id=payload.campaign_id,
        lead_id=payload.lead_id,
        business_name=payload.business_name,
        context=payload.context,
    )
    return {"id": str(outreach.id), "status": outreach.status, "subject": outreach.subject}
