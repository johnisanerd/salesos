# SalesOS Contributor Guide

## Operating rules

- Keep route handlers thin; business logic belongs in services.
- Prefer adding new workflow-specific services instead of expanding generic utility modules.
- Preserve the local-first default: Docker Compose, PostgreSQL, Redis, Ollama, and n8n are first-class dependencies.
- Reuse shared settings and logging utilities from `packages/config/python` and `packages/shared/python`.
- Add Alembic migrations for any schema changes and keep models in sync.
- Avoid giant files; split routers, services, repositories, and schemas by domain concern.

## Architectural boundaries

- `apps/api` owns ingestion, orchestration APIs, and database-backed workflows.
- `apps/telegram-bot` owns Telegram commands, alerts, and webhook handling.
- `apps/dashboard` owns operator visibility, not customer-facing product flows.
- `packages/shared/python` owns reusable Python primitives that are not app-specific.
- `packages/config/python` owns strongly typed environment settings.

## Near-term roadmap

- Add Apify callback signing verification.
- Add background workers for enrichment and reply processing.
- Add Grafana/Loki and n8n workflow exports.
- Add API fallback providers behind the AI abstraction once local-model behavior is stable.
