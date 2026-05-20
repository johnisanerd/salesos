import asyncio

from pydantic import BaseModel, Field

from app.core.settings import settings
from app.services.prompts import quality_retry_prompt
from salesos_shared import get_logger, log_extra
from salesos_shared.ai import AIProviderError, JSONModelGenerator, OllamaProvider

logger = get_logger(__name__)


class LeadAnalysis(BaseModel):
    score: float
    observation: str
    problem: str
    outreach_hook: str
    generation_metadata: dict[str, object] = Field(default_factory=dict)


class OutreachPersonalization(BaseModel):
    observation: str
    problem: str
    outreach_hook: str
    subject: str
    message: str
    generation_metadata: dict[str, object] = Field(default_factory=dict)


class ReplyAnalysis(BaseModel):
    classification: str
    reason: str


class ReviewSignalRefinement(BaseModel):
    operational_summary: str
    outreach_hook: str
    generation_metadata: dict[str, object] = Field(default_factory=dict)


class AIService:
    filler_phrases = (
        "importance of",
        "business growth",
        "startup scene",
        "strong online presence",
        "improve seo",
        "digital transformation",
        "strong strategy",
        "vibrant market",
        "online visibility",
        "emphasize the importance",
    )
    buzzwords = ("unlock", "leverage", "synergy", "game-changer", "boost", "optimize", "transform", "maximize")
    operational_terms = (
        "cta",
        "mobile",
        "trust",
        "proof",
        "booking",
        "quote",
        "form",
        "response",
        "follow-up",
        "messaging",
        "offer",
        "appointment",
        "review",
        "case study",
        "hero",
        "below the fold",
        "service area",
        "headline",
    )

    def __init__(self) -> None:
        self.provider = OllamaProvider(
            settings.ollama_base_url,
            timeout=settings.ollama_timeout_seconds,
            retries=settings.ollama_retry_attempts,
            keep_alive=settings.ollama_keep_alive,
        )
        self.generator = JSONModelGenerator(self.provider)
        self.classification_model = settings.ollama_classification_model
        self.secondary_classification_model = settings.ollama_secondary_classification_model
        self.reasoning_model = settings.ollama_reasoning_model
        self.personalization_model = settings.ollama_personalization_model

    async def analyze_lead(self, prompt: str, *, business_name: str, context: str) -> LeadAnalysis:
        issues: list[str] = []
        retry_count = 0
        current_prompt = prompt
        for attempt in range(2):
            try:
                analysis = await self._run_generation_with_timeout(
                    self.generator.generate(
                        model=self.reasoning_model,
                        prompt=current_prompt,
                        response_model=LeadAnalysis,
                        prompt_template="lead_analysis",
                    ),
                    model=self.reasoning_model,
                    prompt_template="lead_analysis",
                )
            except AIProviderError as exc:
                logger.warning(
                    "Using stub lead analysis after AI generation failure",
                    extra=log_extra(
                        model=self.reasoning_model,
                        fallback_used=True,
                        error_code=exc.code,
                        diagnostics=exc.diagnostics,
                        errors=[error.model_dump() for error in exc.details],
                    ),
                )
                fallback = self._fallback_analysis(business_name=business_name, context=context)
                fallback.generation_metadata = {
                    "fallback_used": True,
                    "retry_count": retry_count,
                    "filler_detected": False,
                    "heuristic_score": 58,
                    "quality_issues": [exc.code],
                    "model": self.reasoning_model,
                    "prompt_template": "lead_analysis",
                }
                return fallback

            quality = self._evaluate_analysis(analysis)
            analysis.generation_metadata = {
                "fallback_used": False,
                "retry_count": retry_count,
                "filler_detected": quality["filler_detected"],
                "heuristic_score": quality["heuristic_score"],
                "quality_issues": quality["issues"],
                "model": self.reasoning_model,
                "prompt_template": "lead_analysis",
            }
            if quality["acceptable"]:
                return analysis

            issues = quality["issues"]
            logger.warning(
                "Lead analysis quality gate triggered",
                extra=log_extra(
                    model=self.reasoning_model,
                    retry_count=retry_count,
                    filler_detected=quality["filler_detected"],
                    heuristic_score=quality["heuristic_score"],
                    quality_issues=quality["issues"],
                    fallback_used=False,
                ),
            )
            if attempt == 0:
                retry_count += 1
                current_prompt = quality_retry_prompt(original_prompt=prompt, issues=quality["issues"])
                continue

            fallback = self._fallback_analysis(business_name=business_name, context=context)
            fallback.generation_metadata = {
                "fallback_used": True,
                "retry_count": retry_count,
                "filler_detected": quality["filler_detected"],
                "heuristic_score": quality["heuristic_score"],
                "quality_issues": quality["issues"],
                "model": self.reasoning_model,
                "prompt_template": "lead_analysis",
            }
            return fallback

        fallback = self._fallback_analysis(business_name=business_name, context=context)
        fallback.generation_metadata = {
            "fallback_used": True,
            "retry_count": retry_count,
            "filler_detected": bool(issues),
            "heuristic_score": 50,
            "quality_issues": issues or ["analysis_quality_gate_unknown"],
            "model": self.reasoning_model,
            "prompt_template": "lead_analysis",
        }
        return fallback

    async def generate_outreach(
        self,
        prompt: str,
        *,
        business_name: str,
        context: str,
        analysis: LeadAnalysis,
    ) -> OutreachPersonalization:
        issues: list[str] = []
        retry_count = 0
        current_prompt = prompt
        for attempt in range(2):
            try:
                outreach = await self._run_generation_with_timeout(
                    self.generator.generate(
                        model=self.personalization_model,
                        prompt=current_prompt,
                        response_model=OutreachPersonalization,
                        temperature=0.2,
                        prompt_template="outreach_personalization",
                    ),
                    model=self.personalization_model,
                    prompt_template="outreach_personalization",
                )
            except AIProviderError as exc:
                logger.warning(
                    "Using stub outreach personalization after AI generation failure",
                    extra=log_extra(
                        model=self.personalization_model,
                        fallback_used=True,
                        error_code=exc.code,
                        diagnostics=exc.diagnostics,
                        errors=[error.model_dump() for error in exc.details],
                    ),
                )
                fallback = self._fallback_outreach(
                    business_name=business_name,
                    context=context,
                    analysis=analysis,
                )
                fallback.generation_metadata = {
                    "fallback_used": True,
                    "retry_count": retry_count,
                    "filler_detected": False,
                    "heuristic_score": 60,
                    "quality_issues": [exc.code],
                    "model": self.personalization_model,
                    "prompt_template": "outreach_personalization",
                }
                return fallback

            quality = self._evaluate_outreach(outreach)
            outreach.generation_metadata = {
                "fallback_used": False,
                "retry_count": retry_count,
                "filler_detected": quality["filler_detected"],
                "heuristic_score": quality["heuristic_score"],
                "quality_issues": quality["issues"],
                "model": self.personalization_model,
                "prompt_template": "outreach_personalization",
            }
            if quality["acceptable"]:
                return outreach

            issues = quality["issues"]
            logger.warning(
                "Outreach personalization quality gate triggered",
                extra=log_extra(
                    model=self.personalization_model,
                    retry_count=retry_count,
                    filler_detected=quality["filler_detected"],
                    heuristic_score=quality["heuristic_score"],
                    quality_issues=quality["issues"],
                    fallback_used=False,
                ),
            )
            if attempt == 0:
                retry_count += 1
                current_prompt = quality_retry_prompt(original_prompt=prompt, issues=quality["issues"])
                continue

            fallback = self._fallback_outreach(
                business_name=business_name,
                context=context,
                analysis=analysis,
            )
            fallback.generation_metadata = {
                "fallback_used": True,
                "retry_count": retry_count,
                "filler_detected": quality["filler_detected"],
                "heuristic_score": quality["heuristic_score"],
                "quality_issues": quality["issues"],
                "model": self.personalization_model,
                "prompt_template": "outreach_personalization",
            }
            return fallback

        fallback = self._fallback_outreach(business_name=business_name, context=context, analysis=analysis)
        fallback.generation_metadata = {
            "fallback_used": True,
            "retry_count": retry_count,
            "filler_detected": bool(issues),
            "heuristic_score": 50,
            "quality_issues": issues or ["outreach_quality_gate_unknown"],
            "model": self.personalization_model,
            "prompt_template": "outreach_personalization",
        }
        return fallback

    async def classify_reply(self, prompt: str) -> ReplyAnalysis:
        try:
            return await self._run_generation_with_timeout(
                self.generator.generate(
                    model=self.classification_model,
                    prompt=prompt,
                    response_model=ReplyAnalysis,
                    prompt_template="reply_classification_primary",
                ),
                model=self.classification_model,
                prompt_template="reply_classification_primary",
            )
        except AIProviderError as primary_error:
            logger.warning(
                "Primary reply classification model failed, retrying with secondary model",
                extra=log_extra(
                    model=self.classification_model,
                    retry_model=self.secondary_classification_model,
                    error_code=primary_error.code,
                    diagnostics=primary_error.diagnostics,
                    errors=[error.model_dump() for error in primary_error.details],
                ),
            )
            try:
                return await self._run_generation_with_timeout(
                    self.generator.generate(
                        model=self.secondary_classification_model,
                        prompt=prompt,
                        response_model=ReplyAnalysis,
                        prompt_template="reply_classification_secondary",
                    ),
                    model=self.secondary_classification_model,
                    prompt_template="reply_classification_secondary",
                )
            except AIProviderError as secondary_error:
                logger.warning(
                    "Using stub reply classification after AI generation failure",
                    extra=log_extra(
                        model=self.secondary_classification_model,
                        fallback_used=True,
                        error_code=secondary_error.code,
                        diagnostics=secondary_error.diagnostics,
                        errors=[error.model_dump() for error in secondary_error.details],
                    ),
                )
                return ReplyAnalysis(
                    classification="neutral",
                    reason="Ollama unavailable, returned a local stub reply classification.",
                )

    async def refine_review_signal(
        self,
        prompt: str,
        *,
        fallback_summary: str,
        fallback_hook: str,
    ) -> ReviewSignalRefinement:
        issues: list[str] = []
        retry_count = 0
        current_prompt = prompt
        for attempt in range(2):
            try:
                refinement = await self._run_generation_with_timeout(
                    self.generator.generate(
                        model=self.reasoning_model,
                        prompt=current_prompt,
                        response_model=ReviewSignalRefinement,
                        temperature=0.1,
                        prompt_template="review_signal_refinement",
                    ),
                    model=self.reasoning_model,
                    prompt_template="review_signal_refinement",
                )
            except AIProviderError as exc:
                logger.warning(
                    "Using heuristic review signal summary after AI refinement failure",
                    extra=log_extra(
                        model=self.reasoning_model,
                        fallback_used=True,
                        error_code=exc.code,
                        diagnostics=exc.diagnostics,
                        errors=[error.model_dump() for error in exc.details],
                    ),
                )
                return ReviewSignalRefinement(
                    operational_summary=fallback_summary,
                    outreach_hook=fallback_hook,
                    generation_metadata={
                        "fallback_used": True,
                        "retry_count": retry_count,
                        "quality_issues": [exc.code],
                        "model": self.reasoning_model,
                        "prompt_template": "review_signal_refinement",
                    },
                )

            quality = self._evaluate_review_signal_refinement(refinement)
            refinement.generation_metadata = {
                "fallback_used": False,
                "retry_count": retry_count,
                "filler_detected": quality["filler_detected"],
                "heuristic_score": quality["heuristic_score"],
                "quality_issues": quality["issues"],
                "model": self.reasoning_model,
                "prompt_template": "review_signal_refinement",
            }
            if quality["acceptable"]:
                return refinement

            issues = quality["issues"]
            logger.warning(
                "Review signal refinement quality gate triggered",
                extra=log_extra(
                    model=self.reasoning_model,
                    retry_count=retry_count,
                    filler_detected=quality["filler_detected"],
                    heuristic_score=quality["heuristic_score"],
                    quality_issues=quality["issues"],
                    fallback_used=False,
                ),
            )
            if attempt == 0:
                retry_count += 1
                current_prompt = quality_retry_prompt(original_prompt=prompt, issues=quality["issues"])
                continue

            break

        return ReviewSignalRefinement(
            operational_summary=fallback_summary,
            outreach_hook=fallback_hook,
            generation_metadata={
                "fallback_used": True,
                "retry_count": retry_count,
                "filler_detected": bool(issues),
                "heuristic_score": 50,
                "quality_issues": issues or ["review_signal_refinement_quality_gate_unknown"],
                "model": self.reasoning_model,
                "prompt_template": "review_signal_refinement",
            },
        )

    def _evaluate_analysis(self, analysis: LeadAnalysis) -> dict[str, object]:
        combined = " ".join([analysis.observation, analysis.problem, analysis.outreach_hook]).lower()
        issues: list[str] = []
        filler_detected = self._contains_filler(combined)
        if filler_detected:
            issues.append("generic_filler_detected")
        if not any(term in combined for term in self.operational_terms):
            issues.append("missing_operational_detail")
        if len(analysis.observation.split()) > 22:
            issues.append("observation_too_long")
        if len(analysis.problem.split()) > 22:
            issues.append("problem_too_long")
        if len(analysis.outreach_hook.split()) > 22:
            issues.append("outreach_hook_too_long")
        heuristic_score = max(
            0,
            100
            - (25 if filler_detected else 0)
            - (20 if "missing_operational_detail" in issues else 0)
            - (10 * sum(issue.endswith("_too_long") for issue in issues)),
        )
        return {
            "acceptable": not issues,
            "issues": issues,
            "filler_detected": filler_detected,
            "heuristic_score": heuristic_score,
        }

    def _evaluate_outreach(self, outreach: OutreachPersonalization) -> dict[str, object]:
        subject = outreach.subject.strip()
        message = outreach.message.strip()
        combined = " ".join(
            [outreach.observation, outreach.problem, outreach.outreach_hook, subject, message]
        ).lower()
        issues: list[str] = []
        filler_detected = self._contains_filler(combined)
        if filler_detected:
            issues.append("generic_filler_detected")
        if not any(term in combined for term in self.operational_terms):
            issues.append("missing_operational_detail")
        sentence_count = self._sentence_count(message)
        if sentence_count > 2:
            issues.append("message_too_long")
        if len(subject.split()) > 8:
            issues.append("subject_too_long")
        if len(message.split()) > 55:
            issues.append("message_wordy")
        if message.lower().startswith(("hi ", "hi,", "hello ", "hello,", "hey ", "hey,")):
            issues.append("intro_detected")
        heuristic_score = max(
            0,
            100
            - (30 if filler_detected else 0)
            - (20 if "missing_operational_detail" in issues else 0)
            - (10 if "message_too_long" in issues else 0)
            - (10 if "message_wordy" in issues else 0)
            - (5 if "subject_too_long" in issues else 0)
            - (5 if "intro_detected" in issues else 0),
        )
        return {
            "acceptable": not issues,
            "issues": issues,
            "filler_detected": filler_detected,
            "heuristic_score": heuristic_score,
        }

    def _evaluate_review_signal_refinement(self, refinement: ReviewSignalRefinement) -> dict[str, object]:
        combined = f"{refinement.operational_summary} {refinement.outreach_hook}".lower()
        issues: list[str] = []
        filler_detected = self._contains_filler(combined)
        if filler_detected:
            issues.append("generic_filler_detected")
        if "review" not in combined and "call" not in combined and "response" not in combined:
            issues.append("missing_review_context")
        if self._sentence_count(refinement.operational_summary) > 1:
            issues.append("summary_too_long")
        if self._sentence_count(refinement.outreach_hook) > 1:
            issues.append("hook_too_long")
        heuristic_score = max(
            0,
            100
            - (30 if filler_detected else 0)
            - (20 if "missing_review_context" in issues else 0)
            - (10 if "summary_too_long" in issues else 0)
            - (10 if "hook_too_long" in issues else 0),
        )
        return {
            "acceptable": not issues,
            "issues": issues,
            "filler_detected": filler_detected,
            "heuristic_score": heuristic_score,
        }

    def _fallback_analysis(self, *, business_name: str, context: str) -> LeadAnalysis:
        lower = context.lower()
        if "seo" in lower:
            return LeadAnalysis(
                score=71.0,
                observation=f"{business_name} emphasizes rankings, but the next-step CTA likely matters more than the copy itself.",
                problem="When the quote action is hard to spot on mobile, local search traffic often fails to convert.",
                outreach_hook="A clearer mobile CTA path would make the existing offer easier to act on.",
            )
        if "agency" in lower:
            return LeadAnalysis(
                score=69.0,
                observation=f"{business_name} likely has a visible offer, but the positioning and proof may not point to one buyer outcome.",
                problem="Mixed messaging usually makes qualified visitors hesitate before booking a call.",
                outreach_hook="A tighter proof-to-CTA path would make the offer easier to trust and act on.",
            )
        return LeadAnalysis(
            score=65.0,
            observation=f"{business_name} likely has a usable offer, but the conversion path may be less clear than the service promise.",
            problem="When the next step is not obvious, interested local traffic often drops before making contact.",
            outreach_hook="A sharper CTA and proof path would make the current offer easier to act on.",
        )

    def _fallback_outreach(
        self,
        *,
        business_name: str,
        context: str,
        analysis: LeadAnalysis,
    ) -> OutreachPersonalization:
        lower = context.lower()
        if "seo" in lower:
            subject = "Quick thought on mobile CTA"
        elif "agency" in lower:
            subject = "Quick thought on offer clarity"
        else:
            subject = "Quick thought on conversion flow"
        message = f"{business_name}: {analysis.observation} {analysis.problem}"
        return OutreachPersonalization(
            observation=analysis.observation,
            problem=analysis.problem,
            outreach_hook=analysis.outreach_hook,
            subject=subject,
            message=message,
        )

    def _contains_filler(self, text: str) -> bool:
        return any(phrase in text for phrase in self.filler_phrases) or any(
            buzzword in text for buzzword in self.buzzwords
        )

    @staticmethod
    def _sentence_count(text: str) -> int:
        segments = [segment.strip() for segment in text.replace("?", ".").replace("!", ".").split(".")]
        return len([segment for segment in segments if segment])

    async def _run_generation_with_timeout(self, operation, *, model: str, prompt_template: str):
        try:
            return await asyncio.wait_for(operation, timeout=settings.ollama_generation_timeout_seconds)
        except TimeoutError as exc:
            diagnostics = {
                "model": model,
                "prompt_template": prompt_template,
                "failure_stage": "generation_timeout",
                "timeout_seconds": settings.ollama_generation_timeout_seconds,
            }
            logger.warning(
                "Ollama generation timed out",
                extra=log_extra(
                    model=model,
                    prompt_template=prompt_template,
                    timeout_seconds=settings.ollama_generation_timeout_seconds,
                    fallback_used=True,
                ),
            )
            raise AIProviderError(
                "Ollama generation timed out before a structured response was produced.",
                code="generation_timeout",
                diagnostics=diagnostics,
            ) from exc
