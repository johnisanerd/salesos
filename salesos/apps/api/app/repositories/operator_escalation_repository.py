from sqlalchemy import select

from app.models.enums import EscalationStatus
from app.models.operator_escalation import OperatorEscalation
from app.repositories.base import Repository


class OperatorEscalationRepository(Repository):
    async def list_open(self, *, limit: int = 100) -> list[OperatorEscalation]:
        result = await self.session.execute(
            select(OperatorEscalation)
            .where(OperatorEscalation.status.in_([EscalationStatus.pending, EscalationStatus.escalated]))
            .order_by(OperatorEscalation.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
