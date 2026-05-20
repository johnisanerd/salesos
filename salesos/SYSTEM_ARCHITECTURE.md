# System Architecture

## Service responsibilities

- `apps/api` owns orchestration, persistence, workflow logging, and the first operational pipeline.
- `apps/telegram-bot` owns webhook handling, Redis-backed operator state, and fan-out of internal alerts to Telegram chats.
- `apps/dashboard` provides a thin operator view over the local system.
- `packages/config/python` holds typed settings shared by Python services.
- `packages/shared/python` holds cross-service primitives such as JSON logging, database mixins, and AI provider abstractions.

## First pipeline slice

1. An operator triggers `POST /api/leads/scrape`.
2. The API uses the Apify integration layer. If Apify is not configured, it runs in deterministic stub mode.
3. Raw lead payloads are normalized into the canonical `LeadCreate` shape.
4. Leads are deduplicated by normalized fingerprint and stored in PostgreSQL.
5. Workflow events are recorded in `workflow_logs`.
6. Enrichment, analysis, and personalization stubs run for newly inserted leads.
7. The API writes the latest pipeline summary into Redis.
8. The API posts a local internal alert to the Telegram bot service.
9. The Telegram bot caches the alert in Redis and optionally forwards it to configured Telegram chats.

## Startup flow

1. Docker Compose starts PostgreSQL, Redis, and Ollama first.
2. The API waits on those dependencies, runs Alembic migrations, validates configuration, and starts FastAPI.
3. The Telegram bot validates configuration, initializes the webhook application, and exposes the internal alert endpoint.
4. The dashboard waits for a healthy API before starting.
