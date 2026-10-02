SHELL := /bin/bash
PORT := $(or $(shell grep -E '^SIRISOS_PORT=' .env 2>/dev/null | tail -1 | cut -d= -f2),8094)

.PHONY: help up dev dev-web backend stop restart logs status hub-check clean rebuild-app

help:
	@echo "SirisOS commands"
	@echo ""
	@echo "  make up          Build and start the complete SirisOS stack"
	@echo "  make dev         Start backend and the Vite hot-reload web server"
	@echo "  make dev-web     Alias for make dev"
	@echo "  make backend     Start backend services only for local development"
	@echo "  make rebuild-app Rebuild only the unified SirisOS application container"
	@echo "  make stop        Stop all SirisOS services"
	@echo "  make restart     Rebuild and restart the complete stack"
	@echo "  make logs        Follow all service logs"
	@echo "  make status      Show service status and SirisOS health"
	@echo "  make hub-check   Check every connected app from inside the container"
	@echo "  make clean       Stop services and remove web build output"

up:
	@test -f .env || cp .env.example .env
	@mkdir -p data/postgres data/logs data/standards data/app
	@docker compose up --build -d --remove-orphans
	@echo ""
	@echo "SirisOS: http://192.168.0.100:$(PORT)"
	@echo "API docs: http://192.168.0.100:$(PORT)/docs"

dev: dev-web

dev-web:
	@bash scripts/dev-web.sh

backend:
	@bash scripts/backend-up.sh

rebuild-app:
	@docker compose build --no-cache sirisos
	@docker compose up -d --remove-orphans sirisos

stop:
	@docker compose down --remove-orphans

restart:
	@docker compose down --remove-orphans
	@docker compose up --build -d --remove-orphans

logs:
	@docker compose logs -f

status:
	@docker compose ps
	@echo ""
	@curl --fail --silent http://localhost:$(PORT)/health || true
	@echo ""

hub-check:
	@docker compose exec sirisos python -m app.hub.check

clean:
	@docker compose down --remove-orphans
	@rm -rf apps/web/dist
