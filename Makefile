.PHONY: help setup install build up down restart logs clean test lint format

# Colors for output
CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(CYAN)Housler v2.0 - Available commands:$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""

# ========================================
# Setup & Installation
# ========================================

setup: ## Initial setup (create .env from template)
	@echo "$(CYAN)Setting up Housler...$(NC)"
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(GREEN)✓ Created .env from template$(NC)"; \
		echo "$(YELLOW)⚠ Please edit .env and set your configuration$(NC)"; \
	else \
		echo "$(YELLOW).env already exists, skipping...$(NC)"; \
	fi

install: ## Install Python dependencies locally
	@echo "$(CYAN)Installing dependencies...$(NC)"
	pip install -r requirements.txt
	playwright install chromium
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

install-dev: ## Install development dependencies
	@echo "$(CYAN)Installing dev dependencies...$(NC)"
	pip install -r requirements.txt
	pip install pytest black flake8 mypy
	playwright install chromium
	@echo "$(GREEN)✓ Dev dependencies installed$(NC)"

# ========================================
# Docker Operations
# ========================================

build: ## Build Docker images
	@echo "$(CYAN)Building Docker images...$(NC)"
	docker-compose build --no-cache
	@echo "$(GREEN)✓ Build complete$(NC)"

up: ## Start all services
	@echo "$(CYAN)Starting Housler...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "$(GREEN)✓ App: http://localhost:5000$(NC)"
	@echo "$(GREEN)✓ Health: http://localhost:5000/health$(NC)"

up-monitoring: ## Start with monitoring (Prometheus + Grafana)
	@echo "$(CYAN)Starting Housler with monitoring...$(NC)"
	docker-compose --profile monitoring up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "$(GREEN)✓ App: http://localhost:5000$(NC)"
	@echo "$(GREEN)✓ Prometheus: http://localhost:9090$(NC)"
	@echo "$(GREEN)✓ Grafana: http://localhost:3000 (admin/admin)$(NC)"

up-production: ## Start with production profile (Nginx + SSL)
	@echo "$(CYAN)Starting Housler in production mode...$(NC)"
	docker-compose --profile production up -d
	@echo "$(GREEN)✓ Production services started$(NC)"

down: ## Stop all services
	@echo "$(CYAN)Stopping Housler...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Services stopped$(NC)"

down-volumes: ## Stop and remove volumes (WARNING: deletes data!)
	@echo "$(RED)⚠ This will delete all data including Redis cache$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo ""; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down -v; \
		echo "$(GREEN)✓ Services and volumes removed$(NC)"; \
	else \
		echo "$(YELLOW)Cancelled$(NC)"; \
	fi

restart: ## Restart all services
	@echo "$(CYAN)Restarting Housler...$(NC)"
	docker-compose restart
	@echo "$(GREEN)✓ Services restarted$(NC)"

restart-app: ## Restart only app service (fast)
	@echo "$(CYAN)Restarting app...$(NC)"
	docker-compose restart app
	@echo "$(GREEN)✓ App restarted$(NC)"

# ========================================
# Logs & Monitoring
# ========================================

logs: ## Show logs from all services
	docker-compose logs -f

logs-app: ## Show logs from app only
	docker-compose logs -f app

logs-redis: ## Show logs from Redis
	docker-compose logs -f redis

health: ## Check application health
	@echo "$(CYAN)Checking health...$(NC)"
	@curl -s http://localhost:5000/health | jq || echo "$(RED)Service not responding$(NC)"

metrics: ## Show Prometheus metrics
	@echo "$(CYAN)Fetching metrics...$(NC)"
	@curl -s http://localhost:5000/metrics

stats: ## Show cache statistics
	@echo "$(CYAN)Cache statistics:$(NC)"
	@curl -s http://localhost:5000/api/cache/stats | jq

# ========================================
# Development
# ========================================

dev: ## Run in development mode (local)
	@echo "$(CYAN)Starting development server...$(NC)"
	FLASK_ENV=development FLASK_DEBUG=true python app_new.py

shell: ## Open Python shell with app context
	@echo "$(CYAN)Opening shell...$(NC)"
	docker-compose exec app python

bash: ## Open bash in app container
	@echo "$(CYAN)Opening bash...$(NC)"
	docker-compose exec app /bin/bash

redis-cli: ## Open Redis CLI
	@echo "$(CYAN)Opening Redis CLI...$(NC)"
	docker-compose exec redis redis-cli

# ========================================
# Testing & Quality
# ========================================

test: ## Run tests
	@echo "$(CYAN)Running tests...$(NC)"
	pytest tests/ -v

test-integration: ## Run integration tests
	@echo "$(CYAN)Running integration tests...$(NC)"
	pytest tests/integration/ -v

lint: ## Run linter (flake8)
	@echo "$(CYAN)Running linter...$(NC)"
	flake8 src/ app_new.py --max-line-length=120 --exclude=venv,__pycache__

format: ## Format code with black
	@echo "$(CYAN)Formatting code...$(NC)"
	black src/ app_new.py --line-length=100

type-check: ## Run type checker (mypy)
	@echo "$(CYAN)Running type checker...$(NC)"
	mypy src/ app_new.py --ignore-missing-imports

validate: lint format type-check ## Run all quality checks
	@echo "$(GREEN)✓ All checks passed$(NC)"

# ========================================
# Maintenance
# ========================================

backup-redis: ## Backup Redis data
	@echo "$(CYAN)Creating Redis backup...$(NC)"
	@mkdir -p backups
	docker exec housler-redis redis-cli BGSAVE
	@sleep 2
	docker cp housler-redis:/data/dump.rdb backups/dump_$(shell date +%Y%m%d_%H%M%S).rdb
	@echo "$(GREEN)✓ Backup created in backups/$(NC)"

restore-redis: ## Restore Redis from latest backup
	@echo "$(CYAN)Restoring Redis from latest backup...$(NC)"
	@LATEST=$$(ls -t backups/dump_*.rdb | head -1); \
	if [ -z "$$LATEST" ]; then \
		echo "$(RED)No backups found$(NC)"; \
		exit 1; \
	fi; \
	echo "Restoring from: $$LATEST"; \
	docker cp "$$LATEST" housler-redis:/data/dump.rdb; \
	docker-compose restart redis; \
	echo "$(GREEN)✓ Redis restored$(NC)"

clear-cache: ## Clear Redis cache
	@echo "$(CYAN)Clearing cache...$(NC)"
	@curl -X POST http://localhost:5000/api/cache/clear \
		-H "Content-Type: application/json" \
		-d '{"pattern": "*"}' | jq
	@echo "$(GREEN)✓ Cache cleared$(NC)"

clean: ## Clean temporary files and caches
	@echo "$(CYAN)Cleaning temporary files...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(NC)"

clean-docker: ## Remove all Docker containers and images (WARNING!)
	@echo "$(RED)⚠ This will remove all Housler Docker containers and images$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo ""; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down --rmi all; \
		echo "$(GREEN)✓ Docker artifacts removed$(NC)"; \
	else \
		echo "$(YELLOW)Cancelled$(NC)"; \
	fi

# ========================================
# Production
# ========================================

deploy: ## Deploy to production
	@echo "$(CYAN)Deploying to production...$(NC)"
	git pull origin main
	docker-compose build --no-cache
	docker-compose up -d --force-recreate --no-deps app
	@echo "$(GREEN)✓ Deployed$(NC)"

ssl-renew: ## Renew SSL certificates (Let's Encrypt)
	@echo "$(CYAN)Renewing SSL certificates...$(NC)"
	certbot renew --quiet
	@echo "$(GREEN)✓ Certificates renewed$(NC)"

# ========================================
# Utilities
# ========================================

ps: ## Show running containers
	docker-compose ps

top: ## Show container resource usage
	docker stats

version: ## Show application version
	@echo "$(CYAN)Housler v2.0.0$(NC)"

update: ## Update dependencies
	@echo "$(CYAN)Updating dependencies...$(NC)"
	pip install --upgrade -r requirements.txt
	@echo "$(GREEN)✓ Dependencies updated$(NC)"
