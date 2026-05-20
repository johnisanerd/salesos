# SalesOS File Map

This map explains why the main scaffold files exist so the structure stays intentional as the codebase grows.

## Root

- `README.md`: setup, scope, and operator-oriented overview.
- `AGENTS.md`: contributor rules and architectural boundaries.
- `PROJECT_SCOPE.md`: current delivery boundaries and intentional non-goals.
- `SYSTEM_ARCHITECTURE.md`: service responsibilities, startup flow, and event flow.
- `.env.example`: single source of expected runtime configuration.
- `docker-compose.yml`: local-first service orchestration.
- `Makefile`: common operational commands for developers.

## API app

- `apps/api/app/main.py`: FastAPI entrypoint and middleware registration.
- `apps/api/app/api/router.py`: top-level router composition.
- `apps/api/app/api/routes/*.py`: thin, domain-scoped HTTP handlers.
- `apps/api/app/core/settings.py`: app-local accessor for shared settings.
- `apps/api/app/core/startup.py`: startup validation and configuration warnings.
- `apps/api/app/core/exceptions.py`: centralized exception responses.
- `apps/api/app/clients/redis.py`: shared Redis client for API operational state.
- `apps/api/app/db/*`: declarative base and async session factory.
- `apps/api/app/middleware/request_context.py`: request ID propagation for structured logs.
- `apps/api/app/models/*.py`: split ORM models by table for maintainability.
- `apps/api/app/repositories/*.py`: reusable persistence operations.
- `apps/api/app/schemas/*.py`: transport models for request and response validation.
- `apps/api/app/services/normalization_service.py`: canonical lead normalization before dedupe.
- `apps/api/app/services/scrape_pipeline_service.py`: end-to-end orchestration for the first operational pipeline slice.
- `apps/api/app/services/pipeline_observer.py`: structured pipeline events, timing, and stage persistence.
- `apps/api/app/services/health_service.py`: dependency-aware readiness checks.
- `apps/api/app/services/*.py`: orchestration logic for scraping, enrichment, AI, replies, and alerts.
- `apps/api/alembic/*`: migration environment and initial schema creation.

## Telegram bot

- `apps/telegram-bot/bot/main.py`: webhook app entrypoint.
- `apps/telegram-bot/bot/application.py`: command and callback handler registration.
- `apps/telegram-bot/bot/handlers/*.py`: modular command handlers.
- `apps/telegram-bot/bot/schemas.py`: internal alert contract for local service-to-service notification.
- `apps/telegram-bot/bot/services/api_client.py`: bot-to-API trigger path for fixture-backed pipeline validation.
- `apps/telegram-bot/bot/services/alerts.py`: Redis caching and optional Telegram fan-out for operator alerts.
- `apps/telegram-bot/bot/services/startup.py`: bot startup validation.
- `apps/telegram-bot/bot/services/*.py`: notification formatting and access control helpers.
- `apps/telegram-bot/bot/state.py`: Redis connection for ephemeral bot state.

## Dashboard

- `apps/dashboard/app/*`: Next.js app-router pages and global styling.
- `apps/dashboard/components/ui/*`: lightweight shadcn-style primitives for reuse.
- `apps/dashboard/lib/utils.ts`: shared frontend utility helpers.
- `apps/dashboard/tailwind.config.ts`: dashboard visual system tokens.

## Shared packages

- `packages/config/python/salesos_config/settings.py`: typed environment contract across Python services.
- `packages/shared/python/salesos_shared/logging.py`: JSON logging and request context.
- `packages/shared/python/salesos_shared/redis.py`: typed Redis state wrapper with retry-safe JSON helpers.
- `packages/shared/python/salesos_shared/retry.py`: shared timeout and retry helper for local integrations.
- `packages/shared/python/salesos_shared/db.py`: UUID and timestamp mixins.
- `packages/shared/python/salesos_shared/ai.py`: provider abstraction and validated JSON generation helper.
- `packages/types/index.ts`: shared frontend-oriented pipeline types.

## Infrastructure and support

- `infrastructure/docker/*/Dockerfile`: per-service container recipes.
- `infrastructure/postgres/init.sql`: database bootstrap helpers.
- `infrastructure/nginx/README.md`: reserved ingress area for future consolidation.
- `n8n-workflows/README.md`: location for exported automation flows.
- `scripts/bootstrap.sh`: quick local bootstrap for Unix-like environments.
- `scripts/simulate_pipeline.py`: end-to-end local pipeline trigger using deterministic fixtures.
- `scripts/fixtures/*.json`: deterministic fixture sets for normal, duplicate, and malformed scrape inputs.
- `scripts/dev-check.ps1`: quick validation helper for Windows operators.
