from decimal import Decimal
import traceback

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import WorkflowStatus
from app.models.lead_score import LeadScore
from app.models.workflow_log import WorkflowLog
from app.repositories.base import Repository
from app.repositories.workflow_repository import WorkflowLogRepository
from app.services.ai_service import AIService, LeadAnalysis
from app.services.prompts import lead_analysis_prompt
from salesos_shared import get_logger

logger = get_logger(__name__)


class AnalysisService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = Repository(session)
        self.workflow_logs = WorkflowLogRepository(session)
        self.ai_service = AIService()

    async def analyze_lead(self, *, lead_id, business_name: str, context: str) -> LeadScore:
        try:
            analysis = await self.ai_service.analyze_lead(
                lead_analysis_prompt(business_name=business_name, context=context),
                business_name=business_name,
                context=context,
            )
        except Exception as ai_exc:
            logger.error(
                "AI service failed during lead analysis",
                extra={
                    "lead_id": str(lead_id),
                    "business_name": business_name,
                    "exception_type": ai_exc.__class__.__name__,
                    "exception_message": str(ai_exc),
                    "traceback": traceback.format_exc(),
                },
            )
            raise

        try:
            return await self.store_analysis_result(
                lead_id=lead_id,
                analysis=analysis,
                model_name=self.ai_service.reasoning_model,
            )
        except Exception as store_exc:
            logger.error(
                "Failed to store analysis result",
                extra={
                    "lead_id": str(lead_id),
                    "business_name": business_name,
                    "analysis_score": analysis.score,
                    "exception_type": store_exc.__class__.__name__,
                    "exception_message": str(store_exc),
                    "traceback": traceback.format_exc(),
                },
            )
            raise

    async def store_analysis_result(self, *, lead_id, analysis: LeadAnalysis, model_name: str) -> LeadScore:
        try:
            # Validate score is within acceptable range for Numeric(5,2)
            if not isinstance(analysis.score, (int, float)):
                raise TypeError(f"analysis.score must be numeric, got {type(analysis.score).__name__}")
            
            score_val = float(analysis.score)
            if score_val < -999.99 or score_val > 999.99:
                raise ValueError(
                    f"analysis.score out of valid range [-999.99, 999.99]: {score_val}"
                )
            
            rationale = f"{analysis.observation} {analysis.problem}".strip()
            score = LeadScore(
                lead_id=lead_id,
                model_name=model_name,
                score=Decimal(str(round(analysis.score, 2))),
                rationale=rationale,
                payload=analysis.model_dump(),
            )
            await self.repository.add(score)
        except Exception as construct_exc:
            logger.error(
                "Failed to construct LeadScore",
                extra={
                    "lead_id": str(lead_id),
                    "analysis_score": analysis.score,
                    "model_name": model_name,
                    "exception_type": construct_exc.__class__.__name__,
                    "exception_message": str(construct_exc),
                    "traceback": traceback.format_exc(),
                },
            )
            raise

        try:
            await self.workflow_logs.create_log(
                WorkflowLog(
                    lead_id=lead_id,
                    workflow_name="lead_analysis",
                    status=WorkflowStatus.succeeded,
                    payload=analysis.model_dump(),
                ),
            )
        except Exception as log_exc:
            logger.error(
                "Failed to create workflow log for analysis",
                extra={
                    "lead_id": str(lead_id),
                    "exception_type": log_exc.__class__.__name__,
                    "exception_message": str(log_exc),
                    "traceback": traceback.format_exc(),
                },
            )
            raise

        try:
            await self.session.commit()
            await self.session.refresh(score)
        except Exception as commit_exc:
            logger.error(
                "Failed to commit analysis changes to database",
                extra={
                    "lead_id": str(lead_id),
                    "exception_type": commit_exc.__class__.__name__,
                    "exception_message": str(commit_exc),
                    "traceback": traceback.format_exc(),
                },
            )
            raise

        return score
