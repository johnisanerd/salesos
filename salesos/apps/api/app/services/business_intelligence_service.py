from __future__ import annotations

import re
import ssl
from dataclasses import dataclass
from html import unescape
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import WorkflowStatus
from app.models.lead_enrichment import LeadEnrichment
from app.models.workflow_log import WorkflowLog
from app.repositories.base import Repository
from app.repositories.workflow_repository import WorkflowLogRepository


CTA_TERMS = ("book", "schedule", "contact", "call", "quote", "demo", "get started", "sign up")
SOCIAL_HOSTS = ("facebook.com", "instagram.com", "linkedin.com", "x.com", "twitter.com", "youtube.com", "tiktok.com")


@dataclass(slots=True)
class BusinessAnalysisResult:
    website_exists: bool
    ssl_enabled: bool
    mobile_responsive: bool
    social_links: list[str]
    cta_detected: bool
    seo_title_present: bool
    seo_description_present: bool
    h1_present: bool
    score_inputs: dict[str, int]
    summary: str
    source_url: str | None = None

    def model_dump(self) -> dict:
        return {
            "website_exists": self.website_exists,
            "ssl_enabled": self.ssl_enabled,
            "mobile_responsive": self.mobile_responsive,
            "social_links": self.social_links,
            "cta_detected": self.cta_detected,
            "seo_title_present": self.seo_title_present,
            "seo_description_present": self.seo_description_present,
            "h1_present": self.h1_present,
            "score_inputs": self.score_inputs,
            "summary": self.summary,
            "source_url": self.source_url,
        }


class BusinessIntelligenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = Repository(session)
        self.workflow_logs = WorkflowLogRepository(session)

    async def analyze_lead(self, *, lead_id, website: str | None) -> BusinessAnalysisResult:
        existing = await self.session.execute(
            select(LeadEnrichment)
            .where(LeadEnrichment.lead_id == lead_id, LeadEnrichment.provider == "business_intelligence")
            .order_by(LeadEnrichment.created_at.desc())
            .limit(1)
        )
        existing_record = existing.scalar_one_or_none()
        if existing_record is not None:
            return BusinessAnalysisResult(**existing_record.payload)

        if not website:
            result = BusinessAnalysisResult(
                website_exists=False,
                ssl_enabled=False,
                mobile_responsive=False,
                social_links=[],
                cta_detected=False,
                seo_title_present=False,
                seo_description_present=False,
                h1_present=False,
                score_inputs={
                    "website_exists": 0,
                    "ssl_enabled": 0,
                    "mobile_responsive": 0,
                    "social_links": 0,
                    "cta_detected": 0,
                    "seo_metadata": 0,
                },
                summary="No website was available, so web presence checks were skipped.",
                source_url=None,
            )
            return await self._store_result(lead_id=lead_id, result=result)

        normalized = self._normalize_url(website)
        html, final_url = await self._fetch_html(normalized)
        title = self._extract_first(r"<title[^>]*>(.*?)</title>", html)
        description = self._extract_meta_description(html)
        viewport = 'name="viewport"' in html.lower() or "name='viewport'" in html.lower()
        h1_present = bool(re.search(r"<h1\b", html, flags=re.IGNORECASE))
        social_links = self._extract_social_links(html)
        cta_detected = any(term in html.lower() for term in CTA_TERMS)
        ssl_enabled = self._is_https(final_url) and self._has_valid_ssl(final_url)
        seo_title_present = bool(title and title.strip())
        seo_description_present = bool(description and description.strip())
        result = BusinessAnalysisResult(
            website_exists=True,
            ssl_enabled=ssl_enabled,
            mobile_responsive=viewport,
            social_links=social_links,
            cta_detected=cta_detected,
            seo_title_present=seo_title_present,
            seo_description_present=seo_description_present,
            h1_present=h1_present,
            score_inputs={
                "website_exists": 1,
                "ssl_enabled": int(ssl_enabled),
                "mobile_responsive": int(viewport),
                "social_links": 1 if social_links else 0,
                "cta_detected": int(cta_detected),
                "seo_metadata": int(seo_title_present and seo_description_present),
            },
            summary=self._summary(
                ssl_enabled=ssl_enabled,
                viewport=viewport,
                cta_detected=cta_detected,
                social_links=social_links,
                seo_title_present=seo_title_present,
                seo_description_present=seo_description_present,
            ),
            source_url=final_url,
        )
        return await self._store_result(lead_id=lead_id, result=result)

    async def _store_result(self, *, lead_id, result: BusinessAnalysisResult) -> BusinessAnalysisResult:
        await self.repository.add(
            LeadEnrichment(
                lead_id=lead_id,
                provider="business_intelligence",
                payload=result.model_dump(),
            )
        )
        await self.workflow_logs.create_log(
            WorkflowLog(
                lead_id=lead_id,
                workflow_name="business_intelligence",
                status=WorkflowStatus.succeeded,
                payload=result.model_dump(),
            )
        )
        await self.session.commit()
        return result

    async def _fetch_html(self, website: str) -> tuple[str, str]:
        timeout = httpx.Timeout(10.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(website, headers={"User-Agent": "SalesOS/0.1"})
            response.raise_for_status()
            return response.text[:250000], str(response.url)

    @staticmethod
    def _normalize_url(website: str) -> str:
        if website.startswith(("http://", "https://")):
            return website
        return f"https://{website}"

    @staticmethod
    def _is_https(url: str | None) -> bool:
        return bool(url and url.lower().startswith("https://"))

    @staticmethod
    def _has_valid_ssl(url: str | None) -> bool:
        if not url:
            return False
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            return False
        try:
            ssl.create_default_context()
            return True
        except ssl.SSLError:
            return False

    @staticmethod
    def _extract_first(pattern: str, html: str) -> str | None:
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        return unescape(re.sub(r"\s+", " ", match.group(1))).strip()

    @classmethod
    def _extract_meta_description(cls, html: str) -> str | None:
        return cls._extract_first(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html)

    @staticmethod
    def _extract_social_links(html: str) -> list[str]:
        links = re.findall(r'href=["\'](.*?)["\']', html, flags=re.IGNORECASE)
        found: list[str] = []
        for link in links:
            lowered = link.lower()
            if any(host in lowered for host in SOCIAL_HOSTS):
                found.append(link)
        return found[:6]

    @staticmethod
    def _summary(
        *,
        ssl_enabled: bool,
        viewport: bool,
        cta_detected: bool,
        social_links: list[str],
        seo_title_present: bool,
        seo_description_present: bool,
    ) -> str:
        issues: list[str] = []
        if not ssl_enabled:
            issues.append("missing HTTPS confidence")
        if not viewport:
            issues.append("no mobile viewport hint")
        if not cta_detected:
            issues.append("weak CTA path")
        if not social_links:
            issues.append("no obvious social proof links")
        if not (seo_title_present and seo_description_present):
            issues.append("incomplete SEO metadata")
        if not issues:
            return "Website looks presentable, mobile-aware, and conversion-ready from a quick crawl."
        return "Website checks surfaced: " + ", ".join(issues) + "."
