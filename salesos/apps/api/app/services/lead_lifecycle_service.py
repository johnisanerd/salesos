from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LeadPersonalizationTier, LeadState, LeadStatus
from app.models.lead import Lead
from app.models.lead_state_transition import LeadStateTransition
from app.repositories.lead_state_transition_repository import LeadStateTransitionRepository
from salesos_shared.logging import get_logger, log_extra


logger = get_logger(__name__)


class LeadLifecycleService:
    """Manage idempotent lead lifecycle transitions and related persistence."""

    failure_states = {LeadState.FAILED, LeadState.REJECTED}

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.transitions = LeadStateTransitionRepository(session)

    async def transition(
        self,
        lead: Lead,
        to_state: LeadState,
        *,
        failure_reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Transition a lead to a new lifecycle state once, skipping duplicate transitions."""
        if lead.lifecycle_state == to_state:
            logger.info(
                "Lead lifecycle transition skipped as idempotent",
                extra=log_extra(
                    service="api",
                    lead_id=str(lead.id),
                    from_state=lead.lifecycle_state.value,
                    to_state=to_state.value,
                ),
            )
            return False

        now = datetime.now(UTC)
        from_state = lead.lifecycle_state
        timestamps = dict(lead.state_timestamps or {})
        timestamps.setdefault(to_state.value, now.isoformat())

        lead.lifecycle_state = to_state
        lead.state_updated_at = now
        lead.state_timestamps = timestamps
        lead.state_failure_reason = failure_reason if to_state in self.failure_states else None
        lead.status = self._legacy_status_for_state(to_state)

        await self.transitions.create_transition(
            LeadStateTransition(
                lead_id=lead.id,
                from_state=from_state,
                to_state=to_state,
                failure_reason=failure_reason,
                metadata_json=metadata or {},
            )
        )
        await self.session.commit()
        await self.session.refresh(lead)

        logger.info(
            "Lead lifecycle transition persisted",
            extra=log_extra(
                service="api",
                metric_name="lead_state_transition_total",
                metric_value=1,
                lead_id=str(lead.id),
                from_state=from_state.value if from_state else None,
                to_state=to_state.value,
                failure_reason=failure_reason,
                metadata=metadata or {},
            ),
        )
        return True

    async def set_scoring(
        self,
        lead: Lead,
        *,
        heuristic_score: float,
        personalization_tier: LeadPersonalizationTier,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist heuristic score and selected personalization tier."""
        lead.heuristic_score = round(float(heuristic_score), 2)
        lead.personalization_tier = personalization_tier
        if metadata:
            payload = dict(lead.metadata_json or {})
            payload["heuristic_scoring"] = metadata
            lead.metadata_json = payload
        await self.session.commit()
        await self.session.refresh(lead)
        logger.info(
            "Lead heuristic scoring persisted",
            extra=log_extra(
                service="api",
                lead_id=str(lead.id),
                heuristic_score=lead.heuristic_score,
                personalization_tier=personalization_tier.value,
                metric_name="lead_heuristic_score_total",
                metric_value=1,
            ),
        )

    @staticmethod
    def _legacy_status_for_state(state: LeadState) -> LeadStatus:
        mapping = {
            LeadState.DISCOVERED: LeadStatus.new,
            LeadState.ENRICHED: LeadStatus.enriched,
            LeadState.INTELLIGENCE_READY: LeadStatus.analyzed,
            LeadState.QUALIFIED: LeadStatus.qualified,
            LeadState.PERSONALIZED: LeadStatus.queued,
            LeadState.OUTREACH_READY: LeadStatus.queued,
            LeadState.IN_REVIEW: LeadStatus.queued,
            LeadState.CONTACTED: LeadStatus.contacted,
            LeadState.REPLIED: LeadStatus.replied,
            LeadState.INTERESTED: LeadStatus.qualified,
            LeadState.CLOSED: LeadStatus.archived,
            LeadState.REJECTED: LeadStatus.archived,
            LeadState.COOLDOWN: LeadStatus.queued,
            LeadState.FAILED: LeadStatus.archived,
        }
        return mapping[state]
