# Project Scope

SalesOS is a local-first outbound operations system. The current scope is to provide a stable operational foundation that can run on a developer laptop or small local server using Docker Compose, PostgreSQL, Redis, Ollama, FastAPI, Next.js, Telegram, and n8n.

## In scope now

- Google Maps scrape intake
- lead normalization and deduplication
- PostgreSQL lead storage
- enrichment stub logging
- Ollama-backed analysis with local stub fallback
- personalization stub generation
- Telegram alert dispatch through the local bot service
- structured logging and dependency health checks

## Explicitly out of scope now

- billing
- multi-tenancy
- Kubernetes
- advanced frontend product UX
- autonomous sales negotiation
- payment automation

The goal of this phase is operational reliability, clean architecture, and a fast local development loop.
