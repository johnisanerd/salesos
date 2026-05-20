# SalesOS Architecture

## Design goals

SalesOS is structured as operational infrastructure rather than a conversational assistant. The architecture favors local reliability, thin transport layers, and explicit workflow boundaries so the system can be debugged by operators running it on a single machine or a small server.

## Service layout

- `apps/api` exposes the orchestration API, webhook-safe endpoints, and the core database-backed workflow services.
- `apps/telegram-bot` exposes a dedicated webhook application for Telegram commands and alert delivery.
- `apps/dashboard` provides the operator surface and can grow independently from the backend deployment cadence.

## Python package boundaries

- `packages/config/python/salesos_config` centralizes typed environment settings to prevent config drift between services.
- `packages/shared/python/salesos_shared` holds reusable logging, ID/timestamp mixins, and AI-provider abstractions.

## Backend layering

- Routes map HTTP input to schemas and delegate immediately to services.
- Services own orchestration logic across AI calls, repositories, and workflow logging.
- Repositories isolate frequently reused database access patterns without forcing every query through an abstraction.
- Models are split per table to avoid a monolithic ORM layer.
- A dedicated pipeline observer records stage timing, status transitions, and error fields without pushing observability logic into routes or repositories.

## AI strategy

- Ollama is the only provider used initially.
- The `AIProvider` interface and `JSONModelGenerator` keep model invocation and validation decoupled from business services.
- Model selection lives in config, not in route handlers or prompt code.
- Ollama runs on the Windows host and is addressed from containers as `http://host.docker.internal:11434`.
- Ollama calls use explicit timeout, retry, keep-alive, and tolerant JSON extraction so local model instability does not collapse the pipeline.

## Redis role

- Redis stores the latest scrape summary for `/status` and `/stats`.
- Redis stores recent pipeline events keyed by workflow run for fast local debugging.
- Redis stores Telegram alert cache so `/hot_leads` remains useful even when external Telegram delivery is unavailable.

## Operational path today

1. Scrape request enters through `POST /api/leads/scrape`.
2. The Apify service either triggers a real actor run or returns deterministic stub leads when Apify is not configured.
3. Raw lead payloads are normalized into a canonical internal schema.
4. Leads are deduplicated via normalized fingerprint before insertion.
5. The API records workflow logs and enrichment stubs in PostgreSQL.
6. The AI layer attempts Ollama analysis and personalization, then falls back to local stub responses if Ollama is unavailable.
7. Every pipeline stage emits a structured event with workflow event ID, stage, status, duration, IDs, and error fields.
8. The latest pipeline summary and recent stage events are cached in Redis for operator visibility.
9. The API sends an internal alert to the Telegram bot service, which caches and optionally fan-outs the notification to Telegram chats.

## Startup flow

1. PostgreSQL and Redis start first under Docker Compose.
2. Compose health checks gate the API on PostgreSQL and Redis reaching a healthy state.
3. The API container runs `scripts/wait_for_services.py`, executes Alembic migrations, validates settings, validates PostgreSQL, Redis, and Ollama again with structured logs, and then exposes `/live`, `/ready`, and `/health`.
4. The API readiness check probes PostgreSQL, Redis, and Ollama in parallel and reports `starting` during the startup grace window.
5. The Telegram bot waits for Redis, validates settings, initializes the webhook application, and exposes its internal alert endpoint plus `/live`, `/ready`, and `/health`.
6. The dashboard waits on API readiness and remains intentionally thin.
7. Operator scripts such as `scripts/check_stack.py` provide host-side diagnostics across published ports for debugging local Docker issues.

## Docker network model

- Every container joins the shared `salesos` bridge network in Compose.
- Service-to-service traffic uses Docker DNS names such as `postgres`, `redis`, `api`, and `telegram-bot`.
- Ollama is reached from containers via Docker Desktop host routing at `host.docker.internal`.
- Host-to-container traffic uses published `localhost` ports only for local operator access and debugging.
- Persistent named volumes are used for PostgreSQL, Redis, n8n, and dashboard `node_modules` so local restarts are predictable.

## Failure handling

- Apify requests retry and fall back to deterministic stub results if remote scrape submission fails.
- Redis operations go through a typed helper with retry, timeout, and TTL-aware JSON storage.
- Ollama calls use timeout, retry, malformed JSON extraction, and fallback stub responses.
- Startup dependency validation emits readable structured diagnostics before the API begins serving traffic.
- Non-critical stages such as enrichment, analysis, personalization, Redis summary write, and Telegram alerting run as resilient stages so one failure does not abort the full scrape workflow.

## What is intentionally deferred

- Multi-tenant SaaS concerns
- billing
- advanced RBAC
- Kubernetes deployment
- autonomous negotiation loops
- deep frontend polish

Those concerns would add complexity before the core outbound operations loop is stable.
