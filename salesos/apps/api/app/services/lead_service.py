import hashlib
from datetime import UTC, datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LeadState, LeadStatus, WorkflowStatus
from app.models.lead import Lead
from app.models.lead_state_transition import LeadStateTransition
from app.models.workflow_log import WorkflowLog
from app.repositories.lead_repository import LeadRepository
from app.services.lead_lifecycle_service import LeadLifecycleService
from app.repositories.workflow_repository import WorkflowLogRepository
from app.schemas.lead import LeadCreate


class LeadService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.leads = LeadRepository(session)
        self.workflow_logs = WorkflowLogRepository(session)
        self.lifecycle = LeadLifecycleService(session)

    @staticmethod
    def build_fingerprint(payload: LeadCreate) -> str:
        source_value = "|".join(
            filter(
                None,
                [
                    payload.business_name.lower().strip(),
                    (payload.phone or "").strip(),
                    (payload.website or "").lower().strip(),
                    (payload.city or "").lower().strip(),
                ],
            ),
        )
        return hashlib.sha256(source_value.encode("utf-8")).hexdigest()

    async def create_or_get_lead(self, payload: LeadCreate) -> tuple[Lead, bool]:
        fingerprint = self.build_fingerprint(payload)
        existing = await self.leads.get_by_fingerprint(fingerprint)
        if existing:
            return existing, False

        lead = Lead(
            campaign_id=payload.campaign_id,
            source=payload.source,
            external_source_id=payload.external_source_id,
            business_name=payload.business_name,
            phone=payload.phone,
            email=str(payload.email) if payload.email else None,
            website=payload.website,
            city=payload.city,
            state=payload.state,
            country=payload.country,
            category=payload.category,
            status=LeadStatus.new,
            lifecycle_state=LeadState.DISCOVERED,
            state_updated_at=datetime.now(UTC),
            state_timestamps={LeadState.DISCOVERED.value: datetime.now(UTC).isoformat()},
            normalized_fingerprint=fingerprint,
            metadata_json=payload.metadata,
        )
        try:
            await self.leads.add(lead)
            await self.lifecycle.transitions.create_transition(
                LeadStateTransition(
                    lead_id=lead.id,
                    from_state=None,
                    to_state=LeadState.DISCOVERED,
                    metadata_json={"reason": "lead_inserted_from_scraper"},
                )
            )
            await self.workflow_logs.create_log(
                WorkflowLog(
                    campaign_id=payload.campaign_id,
                    lead_id=lead.id,
                    workflow_name="lead_ingestion",
                    status=WorkflowStatus.succeeded,
                    detail="Lead inserted from scraper pipeline",
                ),
            )
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.leads.get_by_fingerprint(fingerprint)
            if existing is not None:
                return existing, False
            raise
        await self.session.refresh(lead)
        return lead, True

    async def create_lead(self, payload: LeadCreate) -> Lead:
        lead, _ = await self.create_or_get_lead(payload)
        return lead

    async def list_recent_leads(self) -> list[Lead]:
        return await self.leads.list_recent()
