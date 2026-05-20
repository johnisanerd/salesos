# SalesOS

A **local-first outbound operations platform** designed for lead generation, enrichment, and outreach coordination. SalesOS runs entirely in Docker with a local Windows Ollama instance for on-device AI inference, making it privacy-focused and suitable for developer laptops or small local servers.

## 🎯 What SalesOS Does

- **Lead Scraping**: Ingest leads from Google Maps and other sources
- **Lead Normalization**: Standardize lead data into canonical formats
- **Deduplication**: Prevent duplicate leads using fingerprinting
- **AI-Powered Analysis**: Classify and score leads using local Ollama models
- **Operator Alerts**: Dispatch lead summaries to Telegram for real-time notifications
- **Workflow Automation**: Orchestrate complex outreach sequences via n8n
- **Local Dashboard**: Monitor system status and lead pipeline

## 📦 What is Included

- **`apps/api`**: FastAPI backend orchestrating the entire lead pipeline, with health endpoints, startup validation, and structured logging
- **`apps/dashboard`**: Next.js operator dashboard for system monitoring
- **`apps/telegram-bot`**: Telegram bot service with local polling support and Redis-backed alert state
- **`packages/shared/python`**: Shared logging, Redis, retry utilities, and AI provider abstractions
- **`packages/config/python`**: Centralized typed environment settings
- **`scripts/`**: Operator utilities for stack validation and pipeline testing
- **`infrastructure/`**: Docker configurations and database initialization scripts

## 🚀 Quick Start

### Prerequisites
- **Docker Desktop** (with Docker Compose)
- **Ollama** installed on Windows ([download](https://ollama.ai))
- **.env file** with required configuration (see [Setup](#-setup) section)

### 1. Start Ollama on Windows
```bash
# Run Ollama on your Windows machine (not in Docker)
ollama pull phi3 gemma2:2b
# Ollama will listen at http://localhost:11434
```

### 2. Start the Stack
```bash
make up           # Start all services
make wait-stack   # Wait for services to be healthy
make check-stack  # Verify all endpoints
```

### 3. Access Services
- **API**: http://localhost:8000 (Swagger docs at `/docs`)
- **Dashboard**: http://localhost:3000
- **Telegram Bot**: Internal service (sends alerts to configured chats)
- **n8n**: http://localhost:5678
- **Postgres**: localhost:5432

## 🏗️ System Architecture

### Service Responsibilities
- **API** (`apps/api`): Orchestration, lead persistence, workflow logging
- **Telegram Bot** (`apps/telegram-bot`): Alert handling, operator notifications
- **Dashboard** (`apps/dashboard`): Operator UI for system monitoring
- **Shared Packages**: Common utilities (logging, Redis, AI providers)

### First Pipeline Slice (Lead Ingestion)
1. Operator triggers `POST /api/leads/scrape`
2. API fetches leads from Apify (or stub mode if unconfigured)
3. Raw payloads are normalized into canonical `LeadCreate` shape
4. Leads deduplicated by fingerprint and stored in PostgreSQL
5. Workflow events recorded for auditability
6. Analysis and enrichment stubs process new leads
7. Pipeline summary written to Redis cache
8. Alert posted to Telegram bot service

### Docker Networking

All services join the `salesos` network and communicate by service name:

| Service | Host | Port |
|---------|------|------|
| PostgreSQL | `postgres` | 5432 |
| Redis | `redis` | 6379 |
| API | `api` | 8000 |
| Telegram Bot | `telegram-bot` | 8080 |
| Dashboard | `dashboard` | 3000 |
| n8n | `n8n` | 5678 |

**Ollama** runs on the Windows host (not in Docker) and is accessed via `host.docker.internal:11434` from containers.

## ⚙️ Setup

### Environment Configuration

Create a `.env` file in the project root:

```env
# Database
POSTGRES_DB=salesos
POSTGRES_USER=salesos
POSTGRES_PASSWORD=secure_password
POSTGRES_PORT=5432

# API
API_ENV=development
API_LOG_LEVEL=INFO

# Ollama (Windows local instance)
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_CLASSIFICATION_MODEL=phi3
OLLAMA_SECONDARY_CLASSIFICATION_MODEL=phi3
OLLAMA_REASONING_MODEL=gemma2:2b
OLLAMA_PERSONALIZATION_MODEL=phi3

# Redis
REDIS_URL=redis://redis:6379

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Apify (optional)
APIFY_TOKEN=your_apify_token_optional
```

### Ollama on Windows

**Critical**: Run Ollama only on Windows, not in Docker.

- **Local host URL**: `http://localhost:11434`
- **Container access URL**: `http://host.docker.internal:11434`
- **Validation endpoint**: `http://localhost:11434/api/tags`

The API validates Ollama connectivity during startup. If `host.docker.internal` fails to resolve, check Docker Desktop settings and restart if needed.

**Default Models** (tuned for smaller local GPUs):
- `phi3` - Classification and personalization
- `gemma2:2b` - Reasoning tasks

## 📋 Common Commands

```bash
# Stack management
make up                      # Start all services in background
make down                    # Stop all services
make ps                      # Show running containers
make logs                    # Stream logs from all services
make rebuild                 # Rebuild images (skip cache)

# Development
make api-shell              # Shell into API container
make bot-shell              # Shell into Telegram bot container
make migrate                # Run database migrations
make validate               # Validate Python syntax

# Testing & Debugging
make check-stack            # Verify all services are healthy
make wait-stack             # Wait for services to be ready
make pipeline-sim           # Simulate lead pipeline
make pipeline-sim-duplicates # Test duplicate handling
make pipeline-sim-malformed # Test malformed data handling
```

## 📚 Documentation

- [System Architecture](docs/architecture.md) - Detailed service design
- [Project Scope](PROJECT_SCOPE.md) - In-scope and out-of-scope features
- [File Map](docs/file-map.md) - Directory structure reference
- [API Reference](apps/api/README.md) - API endpoints and usage

## 🔧 Troubleshooting

### Services won't start
```bash
make check-stack  # See which services are failing
docker compose logs api  # Check API logs specifically
```

### Ollama connection errors
- Ensure Ollama is running: `curl http://localhost:11434/api/tags`
- Verify `OLLAMA_BASE_URL` in `.env` points to `http://host.docker.internal:11434`
- Restart Docker Desktop if DNS resolution fails

### Database migrations failed
```bash
make migrate  # Re-run migrations
```

## 📝 Project Status

**Current Phase**: Operational foundation with stable lead pipeline

**In Scope**: Lead scraping, normalization, deduplication, local AI analysis, Telegram alerts

**Out of Scope**: Multi-tenancy, Kubernetes, autonomous negotiation, payment processing

## 📄 License

Proprietary

---

**Need more info?** Check [docs/architecture.md](docs/architecture.md) for detailed service design and [PROJECT_SCOPE.md](PROJECT_SCOPE.md) for current capabilities and roadmap.

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
