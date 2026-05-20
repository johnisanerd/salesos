from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    FollowUpStatus,
    LeadPersonalizationTier,
    OutreachChannel,
    OutreachReviewStatus,
    OutreachStatus,
    WorkflowStatus,
)
from app.models.outreach_log import OutreachLog
from app.repositories.outreach_repository import OutreachLogRepository
from app.models.workflow_log import WorkflowLog
from app.repositories.base import Repository
from app.repositories.workflow_repository import WorkflowLogRepository
from app.services.ai_service import AIService, LeadAnalysis, OutreachPersonalization
from app.core.settings import settings
from app.services.prompts import lead_analysis_prompt, outreach_personalization_prompt
from salesos_shared.logging import get_logger, log_extra


logger = get_logger(__name__)


class PersonalizationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = Repository(session)
        self.outreach_logs = OutreachLogRepository(session)
        self.workflow_logs = WorkflowLogRepository(session)
        self.ai_service = AIService()

    async def recent_outreach_for_lead(self, *, lead_id, cooldown_hours: int) -> OutreachLog | None:
        return await self.outreach_logs.get_recent_for_lead(lead_id=lead_id, cooldown_hours=cooldown_hours)

    async def prepare_outreach(
        self,
        *,
        campaign_id,
        lead_id,
        business_name: str,
        context: str,
        analysis: LeadAnalysis | None = None,
        personalization_tier: LeadPersonalizationTier = LeadPersonalizationTier.high,
    ) -> OutreachLog:
        logger.info(
            "Preparing outreach log",
            extra=log_extra(
                service="api",
                campaign_id=str(campaign_id) if campaign_id else None,
                lead_id=str(lead_id),
                business_name=business_name,
            ),
        )
        analysis = analysis or await self.ai_service.analyze_lead(
            lead_analysis_prompt(business_name=business_name, context=context),
            business_name=business_name,
            context=context,
        )
        if personalization_tier == LeadPersonalizationTier.medium:
            outreach_plan = self._build_lightweight_outreach(business_name=business_name, analysis=analysis)
        else:
            outreach_plan = await self.ai_service.generate_outreach(
                outreach_personalization_prompt(
                    business_name=business_name,
                    context=context,
                    observation=analysis.observation,
                    problem=analysis.problem,
                    outreach_hook=analysis.outreach_hook,
                ),
                business_name=business_name,
                context=context,
                analysis=analysis,
            )
        return await self._persist_outreach(
            campaign_id=campaign_id,
            lead_id=lead_id,
            business_name=business_name,
            analysis=analysis,
            outreach_plan=outreach_plan,
            personalization_tier=personalization_tier,
        )

    async def _persist_outreach(
        self,
        *,
        campaign_id,
        lead_id,
        business_name: str,
        analysis: LeadAnalysis,
        outreach_plan: OutreachPersonalization,
        personalization_tier: LeadPersonalizationTier,
    ) -> OutreachLog:
        existing = await self.outreach_logs.get_latest_draft_for_lead(lead_id=lead_id)
        if existing is not None and existing.review_status in {
            OutreachReviewStatus.pending,
            OutreachReviewStatus.edited,
            OutreachReviewStatus.approved,
        }:
            return existing

        outreach = OutreachLog(
            campaign_id=campaign_id,
            lead_id=lead_id,
            channel=OutreachChannel.email,
            status=OutreachStatus.in_review,
            review_status=OutreachReviewStatus.pending,
            follow_up_status=FollowUpStatus.pending,
            subject=outreach_plan.subject,
            body=outreach_plan.message,
            follow_up_due_at=datetime.now(UTC) + timedelta(hours=settings.follow_up_default_delay_hours),
            metadata_json={
                "score": analysis.score,
                "observation": outreach_plan.observation,
                "problem": outreach_plan.problem,
                "outreach_hook": outreach_plan.outreach_hook,
                "subject": outreach_plan.subject,
                "message": outreach_plan.message,
                "generation_metadata": outreach_plan.generation_metadata,
                "personalization_tier": personalization_tier.value,
                "source_analysis": analysis.model_dump(),
            },
        )
        await self.repository.add(outreach)
        await self.workflow_logs.create_log(
            WorkflowLog(
                campaign_id=campaign_id,
                lead_id=lead_id,
                workflow_name="outreach_preparation",
                status=WorkflowStatus.succeeded,
                payload={
                    "score": analysis.score,
                    "observation": outreach_plan.observation,
                    "problem": outreach_plan.problem,
                    "outreach_hook": outreach_plan.outreach_hook,
                    "subject": outreach_plan.subject,
                    "message": outreach_plan.message,
                    "personalization_tier": personalization_tier.value,
                },
            ),
        )
        try:
            await self.session.commit()
            await self.session.refresh(outreach)
            return outreach
        except Exception as exc:
            await self.session.rollback()
            logger.warning(
                "Outreach logging transaction rolled back",
                extra=log_extra(
                    service="api",
                    campaign_id=str(campaign_id) if campaign_id else None,
                    lead_id=str(lead_id),
                    business_name=business_name,
                    error=str(exc),
                    recovery="session rollback completed",
                ),
            )
            raise

    @staticmethod
    def _build_lightweight_outreach(*, business_name: str, analysis: LeadAnalysis) -> OutreachPersonalization:
        subject = "Quick thought on conversion flow"
        lower = analysis.observation.lower()
        if "mobile" in lower:
            subject = "Quick thought on mobile CTA"
        elif "proof" in analysis.problem.lower() or "trust" in analysis.problem.lower():
            subject = "Quick thought on trust proof"
        elif any(term in lower for term in ("missed", "voicemail", "no answer", "never answered", "callback")):
            subject = "Noticed missed calls"
        elif any(term in lower for term in ("slow", "delayed", "waited", "slow response", "slow callbacks")):
            subject = "Noticed slow callbacks"
        elif any(term in lower for term in ("follow-up", "follow up", "never followed", "no follow-up")):
            subject = "Noticed no follow-up"
        elif any(term in lower for term in ("schedule", "appointment", "booking", "rescheduled", "no-show")):
            subject = "Noticed scheduling issues"
        return OutreachPersonalization(
            observation=analysis.observation,
            problem=analysis.problem,
            outreach_hook=analysis.outreach_hook,
            subject=subject,
            message=f"{business_name}: {analysis.observation} {analysis.problem}",
            generation_metadata={
                "fallback_used": False,
                "retry_count": 0,
                "filler_detected": False,
                "heuristic_score": 85,
                "quality_issues": [],
                "model": "deterministic_lightweight",
                "prompt_template": "lightweight_personalization",
            },
        )
