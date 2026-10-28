import json
from pathlib import Path
from typing import Any

import httpx

from app.core.settings import settings
from salesos_shared.logging import get_logger, log_extra
from salesos_shared.retry import RetryError, retry_async


logger = get_logger(__name__)


class ApifyGoogleMapsService:
    default_fixture_name = "sample_leads"
    fixture_aliases = {
        "sample": "sample_leads",
        "sample_leads": "sample_leads",
        "duplicates": "duplicate_leads",
        "duplicate": "duplicate_leads",
        "duplicate_leads": "duplicate_leads",
        "malformed": "malformed_leads",
        "malformed_leads": "malformed_leads",
    }

    def __init__(self) -> None:
        self.base_url = "https://api.apify.com/v2"
        self.fixtures_dir = Path(__file__).resolve().parents[4] / "scripts" / "fixtures"

    async def collect_google_maps_leads(
        self,
        *,
        query: str,
        location: str,
        max_results: int,
        fixture_name: str | None = None,
    ) -> dict[str, Any]:
        if fixture_name:
            resolved_fixture_name = self._resolve_fixture_name(fixture_name)
            items, diagnostics = self._load_fixture_with_diagnostics(resolved_fixture_name)
            if resolved_fixture_name != fixture_name:
                diagnostics["fallback_used"] = True
                diagnostics["requested_fixture"] = fixture_name
            logger.info(
                "Using explicit scrape fixture",
                extra=log_extra(
                    service="api",
                    query=query,
                    location=location,
                    fixture_name=resolved_fixture_name,
                    requested_fixture=fixture_name,
                    fixture_path=diagnostics["fixture_path"],
                    loaded_count=diagnostics["loaded_count"],
                    malformed_records=diagnostics["malformed_records"],
                    fallback_used=diagnostics["fallback_used"],
                ),
            )
            return {
                "mode": f"fixture:{resolved_fixture_name}",
                "run_id": f"fixture-{resolved_fixture_name}",
                "items": items[:max_results],
                "fixture_diagnostics": diagnostics,
            }
        if settings.apify_token in {"", "replace-me"}:
            items, diagnostics = self._load_fixture_with_diagnostics(self.default_fixture_name)
            logger.info(
                "APIFY_TOKEN not configured; using local fixture stub mode",
                extra=log_extra(
                    service="api",
                    query=query,
                    location=location,
                    fixture_name=self.default_fixture_name,
                    fixture_path=diagnostics["fixture_path"],
                    loaded_count=diagnostics["loaded_count"],
                    malformed_records=diagnostics["malformed_records"],
                    fallback_used=False,
                ),
            )
            return {
                "mode": f"stub:{self.default_fixture_name}",
                "run_id": f"stub-{self.default_fixture_name}",
                "items": items[:max_results],
                "fixture_diagnostics": diagnostics,
            }

        actor_id = settings.apify_google_maps_actor_id
        url = f"{self.base_url}/acts/{actor_id}/runs"
        payload = {"searchTerms": [f"{query} in {location}"], "maxResultsPerSearch": max(20, max_results)}
        headers = {"Authorization": f"Bearer {settings.apify_token}"}

        async with httpx.AsyncClient(timeout=settings.apify_timeout_seconds) as client:
            async def submit_run() -> dict[str, Any]:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                run_data = response.json().get("data", {})
                return {
                    "mode": "remote",
                    "run_id": run_data.get("id", "unknown"),
                    "items": [],
                }

            try:
                return await retry_async(
                    submit_run,
                    attempts=settings.apify_retry_attempts,
                    timeout_seconds=settings.apify_timeout_seconds,
                    retry_exceptions=(httpx.HTTPError, httpx.TimeoutException),
                    retry_context={
                        "service": "apify",
                        "retry_operation": "apify_submit_run",
                        "stage": "scrape_request",
                        "query": query,
                        "location": location,
                    },
                )
            except RetryError:
                items, diagnostics = self._load_fixture_with_diagnostics(self.default_fixture_name)
                logger.warning(
                    "Apify run failed; using local fixture fallback",
                    extra=log_extra(
                        service="api",
                        query=query,
                        location=location,
                        fixture_name=self.default_fixture_name,
                        fixture_path=diagnostics["fixture_path"],
                        loaded_count=diagnostics["loaded_count"],
                        malformed_records=diagnostics["malformed_records"],
                        fallback_used=True,
                    ),
                )
                return {
                    "mode": f"stub-fallback:{self.default_fixture_name}",
                    "run_id": "stub-fallback-run",
                    "items": items[:max_results],
                    "fixture_diagnostics": diagnostics | {"fallback_used": True},
                }

    def _resolve_fixture_name(self, fixture_name: str) -> str:
        normalized = fixture_name.strip().lower()
        if normalized in self.fixture_aliases:
            return self.fixture_aliases[normalized]
        available = ", ".join(sorted(self.available_fixture_names()))
        logger.warning(
            "Requested fixture was not found; using default fixture instead",
            extra=log_extra(
                service="api",
                requested_fixture=fixture_name,
                fallback_fixture=self.default_fixture_name,
                available_fixtures=available,
                fallback_used=True,
            ),
        )
        return self.default_fixture_name

    def available_fixture_names(self) -> list[str]:
        return [path.stem for path in sorted(self.fixtures_dir.glob("*.json"))]

    def _load_fixture_with_diagnostics(self, fixture_name: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        fixture_path = self.fixtures_dir / f"{fixture_name}.json"
        if not fixture_path.exists():
            available = ", ".join(self.available_fixture_names())
            raise ValueError(f"Fixture not found: {fixture_name}. Available fixtures: {available}")

        items = json.loads(fixture_path.read_text(encoding="utf-8"))
        if not isinstance(items, list):
            raise ValueError(f"Fixture {fixture_name} must contain a JSON array of leads")

        malformed_records = sum(1 for item in items if not self._looks_like_lead(item))
        diagnostics = {
            "fixture_name": fixture_name,
            "fixture_path": str(fixture_path),
            "loaded_count": len(items),
            "malformed_records": malformed_records,
            "fallback_used": False,
        }
        return items, diagnostics

    @staticmethod
    def _looks_like_lead(item: Any) -> bool:
        if not isinstance(item, dict):
            return False
        title = item.get("business_name") or item.get("title")
        return isinstance(title, str) and bool(title.strip())
