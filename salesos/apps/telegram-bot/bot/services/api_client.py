import httpx

from bot.config import settings
from salesos_shared.retry import RetryError, retry_async


class APIClientService:
    async def trigger_scrape(
        self,
        *,
        query: str,
        location: str,
        max_results: int,
        fixture_name: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        payload = {
            "query": query,
            "location": location,
            "max_results": max_results,
            "fixture_name": fixture_name,
        }
        headers = {}
        if request_id:
            headers["X-Request-ID"] = request_id
        async with httpx.AsyncClient(timeout=settings.api_request_timeout_seconds) as client:
            async def perform_request() -> dict:
                response = await client.post(
                    f"{settings.api_base_url.rstrip('/')}/api/leads/scrape",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()

            try:
                return await retry_async(
                    perform_request,
                    attempts=2,
                    timeout_seconds=settings.api_request_timeout_seconds,
                    retry_exceptions=(httpx.HTTPError, httpx.TimeoutException),
                    retry_context={
                        "service": "telegram-bot",
                        "retry_operation": "trigger_scrape",
                        "stage": "api_scrape_request",
                        "request_id": request_id,
                    },
                )
            except RetryError as exc:
                return {"status": "failed", "error": str(exc)}
