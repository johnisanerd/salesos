from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.enums import ConversationStatus, EscalationStatus, MessageDirection, ReplyClassification, WorkflowStatus
from app.models.outreach_log import OutreachLog
from app.models.workflow_log import WorkflowLog
from app.repositories.base import Repository
from app.repositories.workflow_repository import WorkflowLogRepository
from app.schemas.pipeline import ReplyClassificationRequest
from app.services.ai_service import AIService
from app.services.follow_up_service import FollowUpService
from app.services.operator_escalation_service import OperatorEscalationService
from app.services.prompts import reply_classification_prompt


class ReplyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = Repository(session)
        self.workflow_logs = WorkflowLogRepository(session)
        self.ai_service = AIService()
        self.follow_ups = FollowUpService(session)
        self.escalations = OperatorEscalationService(session)

    async def ingest_and_classify(self, payload: ReplyClassificationRequest, *, sender: str | None = None) -> dict:
        conversation = await self.repository.get_by_id(Conversation, payload.conversation_id)
        if conversation is None:
            raise ValueError("Conversation not found")

        await self.repository.add(
            ConversationMessage(
                conversation_id=conversation.id,
                direction=MessageDirection.inbound,
                sender=sender,
                body=payload.message_body,
            )
        )

        analysis = await self.ai_service.classify_reply(
            reply_classification_prompt(message_body=payload.message_body),
        )
        classification = self._normalize_classification(analysis.classification)
        conversation.latest_classification = classification
        conversation.summary = analysis.reason
        conversation.status = self._conversation_status_for(classification)

        outreach = await self._latest_outreach_for_lead(conversation.lead_id)
        if outreach is not None:
            outreach.latest_reply_classification = classification
            await self.follow_ups.mark_replied(outreach.id)

        escalation = None
        if classification in {ReplyClassification.positive, ReplyClassification.objection, ReplyClassification.manual_review}:
            reason = {
                ReplyClassification.positive: "Interested reply needs operator handoff",
                ReplyClassification.objection: "Objection reply needs operator handling",
                ReplyClassification.manual_review: "Reply classification uncertain and needs manual review",
            }[classification]
            escalation = await self.escalations.create(
                lead_id=conversation.lead_id,
                reason=reason,
                payload={"reply_reason": analysis.reason, "classification": classification.value},
                conversation=conversation,
                outreach_log=outreach,
            )
        elif outreach is not None:
            outreach.escalation_status = EscalationStatus.none

        await self.workflow_logs.create_log(
            WorkflowLog(
                lead_id=conversation.lead_id,
                campaign_id=conversation.campaign_id,
                workflow_name="reply_detection",
                status=WorkflowStatus.succeeded,
                payload={
                    **analysis.model_dump(),
                    "normalized_classification": classification.value,
                    "escalation_id": str(escalation.id) if escalation else None,
                },
            ),
        )
        await self.session.commit()
        return {
            **analysis.model_dump(),
            "classification": classification.value,
            "escalation_id": str(escalation.id) if escalation else None,
        }

    async def classify_reply(self, payload: ReplyClassificationRequest) -> dict:
        return await self.ingest_and_classify(payload)

    async def _latest_outreach_for_lead(self, lead_id) -> OutreachLog | None:
        result = await self.session.execute(
            select(OutreachLog).where(OutreachLog.lead_id == lead_id).order_by(OutreachLog.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _normalize_classification(value: str) -> ReplyClassification:
        try:
            return ReplyClassification(value)
        except ValueError:
            return ReplyClassification.manual_review

    @staticmethod
    def _conversation_status_for(classification: ReplyClassification) -> ConversationStatus:
        if classification == ReplyClassification.positive:
            return ConversationStatus.qualified
        if classification in {ReplyClassification.unsubscribe, ReplyClassification.spam}:
            return ConversationStatus.disqualified
        if classification == ReplyClassification.objection:
            return ConversationStatus.waiting
        return ConversationStatus.open
