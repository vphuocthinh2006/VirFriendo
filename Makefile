.PHONY: help setup install train test clean dev down lint

.DEFAULT_GOAL := help

help:
	@echo "=== AI Anime Companion — Development Commands ==="
	@echo ""
	@echo "  setup        - Install all dependencies for local development"
	@echo "  dev          - Start all services with Docker Compose"
	@echo "  down         - Stop all services"
	@echo "  train        - Run the dataset generation pipeline"
	@echo "  test         - Run all tests (pytest)"
	@echo "  lint         - Run linter (ruff)"
	@echo "  clean        - Remove temp files and caches"
	@echo "  run-core     - Start the core service locally with uvicorn"

setup:
	@echo "Installing dependencies..."
	pip install -r requirements.txt
	@if [ -f ml/requirements-training.txt ]; then echo "Installing ML Training dependencies..."; pip install -r ml/requirements-training.txt; fi

dev:
	docker compose up --build

down:
	docker compose down

train:
	@echo "Running dataset generation pipeline..."
	python ml/pipelines/generate_dataset.py

test:
	@echo "Running tests..."
	pytest services/ -v

lint:
	ruff check services/ shared/ ml/

clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache
	rm -rf .ruff_cache

run-core:
	@echo "Starting Core Service..."
	uvicorn services.core.main:app --reload --host 0.0.0.0 --port 8000
