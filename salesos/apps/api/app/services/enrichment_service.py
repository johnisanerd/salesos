from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead_enrichment import LeadEnrichment
from app.models.lead_score import LeadScore
from app.models.workflow_log import WorkflowLog
from app.models.enums import LeadStatus, WorkflowStatus
from app.repositories.base import Repository
from app.repositories.workflow_repository import WorkflowLogRepository
from app.schemas.pipeline import EnrichmentPayload


class EnrichmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = Repository(session)
        self.workflow_logs = WorkflowLogRepository(session)

    async def store_enrichment(self, payload: EnrichmentPayload) -> LeadEnrichment:
        enrichment = LeadEnrichment(
            lead_id=payload.lead_id,
            provider=payload.provider,
            payload=payload.payload,
        )
        await self.repository.add(enrichment)
        await self.workflow_logs.create_log(
            WorkflowLog(
                lead_id=payload.lead_id,
                workflow_name="lead_enrichment",
                status=WorkflowStatus.succeeded,
                detail=f"Stored enrichment from {payload.provider}",
                payload=payload.payload,
            ),
        )
        await self.session.commit()
        await self.session.refresh(enrichment)
        return enrichment

    async def store_enrichment_stub(self, *, lead_id, source_mode: str) -> LeadEnrichment:
        return await self.store_enrichment(
            EnrichmentPayload(
                lead_id=lead_id,
                provider="stub_enrichment",
                payload={"status": "captured", "source_mode": source_mode},
            ),
        )
