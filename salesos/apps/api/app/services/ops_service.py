from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.leads import jobs
from app.models.dead_letter_entry import DeadLetterEntry
from app.models.enums import EscalationStatus, OutreachReviewStatus
from app.models.lead import Lead
from app.models.operator_escalation import OperatorEscalation
from app.models.outreach_log import OutreachLog
from app.models.workflow_log import WorkflowLog
from app.repositories.dead_letter_repository import DeadLetterRepository
from app.repositories.operator_escalation_repository import OperatorEscalationRepository
from app.repositories.outreach_repository import OutreachLogRepository


class OpsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.dead_letters = DeadLetterRepository(session)
        self.escalations = OperatorEscalationRepository(session)
        self.outreach = OutreachLogRepository(session)

    async def dashboard_snapshot(self) -> dict[str, Any]:
        leads_result = await self.session.execute(select(Lead).order_by(Lead.created_at.desc()).limit(10))
        outreach_result = await self.session.execute(select(OutreachLog).order_by(OutreachLog.created_at.desc()).limit(10))
        failures = await self.dead_letters.list_recent(limit=10)
        escalations = await self.escalations.list_open(limit=10)
        metrics = await self.metrics()
        return {
            "jobs": await jobs.list_jobs(limit=10),
            "leads": [self._lead_row(lead) for lead in leads_result.scalars().all()],
            "outreach": [self._outreach_row(item) for item in outreach_result.scalars().all()],
            "failures": [self._dead_letter_row(item) for item in failures],
            "metrics": metrics,
            "escalations": [self._escalation_row(item) for item in escalations],
        }

    async def metrics(self) -> dict[str, Any]:
        total_leads = await self.session.scalar(select(func.count()).select_from(Lead)) or 0
        review_queue = await self.session.scalar(
            select(func.count()).select_from(OutreachLog).where(OutreachLog.review_status == OutreachReviewStatus.pending)
        ) or 0
        dead_letters = await self.session.scalar(select(func.count()).select_from(DeadLetterEntry)) or 0
        open_escalations = await self.session.scalar(
            select(func.count()).select_from(OperatorEscalation).where(
                OperatorEscalation.status.in_([EscalationStatus.pending, EscalationStatus.escalated])
            )
        ) or 0
        avg_score = await self.session.scalar(select(func.avg(Lead.heuristic_score))) or 0
        stage_rows = await self.session.execute(
            select(WorkflowLog.pipeline_stage, func.count())
            .group_by(WorkflowLog.pipeline_stage)
            .order_by(func.count().desc())
        )
        return {
            "total_leads": total_leads,
            "review_queue": review_queue,
            "dead_letters": dead_letters,
            "open_escalations": open_escalations,
            "avg_score": float(avg_score if not isinstance(avg_score, Decimal) else avg_score),
            "stage_counts": {str(stage.value if stage else "unknown"): count for stage, count in stage_rows.all()},
        }

    @staticmethod
    def _lead_row(lead: Lead) -> dict[str, Any]:
        return {
            "id": str(lead.id),
            "business_name": lead.business_name,
            "lifecycle_state": lead.lifecycle_state.value,
            "heuristic_score": float(lead.heuristic_score) if lead.heuristic_score is not None else None,
            "personalization_tier": lead.personalization_tier.value if lead.personalization_tier else None,
            "created_at": lead.created_at.isoformat(),
        }

    @staticmethod
    def _outreach_row(item: OutreachLog) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "lead_id": str(item.lead_id),
            "status": item.status.value,
            "review_status": item.review_status.value,
            "follow_up_status": item.follow_up_status.value,
            "subject": item.subject,
            "created_at": item.created_at.isoformat(),
        }

    @staticmethod
    def _dead_letter_row(item: DeadLetterEntry) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "lead_id": str(item.lead_id) if item.lead_id else None,
            "pipeline_stage": item.pipeline_stage.value,
            "failure_category": item.failure_category.value,
            "error_message": item.error_message,
            "retry_count": item.retry_count,
            "created_at": item.created_at.isoformat(),
        }

    @staticmethod
    def _escalation_row(item: OperatorEscalation) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "lead_id": str(item.lead_id),
            "reason": item.reason,
            "status": item.status.value,
            "created_at": item.created_at.isoformat(),
        }
