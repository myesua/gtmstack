# Architecture

The principle behind this repo: **the instruction stack, persistent context and feedback loops matter more than the tools.** n8n, Postgres and Sygnal are interchangeable; what compounds is how the pipeline is organized.

## Five-stage pipeline

```
INGEST       ENRICH        SCORE         ROUTE          ACT
raw_events → firms/tech → fit + intent → bucket + SLA → n8n notify / sequence
  (A)          (B)          (A)           (A)            (A/B/C)
```

Pipeline A implements ingest → score → route → act and leaves clean seams for B (enrichment, real fit data) and C (LLM personalization, feedback).

## Instruction stack

| Layer | Where it lives | Notes |
|---|---|---|
| 1. ICP + scoring | `pipeline_core/scoring.py` | fit/intent weights and thresholds are constants, not scattered magic numbers |
| 2. Messaging framework | `fixtures/` + n8n (Pipeline C) | value props / openers indexed by bucket |
| 3. Personalization rules | Pipeline C | what to reference, what to avoid |
| 4. Sequence logic | `pipeline_core/routing.py`, n8n workflow | bucket → action/owner/SLA |

## Request lifecycle

1. **Receive** — POST `/webhooks/sygnal`, read raw body.
2. **Verify** — HMAC-SHA256 over the raw bytes vs. the configured secret (constant-time). Reject `401` on mismatch when a secret is set.
3. **Dedupe** — insert the event into `raw_events` keyed by `event_id` (`ON CONFLICT DO NOTHING`). Already-seen → `200 duplicate`, no reprocessing.
4. **ACK** — return `202 accepted` immediately; the rest runs in a background task.
5. **Normalize** — tolerant mapping to `NormalizedSignal` (alias keys, envelope unwrapping, timestamp coercion).
6. **Score** — `fit = firmographic*.40 + technographic*.35 + behavioral*.25`; `intent = first_party*.40 + third_party*.35 + trigger*.25` (sygnal score → third-party axis); `priority = fit*.55 + intent*.45`.
7. **Route** — priority → bucket (`hot`/`warm`/`monitor`/`nurture`/`archive`) with owner, SLA and notify flag.
8. **Persist** — upsert into `signals`; append `signal.received|scored|routed` to `pipeline_events`.
9. **Forward** — POST to n8n with exponential-backoff retries; on final failure write to `dead_letters` and log `forward.failed`.

## Why these choices

| Decision | Rationale |
|---|---|
| Verify at the edge, not in n8n | Downstream stages can trust the payload; failures are cheap and early |
| Idempotency via DB PK | At-least-once delivery is normal; processing twice must be impossible |
| 202 + async work | Webhook senders time out; slow enrichment must not block the ack |
| Append-only `pipeline_events` | Replay events to rebuild state or backtest a new scoring model |
| Dead-letter queue | Silent failures are the #1 cause of "leads fell through the cracks" |
| In-memory fallback store | Repo runs in one command with zero infra; Postgres is opt-in |
| Scoring in core, not n8n | Testable pure functions; n8n mirrors them for visual tuning |

## Extension seams

**Pipeline B (enrichment):**
- Add `pipeline_core/enrichment.py` with a waterfall (`provider.enrich()` → accept at confidence ≥ 0.85, flag ≥ 0.50, reject below).
- Feed results into `scoring.fit_score(firmographic=…, technographic=…, behavioral=…)` — the signature already accepts them.
- Persist provider data in a `company_enrichment` table; cache 30–90 days.

**Pipeline C (personalization + feedback):**
- New service consumes `signals` rows and drafts openers with a free LLM tier (Gemini/Groq).
- Human review queue (n8n approval or a tiny Next.js page).
- Log reply outcomes back as `pipeline_events` (`email.replied`, `meeting.booked`) and re-weight the scoring constants from real conversion data.

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
