PYTHON ?= python3.11
VENV ?= .venv
BIN := $(VENV)/bin

.DEFAULT_GOAL := help
.PHONY: help setup lint typecheck test test-integration check format coverage clean

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

setup: ## Create the virtualenv and install dev dependencies
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e ".[dev]"
	$(BIN)/pre-commit install

lint: ## Run ruff lint and format checks
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

typecheck: ## Run mypy in strict mode
	$(BIN)/mypy

test: ## Run unit tests (no network, no services)
	$(BIN)/pytest -m "not integration"

test-integration: ## Run integration tests (needs the docker compose stack)
	$(BIN)/pytest -m integration

check: lint typecheck test ## Lint, typecheck and test; must pass before every commit

format: ## Apply ruff fixes and formatting
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

coverage: ## Run unit tests with a coverage report
	$(BIN)/pytest -m "not integration" --cov=libs --cov=functions --cov-report=term-missing

clean: ## Remove caches and build artifacts
	rm -rf .mypy_cache .ruff_cache .pytest_cache .coverage htmlcov build dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
