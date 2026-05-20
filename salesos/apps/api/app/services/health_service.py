import asyncio
from time import monotonic
from urllib.parse import urlparse
import socket

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.redis import redis_state
from app.core.settings import settings
from app.schemas.health import DependencyHealth
from salesos_shared.ai import OllamaProvider


class HealthService:
    def __init__(self, session: AsyncSession, *, started_at_monotonic: float | None = None) -> None:
        self.session = session
        self.started_at_monotonic = started_at_monotonic

    async def readiness(self) -> dict[str, DependencyHealth]:
        database, redis, ollama = await asyncio.gather(
            self._database_health(),
            self._redis_health(),
            self._ollama_health(),
        )
        return {"database": database, "redis": redis, "ollama": ollama}

    def overall_status(self, checks: dict[str, DependencyHealth]) -> str:
        if all(item.ok for item in checks.values()):
            return "ok"
        if self._within_startup_grace():
            return "starting"
        return "degraded"

    async def _database_health(self) -> DependencyHealth:
        try:
            await self.session.execute(text("SELECT 1"))
            return DependencyHealth(ok=True, detail="database reachable")
        except Exception as exc:
            return DependencyHealth(ok=False, detail=f"database error: {exc}")

    async def _redis_health(self) -> DependencyHealth:
        try:
            pong = await redis_state.ping()
            return DependencyHealth(ok=bool(pong), detail="redis reachable")
        except Exception as exc:
            return DependencyHealth(ok=False, detail=f"redis error: {exc}")

    async def _ollama_health(self) -> DependencyHealth:
        provider = OllamaProvider(
            settings.ollama_base_url,
            timeout=min(settings.ollama_timeout_seconds, 5.0),
            retries=1,
            keep_alive=settings.ollama_keep_alive,
        )
        hostname = urlparse(settings.ollama_base_url).hostname or "unknown"
        resolution = _resolve_hostname(hostname)
        try:
            await provider.list_models()
            return DependencyHealth(
                ok=True,
                detail=f"ollama reachable at {settings.ollama_base_url} ({resolution})",
            )
        except Exception as exc:
            return DependencyHealth(
                ok=False,
                detail=f"ollama error at {settings.ollama_base_url} ({resolution}): {exc}",
            )

    def _within_startup_grace(self) -> bool:
        if self.started_at_monotonic is None:
            return False
        return monotonic() - self.started_at_monotonic < settings.startup_grace_period_seconds


def _resolve_hostname(hostname: str) -> str:
    if hostname == "unknown":
        return "hostname missing from OLLAMA_BASE_URL"
    try:
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(hostname, None)})
    except socket.gaierror as exc:
        return f"dns lookup failed for {hostname}: {exc}"
    return f"{hostname} -> {', '.join(addresses)}"
