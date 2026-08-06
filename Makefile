SHELL := /bin/bash

.PHONY: help up dev dev-web backend stop restart logs status clean rebuild-web

help:
	@echo "SirisOS commands"
	@echo ""
	@echo "  make up          Build and start the complete SirisOS stack"
	@echo "  make dev         Start backend and Flutter hot-reload web server"
	@echo "  make dev-web     Alias for make dev"
	@echo "  make backend     Start backend services only"
	@echo "  make rebuild-web Rebuild only the Docker-served web UI"
	@echo "  make stop        Stop all SirisOS services"
	@echo "  make restart     Rebuild and restart the complete stack"
	@echo "  make logs        Follow all service logs"
	@echo "  make status      Show service status and health endpoints"
	@echo "  make clean       Stop services and remove Flutter build output"

up:
	@test -f .env || cp .env.example .env
	@mkdir -p data/postgres data/logs data/backups data/uploads
	@docker compose up --build -d
	@echo ""
	@echo "SirisOS Web: http://192.168.0.100:6464"
	@echo "SirisOS API: http://192.168.0.100:8000"

dev: dev-web

dev-web:
	@bash scripts/dev-web.sh

backend:
	@bash scripts/backend-up.sh

rebuild-web:
	@docker compose build --no-cache web
	@docker compose up -d web

stop:
	@docker compose down

restart:
	@docker compose down
	@docker compose up --build -d

logs:
	@docker compose logs -f

status:
	@docker compose ps
	@echo ""
	@curl --fail --silent http://localhost:8000/health || true
	@echo ""
	@curl --fail --silent http://localhost:6464/health || true
	@echo ""

clean:
	@docker compose down
	@cd apps/mobile && flutter clean
