# GTM Engineering Pipelines

A code-first GTM engineering portfolio: real, version-controlled signal → enrich → score → route → act pipelines built on [Sygnal](https://trysygnal.com) buyer-intent signals with a 100% free tool stack.

**Status:** Pipeline A (Signal Router) is scaffolded and runnable.

## Architecture (Pipeline A)

```
  Sygnal webhook
        │  HMAC-signed POST
        ▼
┌──────────────────────────────┐   verify signature
│  webhook_receiver (FastAPI)  │   idempotent insert into raw_events
│  services/webhook_receiver   │   ACK 202, process async
└───────────────┬──────────────┘
                │ normalize → score → route (pipeline_core)
                ▼
┌──────────────────────────────┐
│  n8n orchestration workflow  │   branch on priority, notify, respond
│  n8n/workflows/…router.json  │
└───────────────┬──────────────┘
                ▼
     Slack/Discord alert · Postgres signal state · event log
```

Design choices worth talking about in interviews:

- **Verify at the edge.** HMAC-SHA256 on the raw body, constant-time compare (`pipeline_core/signature.py`).
- **Idempotency.** `raw_events.event_id` is the PK; duplicate deliveries are acked, not reprocessed.
- **ACK fast, work async.** Receiver returns `202` and processes in a background task.
- **Event sourcing.** `pipeline_events` is an append-only audit log of every stage.
- **Graceful degradation.** n8n forward retries with exponential backoff, then dead-letters.
- **Instruction stack.** ICP + scoring in `scoring.py`, sequence/routing in `routing.py`.

## Quickstart (free stack)

```bash
# 1. Deps
make install              # uv sync --extra dev

# 2. Config
cp .env.example .env      # set SYGNAL_WEBHOOK_SECRET; leave DATABASE_URL blank to start

# 3. Run the receiver (in-memory store until Postgres is up)
make run                  # http://localhost:8080

# 4. Fire a signed sample signal at it
make send-test            # -> 202 {"status":"accepted", ...}
```

Add Postgres + n8n (both free, Docker):

```bash
make up                   # postgres:5432, n8n:http://localhost:5678
make import-workflow      # loads the Pipeline A workflow into n8n
```

Expose your machine so Sygnal can reach it (no paid hosting):

```bash
make tunnel               # prints https://<random>.trycloudflare.com
```

Point a Sygnal webhook at `https://<random>.trycloudflare.com/webhooks/sygnal`, set the same secret in `.env`, and the flow runs end-to-end. Full setup: [docs/SETUP.md](docs/SETUP.md). Design notes: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Portfolio write-up: [docs/CASE_STUDY.md](docs/CASE_STUDY.md).

## Layout

```
pipeline_core/            shared domain logic (framework-free, unit-tested)
  signature.py            HMAC-SHA256 webhook verification
  normalize.py            tolerant payload -> NormalizedSignal
  scoring.py              fit / intent / priority model
  routing.py              bucket + owner + SLA
  db.py                   Postgres store + in-memory fallback
services/webhook_receiver/ FastAPI edge service
n8n/workflows/            version-controlled workflow JSON
db/migrations/            append-only event store schema
tests/                    pytest for signature, normalize, scoring, routing
fixtures/, scripts/       sample payload + signed test sender
```

## Roadmap

| Pipeline | Scope | Status |
|---|---|---|
| **A — Signal Router** | webhook → verify → normalize → score → route → n8n notify | ✅ scaffolded |
| **B — Enrichment + scoring** | waterfall enrichment (free providers), real firmographic fit, dashboard | ⏭️ next |
| **C — Personalization + feedback loop** | LLM opener drafts, human review, reply outcomes re-weight scoring | planned |

## Tool stack (all free / free tier)

n8n (self-hosted) · Cloudflare Tunnel · Supabase/Postgres · HubSpot free CRM · Metabase (self-hosted) · GitHub Actions · Gemini/Groq free LLM tiers · Slack/Discord webhooks · Sygnal.
