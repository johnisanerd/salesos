PROJECT_DIR := $(CURDIR)
COMPOSE := docker compose

.PHONY: up down logs ps rebuild api-shell bot-shell migrate dashboard-install format validate compose-config pipeline-sim pipeline-sim-duplicates pipeline-sim-malformed fake-scrape check-stack wait-stack

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=200

ps:
	$(COMPOSE) ps

rebuild:
	$(COMPOSE) build --no-cache

api-shell:
	$(COMPOSE) exec api /bin/sh

bot-shell:
	$(COMPOSE) exec telegram-bot /bin/sh

migrate:
	$(COMPOSE) exec api alembic upgrade head

validate:
	python -m compileall apps/api/app apps/telegram-bot/bot packages/shared/python packages/config/python

compose-config:
	$(COMPOSE) config

wait-stack:
	python scripts/wait_for_services.py --service postgres --service redis --service ollama --service api --service telegram-bot

check-stack:
	python scripts/check_stack.py

pipeline-sim:
	python scripts/simulate_pipeline.py --fixture sample_leads

pipeline-sim-duplicates:
	python scripts/simulate_pipeline.py --fixture duplicate_leads

pipeline-sim-malformed:
	python scripts/simulate_pipeline.py --fixture malformed_leads

fake-scrape:
	python scripts/generate_fake_scrape.py --count 5

dashboard-install:
	cd apps/dashboard && npm install

format:
	$(COMPOSE) exec api sh -lc "python -m compileall app ../../packages/shared/python ../../packages/config/python"
