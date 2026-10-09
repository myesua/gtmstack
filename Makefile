.PHONY: install test lint run up down logs psql send-test tunnel import-workflow seo seo-serve clean

install:
	uv sync --extra dev

test:
	uv run pytest

lint:
	uv run ruff check .

run:
	@ENV_FLAG=""; [ -f .env ] && ENV_FLAG="--env-file .env"; \
	uv run uvicorn services.webhook_receiver.app:app --reload --port 8080 $$ENV_FLAG

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

# Build the static competitor/alternative SEO site into seo/site/.
seo:
	uv run python seo/generate.py

# Preview the generated SEO site locally at http://localhost:8090
seo-serve: seo
	uv run python -m http.server 8090 --directory seo/site

clean:
	rm -rf .pytest_cache .ruff_cache
