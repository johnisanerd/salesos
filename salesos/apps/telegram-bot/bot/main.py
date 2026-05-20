from contextlib import asynccontextmanager
from time import monotonic

from fastapi import FastAPI, Header, HTTPException, Request
from telegram.error import TelegramError
from telegram import Update

from bot.application import build_application
from bot.config import settings
from bot.schemas import InternalAlertRequest
from bot.services.alerts import AlertFanoutService
from bot.services.startup import telegram_mode, telegram_webhook_url, validate_startup_settings
from bot.state import redis_state
from salesos_shared.logging import configure_logging, get_logger, log_extra


telegram_application = build_application()
logger = get_logger(__name__)
telegram_enabled = settings.telegram_bot_token not in {"", "replace-me"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    app.state.started_at_monotonic = monotonic()
    validate_startup_settings()
    if telegram_enabled:
        await telegram_application.initialize()
        bot_profile = await telegram_application.bot.get_me()
        app.state.telegram_bot_username = bot_profile.username
        mode = telegram_mode()
        logger.info(
            "Telegram bot authenticated",
            extra=log_extra(
                service="telegram-bot",
                environment=settings.environment,
                mode=mode,
                bot_username=bot_profile.username,
                webhook_url=telegram_webhook_url() if mode == "webhook" else None,
            ),
        )
        await telegram_application.start()
        if mode == "webhook":
            try:
                await telegram_application.bot.set_webhook(
                    url=telegram_webhook_url(),
                    secret_token=settings.telegram_webhook_secret,
                )
                logger.info(
                    "Telegram webhook configured",
                    extra=log_extra(
                        service="telegram-bot",
                        mode=mode,
                        bot_username=bot_profile.username,
                        webhook_url=telegram_webhook_url(),
                    ),
                )
            except TelegramError as exc:
                logger.error(
                    "Telegram webhook setup failed",
                    extra=log_extra(
                        service="telegram-bot",
                        mode=mode,
                        bot_username=bot_profile.username,
                        webhook_url=telegram_webhook_url(),
                        error=str(exc),
                    ),
                )
                raise RuntimeError(f"Telegram webhook setup failed: {exc}") from exc
        else:
            await telegram_application.bot.delete_webhook(drop_pending_updates=False)
            if telegram_application.updater is None:
                raise RuntimeError("Telegram polling mode requires an updater-enabled application")
            await telegram_application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=False,
            )
            logger.info(
                "Telegram polling started",
                extra=log_extra(
                    service="telegram-bot",
                    mode=mode,
                    bot_username=bot_profile.username,
                ),
            )
    logger.info(
        "Telegram bot startup complete",
        extra=log_extra(
            service="telegram-bot",
            environment=settings.environment,
            port=settings.telegram_bot_port,
            mode=telegram_mode(),
            polling_enabled=telegram_enabled and telegram_mode() == "polling",
            webhook_enabled=telegram_enabled and telegram_mode() == "webhook",
        ),
    )
    yield
    await redis_state.close()
    if telegram_enabled:
        if telegram_mode() == "polling" and telegram_application.updater is not None:
            await telegram_application.updater.stop()
        await telegram_application.stop()
        await telegram_application.shutdown()


app = FastAPI(title="SalesOS Telegram Bot", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health(request: Request) -> dict:
    redis_ok = False
    try:
        redis_ok = bool(await redis_state.ping())
    except Exception:
        redis_ok = False
    grace = monotonic() - getattr(request.app.state, "started_at_monotonic", monotonic())
    status = "ok" if redis_ok else ("starting" if grace < settings.startup_grace_period_seconds else "degraded")
    return {"status": status, "service": "telegram-bot", "redis": redis_ok}


@app.get("/live")
async def live() -> dict:
    return {"status": "ok", "service": "telegram-bot"}


@app.get("/ready")
async def readiness(request: Request) -> dict:
    redis_ok = False
    try:
        redis_ok = bool(await redis_state.ping())
    except Exception:
        redis_ok = False
    grace = monotonic() - getattr(request.app.state, "started_at_monotonic", monotonic())
    status = "ok" if redis_ok else ("starting" if grace < settings.startup_grace_period_seconds else "degraded")
    return {"status": status, "service": "telegram-bot", "redis": redis_ok}


@app.get("/health/ready")
async def readiness_legacy(request: Request) -> dict:
    return await readiness(request)


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    if not telegram_enabled:
        raise HTTPException(status_code=503, detail="Telegram bot token is not configured")
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    payload = await request.json()
    update = Update.de_json(payload, telegram_application.bot)
    await telegram_application.process_update(update)
    return {"status": "accepted"}


@app.post("/internal/alerts")
async def internal_alert(
    payload: InternalAlertRequest,
    x_internal_service_token: str | None = Header(default=None),
) -> dict:
    if x_internal_service_token != settings.internal_service_token:
        raise HTTPException(status_code=401, detail="Invalid internal service token")
    return await AlertFanoutService(telegram_application.bot).dispatch(payload)
