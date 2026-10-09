# Case Study — Pipeline A: Sygnal Signal Router

> A hiring-manager-facing write-up. Part 1 (design + engineering evidence) is
> accurate as built. Part 2 (live results) is a template — fill in the measured
> numbers after running the pipeline against real Sygnal webhooks. Do **not**
> publish invented metrics; the whole point of the discipline is measurable
> feedback loops.

## Context

**Domain:** GTM engineering — the systems that turn buying signals into pipeline.

**Signal source:** [Sygnal](https://trysygnal.com) surfaces public posts where
someone describes the exact pain a product solves, scored 0–10 for buyer intent.
The value is the *48-hour window*: most founders find these posts 5–7 days late,
after the conversation has moved on.

**Problem:** a high-intent signal is worthless if it sits in a dashboard. It has
to reach the right owner, with context, inside the window — reliably, without
duplicates, and without silently dropping events.

**Constraint:** a 100% free tool stack (no paid hosting, enrichment, or
platforms). This is deliberate: the architecture, not the budget, is what
should be judged.

## What was built

A production-shaped **ingest → normalize → route → act** pipeline. Scoring is
Sygnal's job — the pipeline consumes its verdict:

```
Sygnal webhook ──▶ FastAPI receiver ──▶ n8n orchestration ──▶ Slack + Postgres
 (HMAC-signed)      verify · dedupe        branch on priority      audit log
                    ACK 202 · async       (score → priority)

                 Sygnal returns: score, icp_score, entities.competitors, suggested_action
```

- `services/webhook_receiver/` — FastAPI edge: HMAC-SHA256 verification on the
  raw body (constant-time), idempotent ingest, fast ACK, async processing.
- `pipeline_core/` — framework-free domain logic: signature, normalize, verdict,
  route, store. Pure functions, unit-tested.
- `n8n/workflows/` — version-controlled orchestration; routes and notifies.
- `db/migrations/` — append-only event store (`raw_events`, `pipeline_events`),
  current signal state (`signals`), and a `dead_letters` queue.
- `seo/` — competitor/alternative static-site generator (acquisition asset).

## Engineering decisions worth defending

| Decision | Why it matters |
|---|---|
| **Verify at the edge, not in n8n** | Downstream stages trust the payload; bad signatures fail early and cheaply (cheap before expensive). |
| **Idempotency via the `raw_events` PK** | At-least-once delivery is normal. Reprocessing a duplicate must be impossible, not unlikely. |
| **ACK `202` + process async** | Senders time out; slow downstream work must never block the acknowledgement. |
| **Append-only `pipeline_events`** | Event sourcing — replay history to rebuild state or backtest a new routing model. |
| **Dead-letter queue + retries** | Silent failures are the #1 cause of "leads fell through the cracks." Every dropped forward is recorded and alertable. |
| **In-memory fallback store** | The whole pipeline runs in one command with zero infra; Postgres is opt-in, not required to demo. |
| **Consume the verdict, don't recompute it** | Sygnal already scores intent against an ICP blueprint; the pipeline maps `score` → `priority` and routes. Rebuilding scoring would just diverge from the source of truth. |
| **Enriched routing** | `entities.competitors` triggers a `competitive` play and `suggested_action` rides along on the alert. |

Design principle throughout: **the instruction stack, persistent context, and
feedback loops matter more than the tools.** n8n and Postgres are swappable; the
routing logic, entity handling, and event history are the durable asset.

The `instruction stack` is made explicit rather than scattered:

| Layer | Where |
|---|---|
| 1. Intent scoring | Sygnal (upstream) — `score` / `icp_score`; not recomputed here |
| 2. Verdict mapping | `pipeline_core/verdict.py` — `priority = score × 10`, competitive + ICP flags |
| 3. Sequence logic | `pipeline_core/routing.py` — bucket → owner → SLA → play |
| 4. Messaging framework | `suggested_action` carried on the signal (Pipeline C drafts from it) |

## Verified engineering evidence

These are real, reproducible checks (run `make test` and `make send-test`):

- `18` unit tests pass across signature, normalize, verdict, routing, and SEO.
- `ruff` lint clean.
- Signed webhook → `202 accepted`; replay → `200 duplicate` (idempotency);
  unsigned → `401`; tampered signature → `401` (constant-time HMAC).
- Sample Sygnal signal (`score 9`, `icp 8`, competitor `LegacyTool`) → `priority 90`
  → routed `hot` with `play: competitive`, persisted to `signals` and served back by
  `/signals/recent` — deterministic and asserted in tests.
- SEO generator produces 15 comparison pages + `sitemap.xml` / `robots.txt` /
  `llms.txt`, with valid JSON-LD and no broken internal links (asserted in tests).

## Results (fill in after running live)

> Run the pipeline against real Sygnal signals for 2–4 weeks, then replace the
> `TODO`s. Suggested source: query `signals` joined to reply outcomes logged as
> `pipeline_events`.

| Metric | Before (manual) | After (pipeline) | How measured |
|---|---|---|---|
| Median signal→owner time | TODO (hours/days) | TODO | `signal.received` → `forward.sent` timestamps |
| Signals processed / week | TODO | TODO | `count(distinct signal_id)` |
| Duplicate deliveries suppressed | — | TODO | `raw_events` conflict count |
| Signals lost / dropped | TODO | TODO | `dead_letters` count (target: 0) |
| Hot-signal reply rate | TODO | TODO | `signal.routed(bucket=hot)` → `email.replied` |

**Interpreting the numbers:** the interesting result is not raw throughput, it is
that a signal reaches an owner inside the 48-hour window with evidence attached,
and that the system provably never processes the same event twice or loses one.

## Build vs. n8n — why both

The role asks for n8n *and* real engineering. Neither alone is enough:

- **n8n** handles orchestration, branching, and human-visible tuning — what
  RevOps/GTM teams actually operate day to day.
- **Code** handles the parts that must be correct and testable: signature
  verification, idempotency, verdict mapping, retries, event history.

The workflow JSON is committed to Git and imported via `make import-workflow`,
so orchestration is versioned like everything else.

## What's next

- **Pipeline B** — enrichment waterfall (free providers), real firmographic data,
  a metrics dashboard. Seam: Sygnal's `entities` already provide
  `company_domain`, `competitors`, and `tools` as waterfall inputs.
- **Pipeline C** — LLM-drafted openers on a free tier (seeded by
  `suggested_action` and the `competitive` play), a human review queue, and a
  feedback loop that tunes routing thresholds from real reply/meeting outcomes.
- **SEO generator** — deepen the page set (use-case and integration pages,
  GEO-optimized for AI answers), then deploy to free static hosting.
