import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.redis import redis_state
from app.core.settings import settings
from app.models.enums import LeadPersonalizationTier, LeadState, WorkflowStatus
from app.schemas.lead import ScrapePipelineResponse, ScrapeRequest
from app.services.analysis_service import AnalysisService
from app.services.apify_service import ApifyGoogleMapsService
from app.services.business_intelligence_service import BusinessIntelligenceService
from app.services.enrichment_service import EnrichmentService
from app.services.lead_lifecycle_service import LeadLifecycleService
from app.services.lead_scoring_service import HeuristicLeadScore, LeadScoringService
from app.services.lead_service import LeadService
from app.services.normalization_service import LeadNormalizationService
from app.services.personalization_service import PersonalizationService
from app.services.pipeline_observer import PipelineObserver
from app.services.review_signal_service import ReviewSignalService
from app.services.telegram_service import TelegramAlertService
from salesos_shared.logging import get_logger, log_extra


logger = get_logger(__name__)


@dataclass(slots=True)
class ExistingLeadDecision:
    reuse_existing: bool
    skip_reason: str | None = None


class ScrapePipelineService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.leads = LeadService(session)
        self.lifecycle = LeadLifecycleService(session)
        self.scoring = LeadScoringService()
        self.normalizer = LeadNormalizationService()
        self.apify = ApifyGoogleMapsService()
        self.analysis = AnalysisService(session)
        self.business_intelligence = BusinessIntelligenceService(session)
        self.enrichment = EnrichmentService(session)
        self.personalization = PersonalizationService(session)
        self.review_signals = ReviewSignalService(session)
        self.alerts = TelegramAlertService()

    async def run(self, payload: ScrapeRequest) -> ScrapePipelineResponse:
        workflow_run_id = uuid.uuid4()
        observer = PipelineObserver(
            self.session,
            workflow_name="google_maps_scrape",
            workflow_run_id=workflow_run_id,
            campaign_id=payload.campaign_id,
        )
        scrape_result = await observer.run_resilient_stage(
            "scrape_request",
            lambda: self.apify.collect_google_maps_leads(
                query=payload.query,
                location=payload.location,
                max_results=payload.max_results,
                fixture_name=payload.fixture_name,
            ),
            metadata={
                "query": payload.query,
                "location": payload.location,
                "fixture_name": payload.fixture_name,
            },
        )
        scrape_result = scrape_result or {"mode": "empty-fallback", "run_id": "empty-fallback", "items": []}
        items = scrape_result["items"]
        inserted = 0
        deduplicated = 0
        reused_existing = 0
        analyzed = 0
        intelligence_ready = 0
        personalized = 0
        outreach_generated = 0
        skipped_due_to_cooldown = 0
        skipped_low_score = 0
        scored_high = 0
        scored_medium = 0
        scored_low = 0
        invalid = 0
        normalized_count = 0
        await observer.record_event(
            workflow_stage="scrape_result_received",
            status=WorkflowStatus.succeeded.value,
            metadata={
                "source_mode": scrape_result["mode"],
                "received": len(items),
                "run_id": scrape_result["run_id"],
                "fixture_diagnostics": scrape_result.get("fixture_diagnostics"),
            },
        )
        for raw_item in items:
            try:
                async with observer.stage("lead_normalization", metadata={"place_id": raw_item.get("place_id")}):
                    normalized = self.normalizer.normalize_lead(campaign_id=payload.campaign_id, raw_lead=raw_item)
                    normalized_count += 1
            except Exception:
                invalid += 1
                continue

            async with observer.stage("lead_deduplication", metadata={"business_name": normalized.business_name}):
                lead, created = await self.leads.create_or_get_lead(normalized)

            if created:
                inserted += 1
                logger.info(
                    "Selected newly inserted lead for downstream processing",
                    extra=log_extra(
                        service="api",
                        lead_id=str(lead.id),
                        business_name=lead.business_name,
                        campaign_id=str(payload.campaign_id) if payload.campaign_id else None,
                        execution_path="newly_inserted",
                    ),
                )
                await observer.run_resilient_stage(
                    "postgres_insert",
                    lambda lead_id=lead.id: self._emit_insert_confirmation(lead_id),
                    lead_id=lead.id,
                )
            else:
                deduplicated += 1
                existing_decision = self._decide_existing_lead_processing(
                    created=created,
                    process_existing_leads=settings.process_existing_leads,
                )
                if not existing_decision.reuse_existing:
                    logger.info(
                        "Skipping existing lead because PROCESS_EXISTING_LEADS is disabled",
                        extra=log_extra(
                            service="api",
                            lead_id=str(lead.id),
                            business_name=lead.business_name,
                            campaign_id=str(payload.campaign_id) if payload.campaign_id else None,
                            skip_reason=existing_decision.skip_reason,
                        ),
                    )
                    continue

                reused_existing += 1
                logger.info(
                    "Reusing existing lead for downstream processing",
                    extra=log_extra(
                        service="api",
                        lead_id=str(lead.id),
                        business_name=lead.business_name,
                        campaign_id=str(payload.campaign_id) if payload.campaign_id else None,
                        execution_path="existing_reused",
                    ),
                )

            enrichment_result = await observer.run_resilient_stage(
                "enrichment_stub",
                lambda lead_id=lead.id: self.enrichment.store_enrichment_stub(
                    lead_id=lead_id,
                    source_mode=scrape_result["mode"],
                ),
                lead_id=lead.id,
            )
            if enrichment_result is not None:
                await self.lifecycle.transition(
                    lead,
                    LeadState.ENRICHED,
                    metadata={"source_mode": scrape_result["mode"]},
                )
            else:
                await self.lifecycle.transition(
                    lead,
                    LeadState.FAILED,
                    failure_reason="enrichment_stage_failed",
                    metadata={"source_mode": scrape_result["mode"]},
                )
                continue

            extracted_reviews = self.review_signals.extract_reviews(raw_item)
            review_signal_result = await observer.run_resilient_stage(
                "review_signal_detection",
                lambda lead_ref=lead, reviews=tuple(extracted_reviews): self.review_signals.analyze_and_store(
                    lead=lead_ref,
                    business_name=lead_ref.business_name,
                    business_category=lead_ref.category,
                    reviews=reviews,
                ),
                lead_id=lead.id,
                metadata={"review_count": len(extracted_reviews)},
            )
            if review_signal_result is not None:
                logger.info(
                    "Review signals attached to lead metadata",
                    extra=log_extra(
                        service="api",
                        lead_id=str(lead.id),
                        business_name=lead.business_name,
                        severity=review_signal_result.severity,
                        categories=review_signal_result.categories,
                        high_signal=review_signal_result.high_signal,
                        ai_refined=review_signal_result.ai_refined,
                    ),
                )
                if review_signal_result.severity >= settings.review_signal_alert_threshold:
                    review_alert_result = await observer.run_resilient_stage(
                        "telegram_review_signal_alert",
                        lambda lead_ref=lead, assessment=review_signal_result: self.alerts.send_alert(
                            title="High-Signal Review Pain Detected",
                            message=self._telegram_review_signal_message(lead_ref.business_name, assessment),
                            metadata={
                                "lead_id": str(lead_ref.id),
                                "severity": assessment.severity,
                                "categories": assessment.categories,
                                "generated_hook": assessment.outreach_hook,
                            },
                        ),
                        lead_id=lead.id,
                        metadata={
                            "severity": review_signal_result.severity,
                            "categories": review_signal_result.categories,
                        },
                    )
                    await self._record_degraded_dependency_if_present(
                        observer,
                        workflow_stage="telegram_review_signal_alert_degraded",
                        dependency_result=review_alert_result,
                        lead_id=lead.id,
                    )

            business_analysis = await observer.run_resilient_stage(
                "business_intelligence_analysis",
                lambda lead_id=lead.id, website=lead.website: self.business_intelligence.analyze_lead(
                    lead_id=lead_id,
                    website=website,
                ),
                lead_id=lead.id,
                metadata={"website": lead.website},
            )
            if business_analysis is not None:
                intelligence_ready += 1
                lead.metadata_json = {
                    **(lead.metadata_json or {}),
                    "business_analysis": business_analysis.model_dump(),
                }
                await self.session.commit()
                await self.session.refresh(lead)
                await self.lifecycle.transition(
                    lead,
                    LeadState.INTELLIGENCE_READY,
                    metadata=business_analysis.model_dump(),
                )

            score_result = self.scoring.score_lead(
                business_name=lead.business_name,
                website=lead.website,
                email=lead.email,
                phone=lead.phone,
                city=lead.city,
                category=lead.category,
                metadata=lead.metadata_json,
                query=payload.query,
                location=payload.location,
            )
            await self.lifecycle.set_scoring(
                lead,
                heuristic_score=score_result.score,
                personalization_tier=score_result.personalization_tier,
                metadata={
                    "reasons": score_result.reasons,
                    "components": [
                        {
                            "name": component.name,
                            "weight": component.weight,
                            "awarded": component.awarded,
                            "explanation": component.explanation,
                        }
                        for component in score_result.components
                    ],
                },
            )

            if score_result.personalization_tier == LeadPersonalizationTier.high:
                scored_high += 1
            elif score_result.personalization_tier == LeadPersonalizationTier.medium:
                scored_medium += 1
            else:
                scored_low += 1

            logger.info(
                "Lead scoring decision computed",
                extra=log_extra(
                    service="api",
                    lead_id=str(lead.id),
                    business_name=lead.business_name,
                    heuristic_score=score_result.score,
                    personalization_tier=score_result.personalization_tier.value,
                    reasons=score_result.reasons,
                ),
            )

            if score_result.personalization_tier == LeadPersonalizationTier.low:
                skipped_low_score += 1
                await self.lifecycle.transition(
                    lead,
                    LeadState.REJECTED,
                    failure_reason="heuristic_score_below_personalization_threshold",
                    metadata={"heuristic_score": score_result.score, "reasons": score_result.reasons},
                )
                logger.info(
                    "Skipping personalization due to low heuristic score",
                    extra=log_extra(
                        service="api",
                        lead_id=str(lead.id),
                        business_name=lead.business_name,
                        heuristic_score=score_result.score,
                        personalization_tier=score_result.personalization_tier.value,
                        skip_reason="low_heuristic_score",
                    ),
                )
                continue

            await self.lifecycle.transition(
                lead,
                LeadState.QUALIFIED,
                metadata={"heuristic_score": score_result.score, "tier": score_result.personalization_tier.value},
            )

            if score_result.personalization_tier == LeadPersonalizationTier.high:
                analysis_result = await observer.run_resilient_stage(
                    "ollama_analysis_stub",
                    lambda lead_id=lead.id, business_name=lead.business_name: self.analysis.analyze_lead(
                        lead_id=lead_id,
                        business_name=business_name,
                        context=(
                            f"Source query: {payload.query}; location: {payload.location}."
                            f"{self._review_signal_context(lead.metadata_json)}"
                        ),
                    ),
                    lead_id=lead.id,
                )
            else:
                analysis_result = await observer.run_resilient_stage(
                    "heuristic_analysis",
                    lambda lead_id=lead.id: self.analysis.store_analysis_result(
                        lead_id=lead_id,
                        analysis=self._analysis_from_score(score_result),
                        model_name="heuristic:lead_scoring",
                    ),
                    lead_id=lead.id,
                )
            if analysis_result is not None:
                analyzed += 1
                await self._record_fallback_if_present(
                    observer,
                    workflow_stage="analysis_fallback",
                    lead_id=lead.id,
                    payload=getattr(analysis_result, "payload", None),
                )
            else:
                await self.lifecycle.transition(
                    lead,
                    LeadState.FAILED,
                    failure_reason="analysis_stage_failed",
                    metadata={"heuristic_score": score_result.score},
                )
                continue

            recent_outreach = await self.personalization.recent_outreach_for_lead(
                lead_id=lead.id,
                cooldown_hours=settings.outreach_cooldown_hours,
            )
            if self._should_skip_due_to_cooldown(recent_outreach) and not settings.dev_force_outreach_regeneration:
                skipped_due_to_cooldown += 1
                await self.lifecycle.transition(
                    lead,
                    LeadState.COOLDOWN,
                    metadata={
                        "cooldown_hours": settings.outreach_cooldown_hours,
                        "recent_outreach_id": str(recent_outreach.id),
                    },
                )
                logger.info(
                    "Skipping personalization because recent outreach exists",
                    extra=log_extra(
                        service="api",
                        lead_id=str(lead.id),
                        business_name=lead.business_name,
                        campaign_id=str(payload.campaign_id) if payload.campaign_id else None,
                        cooldown_hours=settings.outreach_cooldown_hours,
                        recent_outreach_id=str(recent_outreach.id),
                        recent_outreach_created_at=recent_outreach.created_at.isoformat(),
                        skip_reason="recent_outreach_within_cooldown",
                    ),
                )
                await observer.record_event(
                    workflow_stage="personalization_cooldown_skip",
                    status=WorkflowStatus.succeeded.value,
                    lead_id=lead.id,
                    metadata={
                        "cooldown_hours": settings.outreach_cooldown_hours,
                        "recent_outreach_id": str(recent_outreach.id),
                        "recent_outreach_created_at": recent_outreach.created_at.isoformat(),
                        "skip_reason": "recent_outreach_within_cooldown",
                    },
                )
                continue

            if self._should_skip_due_to_cooldown(recent_outreach) and settings.dev_force_outreach_regeneration:
                logger.info(
                    "DEV_FORCE_REPROCESS: bypassing cooldown check for outreach regeneration testing",
                    extra=log_extra(
                        service="api",
                        lead_id=str(lead.id),
                        business_name=lead.business_name,
                        campaign_id=str(payload.campaign_id) if payload.campaign_id else None,
                        recent_outreach_id=str(recent_outreach.id) if recent_outreach else None,
                        skip_reason="dev_force_outreach_regeneration_enabled",
                    ),
                )

            await self.lifecycle.transition(
                lead,
                LeadState.PERSONALIZED,
                metadata={"personalization_tier": score_result.personalization_tier.value},
            )
            outreach_result = await observer.run_resilient_stage(
                "personalization_stub",
                lambda lead_id=lead.id, business_name=lead.business_name: self.personalization.prepare_outreach(
                    campaign_id=payload.campaign_id,
                    lead_id=lead_id,
                    business_name=business_name,
                    context=(
                        f"Category: {lead.category or payload.query}; Location: {lead.city or payload.location}."
                        f"{self._review_signal_context(lead.metadata_json)}"
                    ),
                    analysis=self._analysis_from_score(score_result)
                    if score_result.personalization_tier == LeadPersonalizationTier.medium
                    else None,
                    personalization_tier=score_result.personalization_tier,
                ),
                lead_id=lead.id,
            )
            if outreach_result is not None:
                personalized += 1
                outreach_generated += 1
                await self._record_fallback_if_present(
                    observer,
                    workflow_stage="personalization_fallback",
                    lead_id=lead.id,
                    payload=getattr(outreach_result, "metadata_json", None),
                )
                await self.lifecycle.transition(
                    lead,
                    LeadState.IN_REVIEW,
                    metadata={
                        "outreach_log_id": str(outreach_result.id),
                        "personalization_tier": score_result.personalization_tier.value,
                        "review_status": outreach_result.review_status.value,
                    },
                )
                logger.info(
                    "Generated outreach for lead",
                    extra=log_extra(
                        service="api",
                        lead_id=str(lead.id),
                        business_name=lead.business_name,
                        campaign_id=str(payload.campaign_id) if payload.campaign_id else None,
                        outreach_log_id=str(outreach_result.id),
                        execution_path="personalization_completed",
                    ),
                )
            else:
                await self.lifecycle.transition(
                    lead,
                    LeadState.FAILED,
                    failure_reason="personalization_stage_failed",
                    metadata={"personalization_tier": score_result.personalization_tier.value},
                )

        summary = (
            f"Scrape completed for '{payload.query}' in '{payload.location}'. "
            f"Received {len(items)} leads, normalized {normalized_count}, inserted {inserted}, "
            f"deduplicated {deduplicated}, reused_existing {reused_existing}, intelligence_ready {intelligence_ready}, analyzed {analyzed}, "
            f"personalized {personalized}, outreach_generated {outreach_generated}, "
            f"skipped_due_to_cooldown {skipped_due_to_cooldown}, skipped_low_score {skipped_low_score}, "
            f"scored_high {scored_high}, scored_medium {scored_medium}, scored_low {scored_low}, invalid {invalid}."
        )
        await observer.record_event(
            workflow_stage="workflow_logging",
            status=WorkflowStatus.succeeded.value,
            metadata={
                "received": len(items),
                "normalized": normalized_count,
                "inserted": inserted,
                "deduplicated": deduplicated,
                "reused_existing": reused_existing,
                "intelligence_ready": intelligence_ready,
                "analyzed": analyzed,
                "personalized": personalized,
                "outreach_generated": outreach_generated,
                "skipped_due_to_cooldown": skipped_due_to_cooldown,
                "skipped_low_score": skipped_low_score,
                "scored_high": scored_high,
                "scored_medium": scored_medium,
                "scored_low": scored_low,
                "invalid": invalid,
                "summary": summary,
                "errors": observer.failures,
            },
        )
        workflow_status = self._final_workflow_status(
            total_received=len(items),
            inserted=inserted,
            deduplicated=deduplicated,
            analyzed=analyzed,
            personalized=personalized,
            invalid=invalid,
            errors=observer.failures,
            source_mode=scrape_result["mode"],
        )
        response = ScrapePipelineResponse(
            workflow_run_id=workflow_run_id,
            correlation_id=observer.correlation_id,
            source_mode=scrape_result["mode"],
            workflow_status=workflow_status,
            total_received=len(items),
            inserted=inserted,
            deduplicated=deduplicated,
            reused_existing=reused_existing,
            analyzed=analyzed,
            personalized=personalized,
            outreach_generated=outreach_generated,
            skipped_due_to_cooldown=skipped_due_to_cooldown,
            invalid=invalid,
            campaign_id=payload.campaign_id,
            summary=summary,
            errors=observer.failures,
        )
        await observer.run_resilient_stage(
            "redis_operational_state",
            lambda: redis_state.set_json(
                "salesos:pipeline:last_scrape",
                response.model_dump(mode="json"),
                ttl_seconds=86400,
            ),
            metadata={"key": "salesos:pipeline:last_scrape"},
        )
        telegram_state_result = await observer.run_resilient_stage(
            "telegram_alert",
            lambda: self.alerts.send_alert(
                title="Scrape Pipeline Completed",
                message=summary,
                metadata={
                    "query": payload.query,
                    "location": payload.location,
                    "mode": scrape_result["mode"],
                    "workflow_run_id": str(workflow_run_id),
                },
            ),
        )
        await self._record_degraded_dependency_if_present(
            observer,
            workflow_stage="telegram_alert_degraded",
            dependency_result=telegram_state_result,
        )
        return response

    async def _emit_insert_confirmation(self, lead_id) -> dict:
        return {"lead_id": str(lead_id), "status": "inserted"}

    @staticmethod
    def _decide_existing_lead_processing(*, created: bool, process_existing_leads: bool) -> ExistingLeadDecision:
        if created:
            return ExistingLeadDecision(reuse_existing=True)
        if not process_existing_leads:
            return ExistingLeadDecision(reuse_existing=False, skip_reason="process_existing_leads_disabled")
        return ExistingLeadDecision(reuse_existing=True)

    @staticmethod
    def _should_skip_due_to_cooldown(recent_outreach) -> bool:
        return recent_outreach is not None

    @staticmethod
    def _review_signal_context(metadata: dict) -> str:
        review_signal_summary = metadata.get("review_signal_summary", {})
        if not isinstance(review_signal_summary, dict) or not review_signal_summary.get("operational_summary"):
            return ""
        categories = ", ".join(review_signal_summary.get("categories") or [])
        evidence_snippets = review_signal_summary.get("evidence_snippets") or []
        evidence_text = " ".join(f'"{line}"' for line in evidence_snippets[:2])
        evidence_section = f" Evidence: {evidence_text}." if evidence_text else ""
        return (
            f" Review signals: {review_signal_summary.get('operational_summary')} "
            f"Hook: {review_signal_summary.get('generated_hook')} "
            f"Categories: {categories} Severity: {review_signal_summary.get('severity')}."
            f"{evidence_section}"
        )

    @staticmethod
    def _telegram_review_signal_message(business_name: str, assessment) -> str:
        categories = ", ".join(assessment.categories[:2])
        return (
            f"{business_name} shows review pain in {categories}. "
            f"Severity {assessment.severity}. {assessment.outreach_hook}"
        )

    @staticmethod
    def _analysis_from_score(score_result: HeuristicLeadScore):
        from app.services.ai_service import LeadAnalysis

        return LeadAnalysis(
            score=float(score_result.score),
            observation=score_result.observation,
            problem=score_result.problem,
            outreach_hook=score_result.outreach_hook,
            generation_metadata={
                "fallback_used": False,
                "retry_count": 0,
                "filler_detected": False,
                "heuristic_score": score_result.score,
                "quality_issues": [],
                "model": "heuristic:lead_scoring",
                "prompt_template": "heuristic_analysis",
            },
        )

    async def _record_fallback_if_present(
        self,
        observer: PipelineObserver,
        *,
        workflow_stage: str,
        lead_id,
        payload: dict | None,
    ) -> None:
        if not isinstance(payload, dict):
            return
        generation_metadata = payload.get("generation_metadata")
        if not isinstance(generation_metadata, dict):
            return
        if not generation_metadata.get("fallback_used"):
            return
        await self._record_degradation(
            observer,
            workflow_stage=workflow_stage,
            lead_id=lead_id,
            error_message="stage completed with AI fallback output",
            metadata={
                "fallback_used": True,
                "model": generation_metadata.get("model"),
                "quality_issues": generation_metadata.get("quality_issues") or [],
                "retry_count": generation_metadata.get("retry_count", 0),
            },
        )

    async def _record_degraded_dependency_if_present(
        self,
        observer: PipelineObserver,
        *,
        workflow_stage: str,
        dependency_result: dict | None,
        lead_id=None,
    ) -> None:
        if not isinstance(dependency_result, dict):
            return
        if dependency_result.get("status") != "degraded":
            return
        await self._record_degradation(
            observer,
            workflow_stage=workflow_stage,
            lead_id=lead_id,
            error_message=str(dependency_result.get("reason") or "dependency degraded"),
            metadata=dependency_result,
        )

    async def _record_degradation(
        self,
        observer: PipelineObserver,
        *,
        workflow_stage: str,
        error_message: str,
        metadata: dict | None = None,
        lead_id=None,
    ) -> None:
        observer.failures.append(
            {
                "workflow_stage": workflow_stage,
                "lead_id": str(lead_id) if lead_id else None,
                "error_message": error_message,
                "degraded": True,
                "metadata": metadata or {},
            }
        )
        await observer.record_event(
            workflow_stage=workflow_stage,
            status=WorkflowStatus.succeeded.value,
            lead_id=lead_id,
            metadata={"degraded": True, **(metadata or {})},
        )

    @staticmethod
    def _final_workflow_status(
        *,
        total_received: int,
        inserted: int,
        deduplicated: int,
        analyzed: int,
        personalized: int,
        invalid: int,
        errors: list[dict],
        source_mode: str,
    ) -> str:
        processed = inserted + deduplicated
        if errors:
            if processed == 0 and total_received == 0 and source_mode == "empty-fallback":
                return "failed"
            if analyzed == 0 and personalized == 0 and processed == 0:
                return "failed"
            return "partial"
        if invalid > 0:
            return "partial"
        return "completed"
