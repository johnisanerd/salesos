from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.core.settings import settings
from app.models.enums import LeadPersonalizationTier


HIGH_SCORE_THRESHOLD = 70
MEDIUM_SCORE_THRESHOLD = 45


@dataclass(slots=True)
class ScoreComponent:
    name: str
    weight: int
    awarded: int
    explanation: str


@dataclass(slots=True)
class HeuristicLeadScore:
    score: int
    personalization_tier: LeadPersonalizationTier
    reasons: list[str]
    components: list[ScoreComponent]
    observation: str
    problem: str
    outreach_hook: str


class LeadScoringService:
    """Compute a lightweight, deterministic lead score before LLM personalization."""

    def score_lead(
        self,
        *,
        business_name: str,
        website: str | None,
        email: str | None,
        phone: str | None,
        city: str | None,
        category: str | None,
        metadata: dict[str, Any],
        query: str,
        location: str,
    ) -> HeuristicLeadScore:
        score = 0
        reasons: list[str] = []
        components: list[ScoreComponent] = []
        source_payload = metadata.get("source_payload", {})
        review_signal_summary = metadata.get("review_signal_summary", {})
        business_analysis = metadata.get("business_analysis", {})

        if website:
            score += 20
            reasons.append("website_present")
            components.append(self._component("website_present", 20, 20, "Business has a live website."))
        if email:
            score += 10
            reasons.append("email_present")
            components.append(self._component("email_present", 10, 10, "Direct email available for outreach."))
        if phone:
            score += 10
            reasons.append("phone_present")
            components.append(self._component("phone_present", 10, 10, "Phone signal is present for follow-up."))
        if self._token_overlap(query, category or business_name):
            score += 15
            reasons.append("niche_relevance_match")
            components.append(self._component("niche_relevance_match", 15, 15, "Search intent overlaps with the business niche."))
        if city and city.lower() in location.lower():
            score += 10
            reasons.append("location_match")
            components.append(self._component("location_match", 10, 10, "Lead matches the target geography."))

        completeness_fields = [website, email, phone, city, category]
        completeness_score = min(sum(1 for item in completeness_fields if item) * 3, 15)
        score += completeness_score
        if completeness_score:
            components.append(
                self._component(
                    "business_completeness",
                    15,
                    completeness_score,
                    "Structured business fields are mostly populated.",
                )
            )
        if sum(1 for item in completeness_fields if item) >= 4:
            reasons.append("business_completeness")

        review_count = self._safe_int(source_payload.get("review_count"))
        rating = self._safe_float(source_payload.get("rating"))
        if review_count >= 10:
            score += 5
            reasons.append("engagement_reviews_present")
            components.append(self._component("engagement_reviews_present", 5, 5, "The business has baseline review volume."))
        if review_count >= 30:
            score += 5
            reasons.append("engagement_reviews_strong")
            components.append(self._component("engagement_reviews_strong", 5, 5, "The business has strong review volume."))
        if rating >= 4.5:
            score += 5
            reasons.append("rating_signal_strong")
            components.append(self._component("rating_signal_strong", 5, 5, "Customer rating looks healthy."))

        if self._truthy(source_payload.get("active_ads")):
            score += 10
            reasons.append("active_ads_detected")
            components.append(self._component("active_ads_detected", 10, 10, "Paid demand suggests active commercial intent."))
        if self._truthy(source_payload.get("social_activity")):
            score += 10
            reasons.append("social_activity_detected")
            components.append(self._component("social_activity_detected", 10, 10, "The business appears active on social channels."))

        review_signal_severity = self._safe_int(review_signal_summary.get("severity"))
        review_signal_categories = review_signal_summary.get("categories") or []
        if review_signal_severity >= settings.review_signal_min_severity:
            score += 25
            reasons.append("review_signal_high_severity")
            components.append(
                self._component(
                    "review_signal_high_severity",
                    25,
                    25,
                    "Review pain suggests revenue leakage that outbound operations can address.",
                )
            )
        elif review_signal_severity >= 45:
            score += 12
            reasons.append("review_signal_present")
            components.append(
                self._component(
                    "review_signal_present",
                    25,
                    12,
                    "Review pain exists, but it is less urgent.",
                )
            )
        if any(category in {"missed_calls", "slow_response", "no_followup"} for category in review_signal_categories):
            score += 5
            reasons.append("review_signal_revenue_risk")
            components.append(
                self._component(
                    "review_signal_revenue_risk",
                    5,
                    5,
                    "Signal maps directly to lost lead handling.",
                )
            )

        score, components, reasons = self._apply_business_analysis(
            score=score,
            components=components,
            reasons=reasons,
            business_analysis=business_analysis if isinstance(business_analysis, dict) else {},
        )

        final_score = max(0, min(score, 100))
        tier = self._tier_for_score(final_score)
        observation, problem, outreach_hook = self._operational_hooks(
            business_name=business_name,
            category=category or query,
            city=city or location,
            tier=tier,
            website_present=bool(website),
            review_count=review_count,
            review_signal_summary=review_signal_summary if isinstance(review_signal_summary, dict) else {},
        )
        return HeuristicLeadScore(
            score=final_score,
            personalization_tier=tier,
            reasons=reasons,
            components=components,
            observation=observation,
            problem=problem,
            outreach_hook=outreach_hook,
        )

    def _apply_business_analysis(
        self,
        *,
        score: int,
        components: list[ScoreComponent],
        reasons: list[str],
        business_analysis: dict[str, Any],
    ) -> tuple[int, list[ScoreComponent], list[str]]:
        if not business_analysis:
            return score, components, reasons
        weights = {
            "website_exists": 5,
            "ssl_enabled": 8,
            "mobile_responsive": 10,
            "social_links": 8,
            "cta_detected": 12,
            "seo_metadata": 7,
        }
        score_inputs = business_analysis.get("score_inputs", {})
        for key, weight in weights.items():
            present = False
            if key == "seo_metadata":
                present = bool(score_inputs.get(key)) or (
                    business_analysis.get("seo_title_present") and business_analysis.get("seo_description_present")
                )
            elif key == "social_links":
                present = bool(business_analysis.get("social_links"))
            else:
                present = bool(business_analysis.get(key))
            if present:
                score += weight
                reasons.append(key)
                components.append(
                    self._component(
                        key,
                        weight,
                        weight,
                        self._business_analysis_explanation(key),
                    )
                )
        return score, components, reasons

    @staticmethod
    def _business_analysis_explanation(key: str) -> str:
        explanations = {
            "website_exists": "A web presence exists and can be improved.",
            "ssl_enabled": "HTTPS is enabled, which improves trust.",
            "mobile_responsive": "The site hints at mobile responsiveness.",
            "social_links": "Social links add trust and auditability.",
            "cta_detected": "The site has a visible call to action.",
            "seo_metadata": "Title and meta description are present.",
        }
        return explanations.get(key, key.replace("_", " "))

    @staticmethod
    def _component(name: str, weight: int, awarded: int, explanation: str) -> ScoreComponent:
        return ScoreComponent(name=name, weight=weight, awarded=awarded, explanation=explanation)

    @staticmethod
    def _tier_for_score(score: int) -> LeadPersonalizationTier:
        if score >= HIGH_SCORE_THRESHOLD:
            return LeadPersonalizationTier.high
        if score >= MEDIUM_SCORE_THRESHOLD:
            return LeadPersonalizationTier.medium
        return LeadPersonalizationTier.low

    @staticmethod
    def _operational_hooks(
        *,
        business_name: str,
        category: str,
        city: str,
        tier: LeadPersonalizationTier,
        website_present: bool,
        review_count: int,
        review_signal_summary: dict[str, Any],
    ) -> tuple[str, str, str]:
        if review_signal_summary.get("operational_summary") and review_signal_summary.get("generated_hook"):
            operational_summary = str(review_signal_summary["operational_summary"])
            generated_hook = str(review_signal_summary["generated_hook"])
            categories = review_signal_summary.get("categories") or []
            problem = (
                f"Repeated complaints around {str(categories[0]).replace('_', ' ')} usually mean sales-ready demand is leaking"
                if categories
                else "Repeated review complaints usually mean sales-ready demand is leaking before contact can turn into booked work."
            )
            return operational_summary, problem, generated_hook
        if not website_present:
            return (
                f"{business_name} has contact signals, but no clear website path for {category} visitors.",
                "Without a simple conversion path, intent often leaks before a lead can request the next step.",
                "A tighter contact or booking path would make local demand easier to capture.",
            )
        if review_count < 10:
            return (
                f"{business_name} appears active in {city}, but the trust proof around the offer looks thin.",
                "Thin proof usually weakens conversion when visitors want reassurance before reaching out.",
                "Clearer proof near the CTA would make response intent easier to convert.",
            )
        if tier == LeadPersonalizationTier.high:
            return (
                f"{business_name} looks complete enough for deeper outreach, but the CTA path likely matters more than broad service copy.",
                "When the next action is not obvious on mobile, qualified local traffic often hesitates instead of converting.",
                "A sharper proof-to-CTA path would make the current offer easier to act on.",
            )
        return (
            f"{business_name} has enough core business data to pursue, but the offer likely needs a clearer next step.",
            "When messaging and action are not aligned, interested visitors often delay contact.",
            "A cleaner conversion path could improve how existing traffic turns into replies.",
        )

    @staticmethod
    def _token_overlap(left: str, right: str) -> bool:
        left_tokens = {token for token in re.split(r"\W+", left.lower()) if token}
        right_tokens = {token for token in re.split(r"\W+", right.lower()) if token}
        return bool(left_tokens & right_tokens)

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _truthy(value: Any) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "active"}
