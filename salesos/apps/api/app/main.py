from contextlib import asynccontextmanager
from time import monotonic

from fastapi import FastAPI

from app.api.router import api_router
from app.api.routes.leads import jobs
from app.clients.redis import redis_client
from app.core.exceptions import register_exception_handlers
from app.core.settings import settings
from app.core.startup import validate_startup_dependencies, validate_startup_settings, warmup_ollama_models
from app.middleware.request_context import RequestContextMiddleware
from salesos_shared.logging import configure_logging, get_logger, log_extra


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    app.state.started_at_monotonic = monotonic()
    validate_startup_settings()
    await validate_startup_dependencies()
    await warmup_ollama_models()
    await jobs.start_cleanup_loop()
    logger.info(
        "API startup complete",
        extra=log_extra(service="api", environment=settings.environment, port=settings.api_port),
    )
    yield
    await jobs.stop_cleanup_loop()
    await redis_client.aclose()


app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(RequestContextMiddleware)
register_exception_handlers(app)
app.include_router(api_router, prefix="/api")
