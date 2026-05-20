import asyncio
from collections.abc import Awaitable, Callable
import socket
from urllib.parse import urlparse

from sqlalchemy import text

from app.clients.redis import redis_state
from app.core.settings import settings
from app.db.session import engine
from salesos_shared.ai import OllamaProvider
from salesos_shared.logging import get_logger, log_extra


logger = get_logger(__name__)


def validate_startup_settings() -> None:
    warnings: list[str] = []

    if not settings.telegram_alert_chats:
        warnings.append("TELEGRAM_ALERT_CHAT_IDS is empty; alerts will only be cached")
    if settings.apify_token in {"", "replace-me"}:
        warnings.append("APIFY_TOKEN is not configured; scraper will run in stub mode")
    if settings.telegram_bot_token in {"", "replace-me"}:
        warnings.append("TELEGRAM_BOT_TOKEN is not configured; Telegram delivery will be skipped")
    if "://ollama:" in settings.ollama_base_url:
        warnings.append(
            "OLLAMA_BASE_URL still points to the removed Docker Ollama service; use http://host.docker.internal:11434"
        )

    for warning in warnings:
        logger.warning(warning, extra=log_extra(service="api", environment=settings.environment))

    if settings.startup_strict_validation and warnings:
        raise RuntimeError("Startup validation failed in strict mode")


async def warmup_ollama_models() -> None:
    if not settings.ollama_warmup_enabled:
        return

    logger.info(
        "Starting Ollama warmup",
        extra=log_extra(
            service="api",
            ollama_base_url=settings.ollama_base_url,
            ollama_host_resolution=_resolve_hostname(_ollama_hostname()),
        ),
    )

    provider = OllamaProvider(
        settings.ollama_base_url,
        timeout=settings.ollama_timeout_seconds,
        retries=1,
        keep_alive=settings.ollama_keep_alive,
    )
    models = {settings.ollama_classification_model, settings.ollama_reasoning_model}
    for model in models:
        try:
            await provider.warmup_model(model)
            logger.info(
                "Ollama warmup completed",
                extra=log_extra(service="api", model=model),
            )
        except Exception as exc:
            logger.warning(
                "Ollama warmup failed",
                extra=log_extra(service="api", model=model, error=str(exc)),
            )


async def validate_startup_dependencies() -> None:
    ollama_hostname = _ollama_hostname()
    ollama_resolution = _resolve_hostname(ollama_hostname)
    logger.info(
        "Validating startup dependencies",
        extra=log_extra(
            service="api",
            environment=settings.environment,
            strict=settings.startup_strict_validation,
            timeout_seconds=settings.startup_dependency_timeout_seconds,
            retry_attempts=settings.startup_dependency_retry_attempts,
            ollama_base_url=settings.ollama_base_url,
            ollama_hostname=ollama_hostname,
            ollama_host_resolution=ollama_resolution,
            redis_url=settings.redis_url,
            postgres_host=settings.postgres_host,
            postgres_port=settings.postgres_port,
        ),
    )

    last_results: dict[str, tuple[bool, str]] = {}
    deadline_attempts = max(settings.startup_dependency_retry_attempts, 1)

    for attempt in range(1, deadline_attempts + 1):
        last_results = dict(
            await asyncio.gather(
                _probe_database(),
                _probe_redis(),
                _probe_ollama(),
            )
        )

        failed = {name: detail for name, (ok, detail) in last_results.items() if not ok}
        if not failed:
            logger.info(
                "Startup dependency validation passed",
                extra=log_extra(
                    service="api",
                    attempt=attempt,
                    dependencies={name: detail for name, (_, detail) in last_results.items()},
                ),
            )
            return

        logger.warning(
            "Startup dependency validation attempt failed",
            extra=log_extra(
                service="api",
                attempt=attempt,
                failed_dependencies=failed,
                ollama_base_url=settings.ollama_base_url,
                ollama_host_resolution=ollama_resolution,
            ),
        )
        if attempt < deadline_attempts:
            await asyncio.sleep(settings.startup_dependency_poll_seconds)

    failed_dependencies = {name: detail for name, (ok, detail) in last_results.items() if not ok}
    message = ", ".join(f"{name}: {detail}" for name, detail in failed_dependencies.items())
    if settings.startup_strict_validation:
        raise RuntimeError(f"Startup dependency validation failed: {message}")

    logger.warning(
        "Continuing startup with degraded dependencies because strict validation is disabled",
        extra=log_extra(service="api", failed_dependencies=failed_dependencies),
    )


async def _probe_database() -> tuple[str, tuple[bool, str]]:
    async def run_check() -> str:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return "database reachable"

    return "database", await _run_probe("database", run_check)


async def _probe_redis() -> tuple[str, tuple[bool, str]]:
    async def run_check() -> str:
        pong = await redis_state.ping()
        if not pong:
            raise RuntimeError("redis ping returned false")
        return "redis reachable"

    return "redis", await _run_probe("redis", run_check)


async def _probe_ollama() -> tuple[str, tuple[bool, str]]:
    ollama_hostname = _ollama_hostname()
    ollama_resolution = _resolve_hostname(ollama_hostname)
    provider = OllamaProvider(
        settings.ollama_base_url,
        timeout=min(float(settings.startup_dependency_timeout_seconds), settings.ollama_timeout_seconds),
        retries=1,
        keep_alive=settings.ollama_keep_alive,
    )

    async def run_check() -> str:
        models = await provider.list_models()
        model_count = len([item for item in models if item])
        return (
            f"ollama reachable at {settings.ollama_base_url} "
            f"({ollama_resolution}; {model_count} models visible)"
        )

    ok, detail = await _run_probe("ollama", run_check)
    if ok:
        logger.info(
            "Ollama connectivity probe succeeded",
            extra=log_extra(
                service="api",
                ollama_base_url=settings.ollama_base_url,
                ollama_host_resolution=ollama_resolution,
                detail=detail,
            ),
        )
    else:
        logger.warning(
            "Ollama connectivity probe failed",
            extra=log_extra(
                service="api",
                ollama_base_url=settings.ollama_base_url,
                ollama_host_resolution=ollama_resolution,
                detail=detail,
            ),
        )
    return "ollama", (ok, detail)


async def _run_probe(name: str, probe: Callable[[], Awaitable[str]]) -> tuple[bool, str]:
    try:
        timeout_seconds = min(float(settings.startup_dependency_timeout_seconds), 5.0)
        detail = await asyncio.wait_for(probe(), timeout=timeout_seconds)
        return True, detail
    except Exception as exc:
        return False, f"{name} error: {exc}"


def _ollama_hostname() -> str:
    return urlparse(settings.ollama_base_url).hostname or "unknown"


def _resolve_hostname(hostname: str) -> str:
    if hostname == "unknown":
        return "hostname missing from OLLAMA_BASE_URL"
    try:
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(hostname, None)})
    except socket.gaierror as exc:
        return f"dns lookup failed for {hostname}: {exc}"
    return f"{hostname} -> {', '.join(addresses)}"
