from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.enums import EscalationStatus
from app.models.operator_escalation import OperatorEscalation
from app.models.outreach_log import OutreachLog
from app.repositories.operator_escalation_repository import OperatorEscalationRepository


class OperatorEscalationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = OperatorEscalationRepository(session)

    async def create(
        self,
        *,
        lead_id,
        reason: str,
        payload: dict,
        conversation: Conversation | None = None,
        outreach_log: OutreachLog | None = None,
    ) -> OperatorEscalation:
        escalation = OperatorEscalation(
            lead_id=lead_id,
            conversation_id=conversation.id if conversation else None,
            outreach_log_id=outreach_log.id if outreach_log else None,
            reason=reason,
            status=EscalationStatus.pending,
            payload=payload,
        )
        await self.repository.add(escalation)
        if conversation is not None:
            conversation.escalation_status = EscalationStatus.pending
        if outreach_log is not None:
            outreach_log.escalation_status = EscalationStatus.pending
        await self.session.commit()
        await self.session.refresh(escalation)
        return escalation

    async def resolve(self, escalation: OperatorEscalation, *, actor: str, resolution_notes: str) -> OperatorEscalation:
        escalation.status = EscalationStatus.resolved
        escalation.assigned_to = actor
        escalation.resolution_notes = resolution_notes
        await self.session.commit()
        await self.session.refresh(escalation)
        return escalation
