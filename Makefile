SHELL := /bin/bash

.PHONY: help up dev dev-web backend stop restart logs status clean rebuild-app

help:
	@echo "SirisOS commands"
	@echo ""
	@echo "  make up          Build and start the complete SirisOS stack"
	@echo "  make dev         Start backend and Flutter hot-reload web server"
	@echo "  make dev-web     Alias for make dev"
	@echo "  make backend     Start backend services only for local development"
	@echo "  make rebuild-app Rebuild only the unified SirisOS application container"
	@echo "  make stop        Stop all SirisOS services"
	@echo "  make restart     Rebuild and restart the complete stack"
	@echo "  make logs        Follow all service logs"
	@echo "  make status      Show service status and SirisOS health"
	@echo "  make clean       Stop services and remove Flutter build output"

up:
	@test -f .env || cp .env.example .env
	@mkdir -p data/postgres data/logs data/backups data/uploads data/standards data/knowledge
	@docker compose up --build -d --remove-orphans
	@echo ""
	@echo "SirisOS: http://192.168.0.100:6464"
	@echo "API docs: http://192.168.0.100:6464/docs"

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
	@curl --fail --silent http://localhost:6464/health || true
	@echo ""

clean:
	@docker compose down --remove-orphans
	@cd apps/mobile && flutter clean
