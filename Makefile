.PHONY: run tunnel serve install clean test

# Default target
.DEFAULT_GOAL := serve

# Port for local development
PORT ?= 8000

# Tuna token from environment or .env
TUNA_TOKEN ?= $(shell grep TUNA_TOKEN .env 2>/dev/null | cut -d'=' -f2)

# Install dependencies
install:
	uv sync

# Run FastAPI server
run:
	uv run uvicorn app.main:app --reload --port $(PORT)

# Start Tuna tunnel
tunnel:
	@if [ -z "$(TUNA_TOKEN)" ]; then \
		echo "Error: TUNA_TOKEN not set. Create .env file with TUNA_TOKEN=your_token"; \
		exit 1; \
	fi
	TUNA_TOKEN=$(TUNA_TOKEN) tuna http $(PORT) --subdomain=telegram-generator

# Run both server and tunnel (for development)
serve:
	@echo "Starting server and tunnel..."
	@make run &
	@sleep 2
	@make tunnel

# Run tests
test:
	uv run pytest tests/ -v

# Clean generated files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .uv/ dist/ build/ 2>/dev/null || true

# Format code
format:
	uv run ruff format .

# Lint code
lint:
	uv run ruff check .
