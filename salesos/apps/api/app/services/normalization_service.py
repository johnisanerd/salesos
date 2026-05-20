import re
from urllib.parse import urlparse

from app.schemas.lead import LeadCreate


class LeadNormalizationService:
    def normalize_lead(self, *, campaign_id, raw_lead: dict) -> LeadCreate:
        business_name = self._normalize_text(raw_lead.get("business_name") or raw_lead.get("title"))
        city = self._normalize_text(raw_lead.get("city"))
        state = self._normalize_text(raw_lead.get("state"))
        payload = LeadCreate(
            campaign_id=campaign_id,
            source="google_maps",
            external_source_id=raw_lead.get("place_id"),
            business_name=business_name,
            phone=self._normalize_phone(raw_lead.get("phone")),
            email=self._normalize_text(raw_lead.get("email")),
            website=self._normalize_website(raw_lead.get("website")),
            city=city,
            state=state,
            country=self._normalize_text(raw_lead.get("country")),
            category=self._normalize_text(raw_lead.get("category")),
            metadata={"source_payload": raw_lead},
        )
        if not payload.business_name:
            raise ValueError("business_name is required after normalization")
        return payload

    @staticmethod
    def _normalize_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = re.sub(r"\s+", " ", value).strip()
        return normalized or None

    def _normalize_website(self, value: str | None) -> str | None:
        normalized = self._normalize_text(value)
        if not normalized:
            return None
        if not normalized.startswith(("http://", "https://")):
            normalized = f"https://{normalized}"
        parsed = urlparse(normalized)
        if not parsed.netloc:
            return None
        return normalized.lower()

    def _normalize_phone(self, value: str | None) -> str | None:
        normalized = self._normalize_text(value)
        if not normalized:
            return None
        digits = re.sub(r"[^\d+]", "", normalized)
        return digits or None
