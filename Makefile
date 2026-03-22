# =============================================================================
# Manic-AI — Development Commands
# =============================================================================
.PHONY: help dev up down test lint build clean logs status setup setup-deps setup-hooks verify monitoring

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Docker Compose
# ---------------------------------------------------------------------------
up: ## Start all services
	docker compose up -d

down: ## Stop all services
	docker compose down

dev: ## Start services with dev overrides (hot-reload)
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

logs: ## Tail logs for all services
	docker compose logs -f --tail=50

status: ## Show service status
	docker compose ps

monitoring: ## Start monitoring stack (Prometheus + Grafana)
	docker compose --profile monitoring up -d

clean: ## Stop all services and remove volumes
	docker compose down -v --remove-orphans

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------
test: test-api test-frontend ## Run all tests

test-api: ## Run API tests (Python)
	cd api && python -m pytest --tb=short -q

test-frontend: ## Run frontend tests (Jest)
	cd frontend && npm test

test-coverage: ## Run API tests with coverage report
	cd api && python -m pytest --cov=api --cov-report=term-missing --tb=short

# ---------------------------------------------------------------------------
# Linting
# ---------------------------------------------------------------------------
lint: lint-api lint-frontend ## Run all linters

lint-api: ## Lint Python code (ruff)
	ruff check api/

lint-frontend: ## Lint frontend code (eslint)
	cd frontend && npm run lint

lint-fix: ## Auto-fix Python lint issues
	ruff check --fix api/
	ruff format api/

# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------
build: build-api build-frontend ## Build all containers

build-api: ## Build API Docker image
	docker build -t manic-ai-api:local ./api

build-frontend: ## Build frontend Docker image
	docker build -t manic-ai-frontend:local ./frontend

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
setup: setup-deps setup-hooks ## Full project setup
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")
	@echo ""
	@echo "Setup complete. Next steps:"
	@echo "  1. Edit .env with your secrets"
	@echo "  2. Run: make up"
	@echo "  3. Run: python scripts/setup_qdrant.py"

setup-deps: ## Install Python and Node dependencies
	@command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required but not installed."; exit 1; }
	@command -v node >/dev/null 2>&1 || { echo "Node.js is required but not installed."; exit 1; }
	@command -v docker >/dev/null 2>&1 || { echo "Docker is required but not installed."; exit 1; }
	cd api && pip install -r requirements.txt
	cd frontend && npm ci --legacy-peer-deps

setup-hooks: ## Install pre-commit hooks
	@command -v pre-commit >/dev/null 2>&1 || pip install pre-commit
	pre-commit install
	@echo "Pre-commit hooks installed"

verify: ## Verify development environment setup
	python scripts/verify_setup.py

sdk: ## Generate TypeScript SDK from OpenAPI spec
	python scripts/generate_sdk.py
