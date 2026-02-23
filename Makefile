.PHONY: help setup install dev start stop restart logs clean test test-cov migrate db-up db-down db-logs format lint docs

# Default target
.DEFAULT_GOAL := help

# Variables
PYTHON := poetry run python
UVICORN := poetry run uvicorn
ALEMBIC := poetry run alembic
PYTEST := poetry run pytest
BLACK := poetry run black
RUFF := poetry run ruff
MYPY := poetry run mypy

help: ## Show this help message
	@echo "Cadence v2.0 - Development Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Setup and Installation
setup: ## Run complete development setup
	@echo "Running development setup..."
	@chmod +x scripts/setup-dev.sh
	@./scripts/setup-dev.sh

install: ## Install Python dependencies
	@echo "Installing dependencies..."
	@poetry install

install-dev: ## Install development dependencies
	@echo "Installing development dependencies..."
	@poetry install --with dev

# Development Server
dev: ## Start development server with auto-reload
	@echo "Starting Cadence development server..."
	$(UVICORN) cadence.main:app --reload --host 0.0.0.0 --port 8000

start: ## Start production server
	@echo "Starting Cadence production server..."
	$(UVICORN) cadence.main:app --host 0.0.0.0 --port 8000 --workers 4

# Database Management
db-up: ## Start all databases (local)
	@chmod +x scripts/docker.sh
	@./scripts/docker.sh start

db-down: ## Stop all databases
	@chmod +x scripts/docker.sh
	@./scripts/docker.sh stop

db-restart: ## Restart all databases
	@chmod +x scripts/docker.sh
	@./scripts/docker.sh restart

db-logs: ## Show database logs
	@chmod +x scripts/docker.sh
	@./scripts/docker.sh logs

db-clean: ## Stop databases and remove volumes (WARNING: deletes all data)
	@chmod +x scripts/docker.sh
	@./scripts/docker.sh reset

db-reset-full: ## Full dev reset: wipe Docker volumes → start → migrate → bootstrap
	@echo "=== Full database reset ==="
	@chmod +x scripts/docker.sh
	@./scripts/docker.sh reset
	@./scripts/docker.sh start
	@echo "Waiting for PostgreSQL to be ready..."
	@sleep 5
	$(ALEMBIC) upgrade head
	@echo ""
	@echo "Run 'make bootstrap' to create the initial admin user."

db-status: ## Show database status
	@chmod +x scripts/docker.sh
	@./scripts/docker.sh status

# Database Migrations
migrate: ## Run database migrations (upgrade to latest)
	@echo "Running migrations..."
	$(ALEMBIC) upgrade head

migrate-down: ## Rollback last migration
	@echo "Rolling back last migration..."
	$(ALEMBIC) downgrade -1

migrate-create: ## Create new migration (use: make migrate-create MSG="description")
	@echo "Creating new migration..."
	@if [ -z "$(MSG)" ]; then \
		echo "Error: Please provide a message with MSG='your message'"; \
		exit 1; \
	fi
	$(ALEMBIC) revision --autogenerate -m "$(MSG)"

migrate-history: ## Show migration history
	$(ALEMBIC) history

migrate-current: ## Show current migration version
	$(ALEMBIC) current

# Testing
test: ## Run all tests
	@echo "Running tests..."
	$(PYTEST) -v

test-cov: ## Run tests with coverage report
	@echo "Running tests with coverage..."
	$(PYTEST) --cov=cadence --cov-report=html --cov-report=term

test-fast: ## Run tests (skip slow tests)
	@echo "Running fast tests..."
	$(PYTEST) -v -m "not slow"

test-watch: ## Run tests in watch mode
	@echo "Running tests in watch mode..."
	$(PYTEST) -f -v

# Code Quality
format: ## Format code with Black and Ruff
	@echo "Formatting code..."
	$(BLACK) .
	$(RUFF) check --fix .

lint: ## Lint code with Ruff
	@echo "Linting code..."
	$(RUFF) check .

type-check: ## Type check with MyPy
	@echo "Type checking..."
	$(MYPY) src/

check: format lint type-check ## Run all code quality checks

# Documentation
docs: ## Generate API documentation
	@echo "Generating documentation..."
	@echo "API docs available at: http://localhost:8000/docs"

docs-build: ## Build Sphinx documentation
	@echo "Building documentation..."
	@cd docs && make html

# Cleaning
clean: ## Clean temporary files and caches
	@echo "Cleaning temporary files..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@rm -rf .coverage htmlcov/
	@echo "Clean complete."

clean-logs: ## Clean log files
	@echo "Cleaning logs..."
	@rm -rf logs/*
	@echo "Logs cleaned."

# Docker
docker-build: ## Build Docker image
	@echo "Building Docker image..."
	docker build -t cadence:latest .

docker-run: ## Run Docker container
	@echo "Running Docker container..."
	docker run -p 8000:8000 --env-file .env cadence:latest

# Utilities
shell: ## Open Python shell with app context
	@echo "Opening Python shell..."
	$(PYTHON) -i -c "from cadence.main import app; print('Cadence app loaded. Use: app')"

psql: ## Connect to PostgreSQL
	@cd devops/local && docker exec -it cadence-postgres-local psql -U cadence -d cadence_dev

mongo: ## Connect to MongoDB
	@cd devops/local && docker exec -it cadence-mongo-local mongosh -u cadence -p cadence_dev_password

redis: ## Connect to Redis CLI
	@cd devops/local && docker exec -it cadence-redis-local redis-cli -a cadence_dev_password

# Plugin Management
plugins-list: ## List installed plugins
	@echo "Listing plugins..."
	$(PYTHON) -c "from cadence_sdk import PluginRegistry; print('\\n'.join([p.name for p in PluginRegistry.instance().list_registered_plugins()]))"

plugins-validate: ## Validate all plugins
	@echo "Validating plugins..."
	$(PYTHON) scripts/validate_plugins.py

# Admin
bootstrap: ## Bootstrap default admin org and user (prints API token)
	@echo "Bootstrapping Cadence..."
	$(PYTHON) scripts/bootstrap.py

openapi: ## Export OpenAPI schema to scripts/openapi_schema.json
	@echo "Generating OpenAPI schema..."
	$(PYTHON) scripts/generate_openapi.py

# Production
prod-up: ## Start production databases
	@echo "Starting production databases..."
	@cd devops/production && docker compose -f database.yaml up -d

prod-down: ## Stop production databases
	@echo "Stopping production databases..."
	@cd devops/production && docker compose -f database.yaml down

prod-logs: ## Show production database logs
	@cd devops/production && docker compose -f database.yaml logs -f

prod-backup: ## Run production backups manually
	@echo "Running production backups..."
	@cd devops/production && docker exec cadence-postgres-backup-prod /backup.sh
	@cd devops/production && docker exec cadence-mongo-backup-prod /backup.sh

# Monitoring
health: ## Check system health
	@echo "Checking system health..."
	@curl -s http://localhost:8000/health | python -m json.tool || echo "API not running"

stats: ## Show pool statistics
	@echo "Fetching pool statistics..."
	@curl -s http://localhost:8000/api/admin/pool/stats | python -m json.tool || echo "API not running"

# Version
version: ## Show version information
	@echo "Cadence v2.0"
	@echo "Python: $$(python3 --version)"
	@echo "Poetry: $$(poetry --version)"
	@echo "Docker: $$(docker --version)"

# Quick commands
up: db-up migrate dev ## Quick start: databases + migrations + dev server
down: db-down ## Quick stop: stop databases
restart: down up ## Quick restart: stop and start everything
logs: db-logs ## Quick logs: show database logs
