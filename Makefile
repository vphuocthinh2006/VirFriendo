.PHONY: help setup dev down run-core clean

.DEFAULT_GOAL := help

help:
	@echo "VirFriendo — common commands"
	@echo "  setup    pip install -r requirements.txt (+ optional ml/requirements-training.txt)"
	@echo "  dev      docker compose up --build"
	@echo "  down     docker compose down"
	@echo "  run-core uvicorn API on :8000"
	@echo "  clean    remove __pycache__ / .pyc"

setup:
	pip install -r requirements.txt
	@if [ -f ml/requirements-training.txt ]; then pip install -r ml/requirements-training.txt; fi

dev:
	docker compose up --build

down:
	docker compose down

run-core:
	uvicorn services.core.main:app --reload --host 0.0.0.0 --port 8000

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
