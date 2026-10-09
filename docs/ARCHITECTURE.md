# Architecture

The principle behind this repo: **the instruction stack, persistent context and feedback loops matter more than the tools.** n8n, Postgres and Sygnal are interchangeable; what compounds is how the pipeline is organized.

## Five-stage pipeline

```
INGEST       ENRICH        SCORE            ROUTE          ACT
raw_events → firms/tech → Sygnal verdict → bucket + SLA → n8n notify / sequence
  (A)          (B)          (Sygnal)         (A)            (A/B/C)
```

Pipeline A implements ingest → route → act and leaves clean seams for B (enrichment, real firmographic data) and C (LLM personalization, feedback). **Scoring is not ours to own:** Sygnal evaluates each signal against an ICP blueprint and returns a 0–10 `score`, `icp_score`, `score_breakdown`, and `entities`. Pipeline A consumes that verdict rather than duplicating it.

## Instruction stack

| Layer | Where it lives | Notes |
|---|---|---|
| 1. Intent scoring | Sygnal (upstream) | `score` / `icp_score`; do not recompute |
| 2. Verdict mapping | `pipeline_core/verdict.py` | `priority = score × 10`, competitive + ICP-match flags |
| 3. Sequence / routing logic | `pipeline_core/routing.py`, n8n workflow | bucket → action/owner/SLA/play |
| 4. Messaging framework | `fixtures/` + n8n (Pipeline C) | value props / openers indexed by bucket |

## Request lifecycle

1. **Receive** — POST `/webhooks/sygnal`, read raw body.
2. **Verify** — HMAC-SHA256 over the raw bytes vs. the configured secret (constant-time). Reject `401` on mismatch when a secret is set.
3. **Dedupe** — insert the event into `raw_events` keyed by `event_id` (`ON CONFLICT DO NOTHING`). Already-seen → `200 duplicate`, no reprocessing.
4. **ACK** — return `202 accepted` immediately; the rest runs in a background task.
5. **Normalize** — tolerant mapping of the Sygnal envelope (`{event, signal}`) to `NormalizedSignal` (alias keys, envelope unwrapping, timestamp coercion).
6. **Route from the verdict** — `priority = round(score × 10)`; `play = competitive` when `entities.competitors` is non-empty; `suggested_action` is carried through. Map priority → bucket (`hot`/`warm`/`monitor`/`nurture`/`archive`) with owner, SLA and notify flag. **No local re-scoring.**
7. **Persist** — upsert into `signals`; append `signal.received|routed` to `pipeline_events`.
8. **Forward** — POST to n8n with exponential-backoff retries; on final failure write to `dead_letters` and log `forward.failed`.

## Why these choices

| Decision | Rationale |
|---|---|
| Verify at the edge, not in n8n | Downstream stages can trust the payload; failures are cheap and early |
| Idempotency via DB PK | At-least-once delivery is normal; processing twice must be impossible |
| 202 + async work | Webhook senders time out; slow enrichment must not block the ack |
| Append-only `pipeline_events` | Replay events to rebuild state or backtest a new routing model |
| Dead-letter queue | Silent failures are the #1 cause of "leads fell through the cracks" |
| In-memory fallback store | Repo runs in one command with zero infra; Postgres is opt-in |
| Consume Sygnal's verdict | Don't rebuild a core competency; map `score` → `priority` and route |

## Extension seams

**Pipeline B (enrichment):**
- Add `pipeline_core/enrichment.py` with a waterfall (`provider.enrich()` → accept at confidence ≥ 0.85, flag ≥ 0.50, reject below).
- Use Sygnal's `entities` (`company_domain`, `competitors`, `tools`) as waterfall inputs rather than re-discovering them.
- Persist provider data in a `company_enrichment` table; cache 30–90 days.

**Pipeline C (personalization + feedback):**
- New service consumes `signals` rows and drafts openers with a free LLM tier (Gemini/Groq), seeded by `suggested_action` and the competitive `play`.
- Human review queue (n8n approval or a tiny Next.js page).
- Log reply outcomes back as `pipeline_events` (`email.replied`, `meeting.booked`) and tune the routing thresholds from real conversion data.

## Observability checklist (per the discipline)

| Metric | Alert threshold |
|---|---|
| Receiver 5xx rate | any sustained errors |
| Signature rejections | spike = secret drift or attack |
| Duplicate rate | spike = sender retry storm |
| `forward.failed` in `pipeline_events` | any |
| Dead letters | > 0 for > 1h |
| Enrichment hit rate (B) | < 60% |
| Email bounce rate (C) | > 5% |
