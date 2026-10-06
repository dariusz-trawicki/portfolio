.PHONY: help install run test lint format check voice up up-app up-all down logs build

PIPER_VOICE ?= en_US-lessac-medium
PIPER_URL   ?= https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium

help:          ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-10s %s\n", $$1, $$2}'

install:       ## Install dependencies (incl. dev tools)
	uv sync

run:           ## Run the teacher natively with config.yaml
	uv run english-teacher --config config.yaml

test:          ## Run unit tests
	uv run pytest -q

lint:          ## Lint with ruff
	uv run ruff check .
	uv run ruff format --check .

format:        ## Auto-format with ruff
	uv run ruff check --fix .
	uv run ruff format .

check: lint test  ## Lint + tests (same as CI)

voice:         ## Download the Piper voice (for TTS backend 'piper' outside Docker)
	mkdir -p models
	curl -fsSL -o models/$(PIPER_VOICE).onnx $(PIPER_URL)/$(PIPER_VOICE).onnx
	curl -fsSL -o models/$(PIPER_VOICE).onnx.json $(PIPER_URL)/$(PIPER_VOICE).onnx.json
	uv sync --extra piper

up:            ## Start Prometheus + Grafana (app runs natively)
	docker compose up -d

up-app:        ## Start monitoring + teacher container (Ollama on host)
	docker compose --profile app up -d --build

up-all:        ## Start everything incl. Ollama in Docker (Linux)
	docker compose --profile app --profile ollama up -d --build

down:          ## Stop all containers
	docker compose --profile app --profile ollama down

logs:          ## Follow teacher container logs
	docker compose logs -f teacher

build:         ## Build the Docker image
	docker build -t local-english-teacher:latest .
