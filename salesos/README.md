# SalesOS

SalesOS is a local-first outbound operations platform built to run with Docker for the app stack and a local Windows Ollama instance for AI inference. The supported local environment is PostgreSQL, Redis, the FastAPI API, the Telegram bot, the Next.js dashboard, and n8n in Docker, with Ollama running on Windows at `http://localhost:11434`.

## What is included

- `apps/api`: FastAPI backend with dependency health endpoints, startup validation, and structured service logs.
- `apps/dashboard`: Next.js operator dashboard shell.
- `apps/telegram-bot`: Telegram bot service with local polling support, optional production webhooks, and Redis-backed alert state.
- `packages/shared/python`: shared logging, Redis, retry, and AI provider helpers.
- `packages/config/python`: central typed environment settings.
- `scripts/check_stack.py`: operator check for the local Docker stack and service endpoints.
- `scripts/wait_for_services.py`: dependency wait helper used by containers and local debugging.

## Docker networking

All Docker services join the `salesos` bridge network defined in `docker-compose.yml`. Inside that network, containers talk to each other by service name:

- PostgreSQL: `postgres:5432`
- Redis: `redis:6379`
- API: `api:8000`
- Telegram bot: `telegram-bot:8080`
- Dashboard: `dashboard:3000`
- n8n: `n8n:5678`

Ollama is the one exception. It is not part of the Compose network anymore. Containers reach the Windows host through Docker Desktop's special hostname:

- `OLLAMA_BASE_URL=http://host.docker.internal:11434`

On Windows, `host.docker.internal` resolves from inside Docker containers back to the host machine. That lets the API container call the already-running Windows Ollama process on port `11434` without starting a second Ollama container.

## Ollama on Windows

Run Ollama locally on Windows only. Do not run it both locally and in Docker.

- Local host URL: `http://localhost:11434`
- Container URL: `http://host.docker.internal:11434`
- Validation endpoint: `http://localhost:11434/api/tags`

The API probes `/api/tags` during startup validation and health checks, logs the exact Ollama URL in use, and retries connectivity before continuing. If `host.docker.internal` does not resolve inside Docker Desktop, the startup logs now surface that directly.

The default local-model settings are tuned for smaller local models:

- `OLLAMA_CLASSIFICATION_MODEL=phi3`
- `OLLAMA_SECONDARY_CLASSIFICATION_MODEL=phi3`
- `OLLAMA_REASONING_MODEL=gemma2:2b`
- `OLLAMA_PERSONALIZATION_MODEL=phi3`

## Startup sequencing

The stack starts in layers so slow services do not create noisy partial failures:

1. Docker Compose starts PostgreSQL and Redis first and waits for their health checks.
2. The API container runs `scripts/wait_for_services.py`, validates local Ollama reachability at `OLLAMA_BASE_URL`, then runs Alembic migrations and FastAPI.
3. During API lifespan startup, the app validates PostgreSQL, Redis, and Ollama again with structured logs before serving traffic.
4. The Telegram bot waits for Redis, validates its own startup config, and starts after Redis is reachable.
5. The dashboard starts after the API is healthy.
6. n8n starts independently on the same network with persistent storage.

This gives two layers of protection:

- Compose `depends_on` plus health checks for coarse sequencing.
- In-container dependency waits and API startup validation for readable diagnostics and graceful degradation.

## Environment setup

1. Copy `.env.example` to `.env`.
2. Set `OLLAMA_BASE_URL=http://host.docker.internal:11434`.
3. Install and start Ollama on Windows, then verify `http://localhost:11434/api/tags` responds.
4. Start Docker Desktop.
5. Run `make up`.
6. Optionally run `make wait-stack` and `make check-stack`.

Important environment groups:

- PostgreSQL:
  `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- Redis:
  `REDIS_URL`, `REDIS_OPERATION_TIMEOUT_SECONDS`, `REDIS_RETRY_ATTEMPTS`
- Ollama:
  `OLLAMA_BASE_URL`, `OLLAMA_*_MODEL`, `OLLAMA_TIMEOUT_SECONDS`, `OLLAMA_RETRY_ATTEMPTS`, `OLLAMA_KEEP_ALIVE`
- API and logging:
  `API_HOST`, `API_PORT`, `API_BASE_URL`, `LOG_LEVEL`
- Telegram:
  `TELEGRAM_BOT_TOKEN`, `TELEGRAM_USE_WEBHOOKS`, `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_ALERT_CHAT_IDS`, `TELEGRAM_ALLOWED_USER_IDS`, `TELEGRAM_BASE_URL`
- Startup behavior:
  `STARTUP_STRICT_VALIDATION`, `STARTUP_GRACE_PERIOD_SECONDS`, `STARTUP_DEPENDENCY_TIMEOUT_SECONDS`, `STARTUP_DEPENDENCY_RETRY_ATTEMPTS`, `STARTUP_DEPENDENCY_POLL_SECONDS`
- Lead reuse behavior:
  `PROCESS_EXISTING_LEADS`, `OUTREACH_COOLDOWN_HOURS`
- Lead lifecycle behavior:
  `PROCESS_EXISTING_LEADS`, `OUTREACH_COOLDOWN_HOURS`
- Development testing (opt-in, disabled by default):
  `SALESOS_DEV_FORCE_OUTREACH` (bypass outreach cooldown to regenerate messages on re-runs for testing)

## Local startup flow

1. `make up`
2. `docker compose ps`
3. `make logs`
4. `make check-stack`

Useful URLs after startup:

- API docs: `http://localhost:8000/docs`
- API live: `http://localhost:8000/api/live`
- API ready: `http://localhost:8000/api/ready`
- API health: `http://localhost:8000/api/health`
- Dashboard: `http://localhost:3000`
- Telegram bot live: `http://localhost:8080/live`
- Telegram bot ready: `http://localhost:8080/ready`
- Telegram bot health: `http://localhost:8080/health`
- Ollama tags: `http://localhost:11434/api/tags`
- n8n: `http://localhost:5678`

## Telegram mode selection

SalesOS supports two Telegram delivery modes:

- Local development: polling mode
- Production/public deployments: webhook mode

Local Docker environments should use polling mode because Telegram webhooks require:

- a public HTTPS URL
- valid public DNS
- a Telegram-reachable endpoint

Your local Docker bridge network and `localhost` URLs do not satisfy those requirements, so webhook registration will fail with host resolution or reachability errors.

Recommended local settings:

- `ENVIRONMENT=development`
- `TELEGRAM_USE_WEBHOOKS=false`
- `TELEGRAM_BASE_URL=` left empty

Production webhook settings:

- `ENVIRONMENT=production`
- `TELEGRAM_USE_WEBHOOKS=true`
- `TELEGRAM_BASE_URL=https://your-public-domain.example`
- `TELEGRAM_WEBHOOK_SECRET=<strong-secret>`

During startup the bot now logs:

- bot username from Telegram `getMe`
- selected mode: polling or webhook
- webhook URL when webhook mode is enabled
- polling startup success in local development

## Scrape stub mode

When `APIFY_TOKEN` is empty or set to `replace-me`, SalesOS runs the scrape pipeline in local stub mode instead of calling Apify.

Stub mode now uses JSON fixtures under `scripts/fixtures` instead of a tiny hardcoded in-memory list. This keeps local runs realistic and makes the pipeline easier to test repeatedly.

Current fixture set:

- `sample_leads`: realistic local business leads for normal pipeline testing
- `duplicate_leads`: repeated businesses for deduplication testing
- `malformed_leads`: incomplete and broken records for normalization failure testing

During stub or fixture execution, logs include:

- selected fixture name
- resolved fixture file path
- loaded lead count
- malformed record count
- fallback usage when an invalid fixture name is requested

Fixture testing flow:

1. Keep `APIFY_TOKEN=replace-me` for local stub mode.
2. Start the stack with `make up`.
3. Trigger a normal local scrape from Telegram with `/scrape marketing agency`.
4. Trigger an explicit fixture from the API or simulator with `python scripts/simulate_pipeline.py --fixture sample_leads`.

Mode selection:

- Local stub mode: `APIFY_TOKEN` missing, fixture-backed data is used automatically
- Explicit fixture mode: send `fixture_name` in the API payload or use `scripts/simulate_pipeline.py`
- Real Apify mode: set `APIFY_TOKEN` and the configured actor ID

## Existing lead reuse

The scrape pipeline now separates duplicate prevention from downstream AI execution.

- Duplicate prevention still stops duplicate lead inserts in PostgreSQL.
- Existing deduplicated leads can still be reused for enrichment, analysis, and outreach generation.
- Reuse is controlled by `PROCESS_EXISTING_LEADS=true`.

Cooldown protection:

- `OUTREACH_COOLDOWN_HOURS` prevents repeated outreach generation for the same lead inside the configured window.
- If a recent outreach exists for a lead, the pipeline logs the skip reason and continues without failing the rest of the run.

Pipeline summaries now include:

- `inserted`
- `deduplicated`
- `reused_existing`
- `analyzed`
- `personalized`
- `outreach_generated`
- `skipped_due_to_cooldown`

## Lead lifecycle state machine

SalesOS now tracks an explicit lead lifecycle in addition to the legacy `status` field used for backward compatibility.

Lifecycle states:

- `DISCOVERED`
- `ENRICHED`
- `QUALIFIED`
- `PERSONALIZED`
- `OUTREACH_READY`
- `CONTACTED`
- `REPLIED`
- `INTERESTED`
- `CLOSED`
- `REJECTED`
- `COOLDOWN`
- `FAILED`

Implementation notes:

- the current lifecycle state is stored on each lead
- state timestamps are stored on the lead record
- state transitions are also appended to a dedicated `lead_state_transitions` table
- repeated transitions to the same state are skipped idempotently
- structured logs emit `lead_state_transition_total` counters for each transition

## Heuristic scoring

Before deep personalization, SalesOS computes a lightweight heuristic score using signals such as:

- website presence
- email and phone completeness
- category relevance to the query
- city/location match
- review and rating activity
- optional active ads or social activity flags in source payloads

Tier behavior:

- `high`: full analysis plus deep AI personalization
- `medium`: heuristic analysis plus lightweight deterministic personalization
- `low`: skip personalization and mark the lead as `REJECTED`

## Windows setup guidance

1. Install Ollama for Windows and confirm the desktop app or background service is running.
2. Confirm `http://localhost:11434/api/tags` works in your browser or PowerShell before starting Compose.
3. Use Docker Desktop so Linux containers can resolve `host.docker.internal` back to Windows.
4. Keep Ollama out of `docker-compose.yml`; starting both a local `ollama.exe` process and a Docker Ollama container causes a port bind conflict on `11434`.

Why the conflict happened:

- Windows Ollama already bound `0.0.0.0:11434` or `127.0.0.1:11434`.
- Docker Compose tried to publish the Ollama container on the same host port with `11434:11434`.
- Only one process can own that socket, so Docker failed before the stack could finish starting.

## Health endpoints

The API exposes:

- `/api/live`: process liveness only
- `/api/ready`: dependency readiness for PostgreSQL, Redis, and Ollama
- `/api/health`: full service health summary with dependency details

The Telegram bot exposes:

- `/live`
- `/ready`
- `/health`

## Operational debugging

Structured JSON logs are emitted by the Python services. During startup you should see:

- startup configuration warnings such as unset Telegram secrets
- the exact `OLLAMA_BASE_URL` being used
- `host.docker.internal` DNS resolution details
- dependency validation attempts for PostgreSQL, Redis, and Ollama
- explicit retry and degradation logs if Ollama or other dependencies are slow or unreachable
- startup completion logs once the service is ready
- Telegram polling startup logs in local development, without webhook registration attempts

Helper commands:

- `make logs`: stream all container logs
- `make ps`: show container status
- `make wait-stack`: wait for key services from the host side
- `make check-stack`: run a host-side connectivity and health sweep
- `docker compose logs api redis postgres`: narrow the diagnosis to core dependencies

## Troubleshooting flow

1. Run `docker compose ps` and confirm the core containers are up.
2. Run `make check-stack` to see which dependency is failing first.
3. If API readiness is degraded, inspect `docker compose logs api` for dependency validation output.
4. If Ollama is the issue, test `http://localhost:11434/api/tags` on Windows first, then confirm the API logs show `host.docker.internal` resolving inside the container.
5. If PostgreSQL or Redis are the issue, inspect `docker compose logs postgres redis`.
6. If the dashboard is blank, confirm the API is healthy first, then inspect `docker compose logs dashboard`.
7. If strict startup is blocking boot, temporarily set `STARTUP_STRICT_VALIDATION=false` to continue local debugging while keeping `/api/health` available.

Telegram troubleshooting:

- If you see `Bad webhook: failed to resolve host`, disable webhooks locally with `TELEGRAM_USE_WEBHOOKS=false`.
- For local Docker use, do not set `TELEGRAM_BASE_URL` unless you are intentionally testing a public webhook endpoint.
- Follow bot logs with `docker logs -f salesos-telegram-bot` and confirm you see `Telegram bot authenticated` and `Telegram polling started`.

## Development testing: forcing outreach regeneration

During testing of outreach generation improvements, you may want to regenerate outreach for leads that already exist in the database without manually clearing the dedupe or cooldown records.

**Opt-in development bypass:**

Set `SALESOS_DEV_FORCE_OUTREACH=true` before running a scrape:

```bash
export SALESOS_DEV_FORCE_OUTREACH=true
curl -X POST http://localhost:8000/api/scrape \
  -H 'Content-Type: application/json' \
  -d '{"query":"marketing agency","location":"Austin, TX","max_results":5}'
```

**Behavior:**

- Existing leads still deduplicate normally (no changes to dedupe logic)
- All pipeline stages run as normal (enrichment, analysis, scoring)
- Outreach **cooldown checks are bypassed** so new outreach is generated even if recent outreach exists
- All logs will contain `DEV_FORCE_REPROCESS` marker so you can identify forced regeneration runs
- No production behavior is changed when the flag is disabled (default)

**Important:**

- This is development-only and must be explicitly enabled
- Do not use in production or with real contact data
- After testing, disable the flag before committing code

## Ollama troubleshooting

Verify Ollama is running on Windows:

- PowerShell: `Invoke-WebRequest http://localhost:11434/api/tags | Select-Object -ExpandProperty StatusCode`
- Browser: open `http://localhost:11434/api/tags`
- CLI: `ollama list`

Test Docker-to-host connectivity:

- `docker compose exec api python /workspace/salesos/scripts/wait_for_services.py --service ollama --timeout 10 --interval 2`
- `docker compose exec api sh -lc "wget -qO- http://host.docker.internal:11434/api/tags"`

Kill duplicate Ollama processes if needed:

- PowerShell: `Get-Process ollama -ErrorAction SilentlyContinue`
- PowerShell: `Stop-Process -Name ollama -Force`

Common port conflict signs:

- `bind: Only one usage of each socket address is normally permitted`
- Compose failing on `11434:11434`
- A second Ollama instance already running in Docker or Windows

Typical failure patterns:

- `ollama error`: the Windows Ollama process is not reachable from Docker, `host.docker.internal` did not resolve, or Ollama is still starting locally.
- `database error`: PostgreSQL is not healthy, credentials do not match `.env`, or migrations failed.
- `redis error`: Redis is not reachable on the Compose network or the URL is malformed.
- `starting` readiness status: the service is still within the configured startup grace window.

## Useful commands

- `make up`: build and start the full stack
- `make down`: stop the stack
- `make logs`: stream service logs
- `make ps`: list container status
- `make migrate`: run Alembic migrations inside the API container
- `make validate`: compile-check the Python services locally
- `make compose-config`: render and validate the Compose config
- `make wait-stack`: wait for core services to become reachable
- `make check-stack`: run a local stack diagnostic sweep
- `make pipeline-sim`: run the sample fixture through the local pipeline
- `make pipeline-sim-duplicates`: validate deduplication behavior
- `make pipeline-sim-malformed`: validate malformed lead handling

See `PROJECT_SCOPE.md`, `SYSTEM_ARCHITECTURE.md`, and `docs/architecture.md` for the broader architecture rationale.
