SHELL := /bin/bash

.PHONY: help dev dev-web backend stop restart logs status clean

help:
	@echo "SirisOS development commands"
	@echo ""
	@echo "  make dev       Start backend services and launch Flutter Web"
	@echo "  make dev-web   Alias for make dev"
	@echo "  make backend   Start backend services only"
	@echo "  make stop      Stop backend services"
	@echo "  make restart   Rebuild and restart backend services"
	@echo "  make logs      Follow backend service logs"
	@echo "  make status    Show service status and API health"
	@echo "  make clean     Stop services and remove generated Flutter build files"

dev: dev-web

dev-web:
	@bash scripts/dev-web.sh

backend:
	@bash scripts/backend-up.sh

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

clean:
	@docker compose down
	@cd apps/mobile && flutter clean
