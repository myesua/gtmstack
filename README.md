# GTM Engineering Pipelines

A code-first GTM engineering portfolio: real, version-controlled signal → route → act pipelines built on [Sygnal](https://trysygnal.com) buyer-intent signals with a 100% free tool stack.

**Status:** Pipeline A (Signal Router) is runnable end-to-end against Postgres; the competitor/alternative SEO generator builds a static site.

## Architecture (Pipeline A)

```
  Sygnal webhook                          Sygnal owns scoring.
        │  HMAC-signed POST               We consume its verdict:
        ▼                                 score, icp_score, entities,
┌──────────────────────────────┐          competitors, suggested_action.
│  webhook_receiver (FastAPI)  │   verify signature
│  services/webhook_receiver   │   idempotent insert into raw_events
│                              │   ACK 202, process async
└───────────────┬──────────────┘
                │ normalize → route (pipeline_core)
                ▼
┌──────────────────────────────┐
│  n8n orchestration workflow  │   branch on priority, notify, respond
│  n8n/workflows/…router.json  │
└───────────────┬──────────────┘
                ▼
     Slack/Discord alert · Postgres signal state · event log
```

Design choices worth talking about in interviews:

- **Consume the verdict, don't recompute it.** Sygnal already scores intent against an ICP blueprint; this pipeline maps `score` → `priority = score × 10` and routes (`pipeline_core/verdict.py`). Only the routing logic is ours.
- **Verify at the edge.** HMAC-SHA256 on the raw body, constant-time compare (`pipeline_core/signature.py`).
- **Idempotency.** `raw_events.event_id` is the PK; duplicate deliveries are acked, not reprocessed.
- **ACK fast, work async.** Receiver returns `202` and processes in a background task.
- **Event sourcing.** `pipeline_events` is an append-only audit log of every stage.
- **Graceful degradation.** n8n forward retries with exponential backoff, then dead-letters.
- **Enriched routing.** `entities.competitors` triggers a `competitive` play; `suggested_action` is carried through to the alert.

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
make up                   # postgres:5433, n8n:http://localhost:5678
make import-workflow      # loads the Pipeline A workflow into n8n
```

> The container Postgres host port is `${POSTGRES_HOST_PORT}` (default `5432`); set `5433` in `.env` if you already run Postgres locally.

Expose your machine so Sygnal can reach it (no paid hosting):

```bash
make tunnel               # prints https://<random>.trycloudflare.com
```

Point a Sygnal webhook at `https://<random>.trycloudflare.com/webhooks/sygnal`, set the same secret in `.env`, and the flow runs end-to-end. Full setup: [docs/SETUP.md](docs/SETUP.md). Design notes: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Portfolio write-up: [docs/CASE_STUDY.md](docs/CASE_STUDY.md).

## SEO generator (acquisition asset)

Turns structured competitor data into static, answer-first comparison pages — the BOFU keywords that convert for a challenger brand:

```bash
make seo         # -> seo/site/index.html, alternatives/*.html, vs/*.html, sitemap.xml, llms.txt
make seo-serve   # preview at http://localhost:8090
```

Content is generated from `seo/data.json` (never free-written), so every page carries unique facts. Pricing/features in that file are **estimates — verify before publishing**.

## Layout

```
pipeline_core/            shared domain logic (framework-free, unit-tested)
  signature.py            HMAC-SHA256 webhook verification
  normalize.py            Sygnal webhook envelope -> NormalizedSignal
  verdict.py              consume Sygnal's score (priority, competitive, ICP match)
  routing.py              bucket + owner + SLA + play
  db.py                   Postgres store + in-memory fallback
services/webhook_receiver/ FastAPI edge service
n8n/workflows/            version-controlled workflow JSON
db/migrations/            append-only event store schema
seo/                      competitor/alternative static-site generator
tests/                    pytest for signature, normalize, verdict, routing, seo
fixtures/, scripts/       sample payload + signed test sender
```

## Roadmap

| Pipeline | Scope | Status |
|---|---|---|
| **A — Signal Router** | webhook → verify → normalize → route → n8n notify | ✅ runnable |
| **B — Enrichment + scoring** | waterfall enrichment (free providers), real firmographic fit, dashboard | ⏭️ next |
| **C — Personalization + feedback loop** | LLM opener drafts, human review, reply outcomes re-weight scoring | planned |
| **SEO — Competitor/alternative pages** | programmatic pages from structured data, free static hosting | ✅ builds |

## Tool stack (all free / free tier)

n8n (self-hosted) · Cloudflare Tunnel · Supabase/Postgres · HubSpot free CRM · Metabase (self-hosted) · GitHub Actions · Gemini/Groq free LLM tiers · Slack/Discord webhooks · Sygnal.
