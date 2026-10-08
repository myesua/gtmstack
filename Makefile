.PHONY: install test lint run up down logs psql send-test tunnel import-workflow clean

install:
	uv sync --extra dev

test:
	uv run pytest

lint:
	uv run ruff check .

run:
	uv run uvicorn services.webhook_receiver.app:app --reload --port 8080

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

psql:
	docker compose exec postgres psql -U gtm -d gtm

send-test:
	uv run python scripts/send_test_signal.py

# Expose your local receiver on a public HTTPS URL for Sygnal webhooks.
# Prints a https://<random>.trycloudflare.com URL - use it as the webhook target.
tunnel:
	cloudflared tunnel --url http://localhost:8080

# Import the Pipeline A workflow into the running n8n container.
import-workflow:
	docker compose exec n8n n8n import:workflow --input=/workflows/pipeline_a_signal_router.json

clean:
	rm -rf .pytest_cache .ruff_cache
