import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.lead import LeadCreate, LeadRead, ScrapeJobAccepted, ScrapeJobStatusResponse, ScrapeRequest
from app.services.lead_service import LeadService
from app.services.scrape_job_service import ScrapeJobService


router = APIRouter()
jobs = ScrapeJobService()


@router.get("/", response_model=list[LeadRead])
async def list_leads(session: AsyncSession = Depends(get_db_session)) -> list[LeadRead]:
    return await LeadService(session).list_recent_leads()


@router.post("/", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
async def create_lead(payload: LeadCreate, session: AsyncSession = Depends(get_db_session)) -> LeadRead:
    return await LeadService(session).create_lead(payload)


@router.post("/scrape", response_model=ScrapeJobAccepted, status_code=status.HTTP_202_ACCEPTED)
async def trigger_scrape(payload: ScrapeRequest) -> ScrapeJobAccepted:
    return await jobs.start_job(payload)


@router.get("/scrape/{job_id}", response_model=ScrapeJobStatusResponse)
async def get_scrape_job(job_id: uuid.UUID) -> ScrapeJobStatusResponse:
    job = await jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Scrape job not found")
    return job
