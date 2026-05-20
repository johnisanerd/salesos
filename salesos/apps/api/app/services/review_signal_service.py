from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.models.enums import WorkflowStatus
from app.models.lead import Lead
from app.models.review_signal import ReviewSignal
from app.models.workflow_log import WorkflowLog
from app.repositories.review_signal_repository import ReviewSignalRepository
from app.repositories.workflow_repository import WorkflowLogRepository
from app.services.ai_service import AIService
from app.services.prompts import review_signal_refinement_prompt
from salesos_shared.logging import get_logger, log_extra


logger = get_logger(__name__)


CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "missed_calls": (
        "didn't answer",
        "did not answer",
        "no answer",
        "never answered",
        "missed call",
        "went to voicemail",
        "straight to voicemail",
        "return my call",
        "returned my call",
    ),
    "slow_response": (
        "slow to respond",
        "slow response",
        "took forever",
        "days to respond",
        "never got back",
        "no response",
        "still waiting",
        "waited days",
        "delayed response",
    ),
    "rude_service": (
        "rude",
        "dismissive",
        "unprofessional",
        "hung up",
        "attitude",
        "condescending",
        "abrupt",
    ),
    "no_followup": (
        "never followed up",
        "no follow up",
        "no follow-up",
        "didn't follow up",
        "did not follow up",
        "promised to call back",
        "promised to email",
        "never called back",
    ),
    "poor_communication": (
        "poor communication",
        "hard to reach",
        "kept me in the dark",
        "no updates",
        "unclear communication",
        "didn't explain",
        "did not explain",
        "confusing communication",
    ),
    "scheduling_issues": (
        "rescheduled",
        "cancelled",
        "canceled",
        "late appointment",
        "no-show",
        "showed up late",
        "double booked",
        "missed appointment",
    ),
    "pricing_confusion": (
        "unexpected charge",
        "hidden fee",
        "quoted one price",
        "bait and switch",
        "pricing unclear",
        "price changed",
        "surprise charge",
        "quote changed",
    ),
    "trust_signals": (
        "would not recommend",
        "avoid this company",
        "scam",
        "misleading",
        "dishonest",
        "fake reviews",
        "felt shady",
        "can't trust",
    ),
}

CATEGORY_LABELS = {
    "missed_calls": "missed calls",
    "slow_response": "slow responses",
    "rude_service": "rude service",
    "no_followup": "no follow-up",
    "poor_communication": "poor communication",
    "scheduling_issues": "scheduling friction",
    "pricing_confusion": "pricing confusion",
    "trust_signals": "trust complaints",
}

CATEGORY_BASE_SEVERITY = {
    "missed_calls": 38,
    "slow_response": 32,
    "rude_service": 34,
    "no_followup": 34,
    "poor_communication": 28,
    "scheduling_issues": 26,
    "pricing_confusion": 30,
    "trust_signals": 40,
}


@dataclass(slots=True)
class ParsedReview:
    text: str
    rating: float
    review_timestamp: datetime | None


@dataclass(slots=True)
class DetectedReviewSignal:
    category: str
    severity: int
    evidence: str
    rating: float
    review_timestamp: datetime | None
    matched_terms: list[str]


@dataclass(slots=True)
class ReviewSignalAssessment:
    severity: int
    categories: list[str]
    signals: list[DetectedReviewSignal]
    operational_summary: str
    outreach_hook: str
    signal_count: int
    malformed_reviews: int
    ai_refined: bool

    @property
    def high_signal(self) -> bool:
        return self.severity >= settings.review_signal_min_severity


class ReviewSignalService:
    def __init__(self, session: AsyncSession, *, ai_service: AIService | None = None) -> None:
        self.session = session
        self.ai_service = ai_service or AIService()
        self.signals = ReviewSignalRepository(session)
        self.workflow_logs = WorkflowLogRepository(session)

    async def analyze_and_store(
        self,
        *,
        lead: Lead,
        business_name: str,
        business_category: str | None,
        reviews: Sequence[dict[str, Any]],
    ) -> ReviewSignalAssessment | None:
        parsed_reviews, malformed_reviews = self._parse_reviews(reviews)
        logger.info(
            "Review signal review payload parsed",
            extra=log_extra(
                service="api",
                lead_id=str(lead.id),
                business_name=business_name,
                review_count=len(reviews),
                parsed_review_count=len(parsed_reviews),
                malformed_reviews=malformed_reviews,
            ),
        )
        if not parsed_reviews:
            return None

        detected = self._detect_signals(parsed_reviews)
        if not detected:
            logger.info(
                "No review signals detected for lead",
                extra=log_extra(
                    service="api",
                    lead_id=str(lead.id),
                    business_name=business_name,
                    parsed_review_count=len(parsed_reviews),
                    malformed_reviews=malformed_reviews,
                ),
            )
            return None

        assessment = self._build_assessment(
            business_name=business_name,
            category=business_category,
            detected=detected,
            malformed_reviews=malformed_reviews,
        )

        if settings.review_signal_ai_refinement_enabled and assessment.high_signal:
            assessment = await self._refine_assessment_with_ai(
                business_name=business_name,
                business_category=business_category,
                assessment=assessment,
            )

        await self._persist_signals(lead=lead, assessment=assessment)
        return assessment

    @staticmethod
    def extract_reviews(raw_lead: dict[str, Any]) -> list[dict[str, Any]]:
        review_keys = ("reviews", "google_reviews", "latest_reviews")
        for key in review_keys:
            value = raw_lead.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []

    def _parse_reviews(self, reviews: Sequence[dict[str, Any]]) -> tuple[list[ParsedReview], int]:
        parsed: list[ParsedReview] = []
        malformed = 0
        for raw_review in reviews:
            text = raw_review.get("text") or raw_review.get("review_text") or raw_review.get("content")
            if not isinstance(text, str) or not text.strip():
                malformed += 1
                continue
            rating = self._safe_float(raw_review.get("rating"))
            parsed.append(
                ParsedReview(
                    text=text.strip(),
                    rating=rating,
                    review_timestamp=self._parse_timestamp(raw_review.get("timestamp") or raw_review.get("date")),
                ),
            )
        return parsed, malformed

    def _detect_signals(self, reviews: Sequence[ParsedReview]) -> list[DetectedReviewSignal]:
        detected: list[DetectedReviewSignal] = []
        for review in reviews:
            lowered = review.text.lower()
            for category, keywords in CATEGORY_KEYWORDS.items():
                matched_terms = [term for term in keywords if term in lowered]
                if not matched_terms:
                    continue
                detected.append(
                    DetectedReviewSignal(
                        category=category,
                        severity=self._calculate_severity(
                            category=category,
                            rating=review.rating,
                            review_timestamp=review.review_timestamp,
                            match_count=len(matched_terms),
                        ),
                        evidence=review.text,
                        rating=review.rating,
                        review_timestamp=review.review_timestamp,
                        matched_terms=matched_terms,
                    ),
                )
        return detected

    def _build_assessment(
        self,
        *,
        business_name: str,
        category: str | None,
        detected: list[DetectedReviewSignal],
        malformed_reviews: int,
    ) -> ReviewSignalAssessment:
        grouped: dict[str, list[DetectedReviewSignal]] = {}
        for signal in detected:
            grouped.setdefault(signal.category, []).append(signal)

        aggregated: list[DetectedReviewSignal] = []
        for signal_category, items in grouped.items():
            top_signal = max(items, key=lambda item: item.severity)
            aggregated.append(
                DetectedReviewSignal(
                    category=signal_category,
                    severity=min(100, top_signal.severity + min((len(items) - 1) * 8, 16)),
                    evidence=top_signal.evidence,
                    rating=top_signal.rating,
                    review_timestamp=top_signal.review_timestamp,
                    matched_terms=top_signal.matched_terms,
                ),
            )

        aggregated.sort(key=lambda item: item.severity, reverse=True)
        categories = [signal.category for signal in aggregated]
        top_labels = [CATEGORY_LABELS.get(signal.category, signal.category.replace("_", " ")) for signal in aggregated[:2]]
        top_signal = aggregated[0]
        severity = min(100, top_signal.severity + min((len(aggregated) - 1) * 5, 15))
        summary = self._heuristic_summary(business_name=business_name, labels=top_labels)
        hook = self._heuristic_hook(category=top_signal.category)
        logger.info(
            "Review signals classified for lead",
            extra=log_extra(
                service="api",
                business_name=business_name,
                detected_categories=categories,
                severity=severity,
                signal_count=len(aggregated),
                malformed_reviews=malformed_reviews,
                prompt_template="heuristic_review_signal",
            ),
        )
        return ReviewSignalAssessment(
            severity=severity,
            categories=categories,
            signals=aggregated,
            operational_summary=summary,
            outreach_hook=hook,
            signal_count=len(aggregated),
            malformed_reviews=malformed_reviews,
            ai_refined=False,
        )

    async def _refine_assessment_with_ai(
        self,
        *,
        business_name: str,
        business_category: str | None,
        assessment: ReviewSignalAssessment,
    ) -> ReviewSignalAssessment:
        try:
            refinement = await self.ai_service.refine_review_signal(
                review_signal_refinement_prompt(
                    business_name=business_name,
                    category=business_category,
                    detected_categories=assessment.categories,
                    heuristic_summary=assessment.operational_summary,
                    heuristic_hook=assessment.outreach_hook,
                    evidence_lines=[signal.evidence for signal in assessment.signals],
                ),
                fallback_summary=assessment.operational_summary,
                fallback_hook=assessment.outreach_hook,
            )
        except Exception as exc:
            logger.warning(
                "Review signal AI refinement failed; using heuristic output",
                extra=log_extra(
                    service="api",
                    business_name=business_name,
                    severity=assessment.severity,
                    error=str(exc),
                ),
            )
            return assessment

        return ReviewSignalAssessment(
            severity=assessment.severity,
            categories=assessment.categories,
            signals=assessment.signals,
            operational_summary=refinement.operational_summary,
            outreach_hook=refinement.outreach_hook,
            signal_count=assessment.signal_count,
            malformed_reviews=assessment.malformed_reviews,
            ai_refined=not bool(refinement.generation_metadata.get("fallback_used")),
        )

    async def _persist_signals(self, *, lead: Lead, assessment: ReviewSignalAssessment) -> None:
        for signal in assessment.signals:
            evidence_hash = self._hash_evidence(signal.evidence)
            existing = await self.signals.get_by_dedup_key(
                lead_id=lead.id,
                category=signal.category,
                evidence_hash=evidence_hash,
            )
            if existing is None:
                self.session.add(
                    ReviewSignal(
                        lead_id=lead.id,
                        category=signal.category,
                        severity=signal.severity,
                        evidence=signal.evidence,
                        evidence_hash=evidence_hash,
                        operational_summary=assessment.operational_summary,
                        generated_hook=assessment.outreach_hook,
                        review_rating=Decimal(str(round(signal.rating, 1))) if signal.rating else None,
                        review_timestamp=signal.review_timestamp,
                        metadata_json={
                            "matched_terms": signal.matched_terms,
                            "signal_count": assessment.signal_count,
                            "ai_refined": assessment.ai_refined,
                        },
                    ),
                )
            else:
                existing.severity = signal.severity
                existing.operational_summary = assessment.operational_summary
                existing.generated_hook = assessment.outreach_hook
                existing.review_rating = Decimal(str(round(signal.rating, 1))) if signal.rating else None
                existing.review_timestamp = signal.review_timestamp
                existing.metadata_json = {
                    **(existing.metadata_json or {}),
                    "matched_terms": signal.matched_terms,
                    "signal_count": assessment.signal_count,
                    "ai_refined": assessment.ai_refined,
                }

        evidence_snippets = [signal.evidence for signal in assessment.signals[:2]]
        lead.metadata_json = {
            **(lead.metadata_json or {}),
            "review_signal_summary": {
                "severity": assessment.severity,
                "categories": assessment.categories,
                "signal_count": assessment.signal_count,
                "operational_summary": assessment.operational_summary,
                "generated_hook": assessment.outreach_hook,
                "evidence_snippets": evidence_snippets,
                "malformed_reviews": assessment.malformed_reviews,
                "ai_refined": assessment.ai_refined,
            },
        }
        await self.workflow_logs.create_log(
            WorkflowLog(
                campaign_id=lead.campaign_id,
                lead_id=lead.id,
                workflow_name="review_signal_detection",
                status=WorkflowStatus.succeeded,
                detail=f"Detected {assessment.signal_count} review signal categories",
                payload=lead.metadata_json["review_signal_summary"],
            ),
        )
        await self.session.commit()

    @staticmethod
    def _calculate_severity(
        *,
        category: str,
        rating: float,
        review_timestamp: datetime | None,
        match_count: int,
    ) -> int:
        severity = CATEGORY_BASE_SEVERITY.get(category, 25)
        if rating <= 1:
            severity += 24
        elif rating <= 2:
            severity += 18
        elif rating <= 3:
            severity += 10

        if review_timestamp is not None:
            age_days = (datetime.now(UTC) - review_timestamp).days
            if age_days <= 30:
                severity += 10
            elif age_days <= 90:
                severity += 5

        severity += min(max(match_count - 1, 0) * 4, 12)
        return max(0, min(100, severity))

    @staticmethod
    def _heuristic_summary(*, business_name: str, labels: list[str]) -> str:
        if len(labels) == 1:
            return f"Recent reviews for {business_name} repeatedly mention {labels[0]}."
        return f"Recent reviews for {business_name} mention {labels[0]} and {labels[1]}."

    @staticmethod
    def _heuristic_hook(*, category: str) -> str:
        hooks = {
            "missed_calls": "That usually means inbound demand is leaking before staff can turn enquiries into booked work.",
            "slow_response": "Slow follow-up usually costs high-intent leads before they ever book a call or quote.",
            "rude_service": "That kind of front-line friction usually drags down both conversion and repeat business.",
            "no_followup": "When callbacks stall after the first enquiry, ready-to-buy leads often disappear before a second chance.",
            "poor_communication": "Unclear updates usually create avoidable drop-off before the customer feels confident enough to commit.",
            "scheduling_issues": "Scheduling friction usually kills momentum after the customer has already shown buying intent.",
            "pricing_confusion": "When pricing feels inconsistent, trust drops before the business can recover the sale.",
            "trust_signals": "Trust complaints usually signal revenue leakage long before a new lead ever reaches the close stage.",
        }
        return hooks.get(category, "Operational friction like this usually leaks demand before a sale can be booked.")

    @staticmethod
    def _hash_evidence(evidence: str) -> str:
        return hashlib.sha256(evidence.strip().lower().encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        if not isinstance(value, str):
            return None
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0
