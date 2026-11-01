PYTHON ?= python3.11
VENV ?= .venv
BIN := $(VENV)/bin

.DEFAULT_GOAL := help
.PHONY: help setup lint typecheck test check

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

setup: ## Create the virtualenv and install dev dependencies
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e ".[dev]"

lint: ## Run ruff lint and format checks
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

typecheck: ## Run mypy in strict mode
	$(BIN)/mypy

test: ## Run unit tests (no network, no services)
	$(BIN)/pytest -m "not integration"

check: lint typecheck test ## Lint, typecheck and test; must pass before every commit
