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

A production-shaped **ingest → normalize → score → route → act** pipeline:

```
Sygnal webhook ──▶ FastAPI receiver ──▶ n8n orchestration ──▶ Slack + Postgres
 (HMAC-signed)      verify · dedupe        branch on priority      audit log
                    ACK 202 · async
```

- `services/webhook_receiver/` — FastAPI edge: HMAC-SHA256 verification on the
  raw body (constant-time), idempotent ingest, fast ACK, async processing.
- `pipeline_core/` — framework-free domain logic: signature, normalize, score,
  route, store. Pure functions, unit-tested.
- `n8n/workflows/` — version-controlled orchestration; routes and notifies.
- `db/migrations/` — append-only event store (`raw_events`, `pipeline_events`),
  current signal state (`signals`), and a `dead_letters` queue.

## Engineering decisions worth defending

| Decision | Why it matters |
|---|---|
| **Verify at the edge, not in n8n** | Downstream stages trust the payload; bad signatures fail early and cheaply (cheap before expensive). |
| **Idempotency via the `raw_events` PK** | At-least-once delivery is normal. Reprocessing a duplicate must be impossible, not unlikely. |
| **ACK `202` + process async** | Senders time out; slow downstream work must never block the acknowledgement. |
| **Append-only `pipeline_events`** | Event sourcing — replay history to rebuild state or backtest a new scoring model. |
| **Dead-letter queue + retries** | Silent failures are the #1 cause of "leads fell through the cracks." Every dropped forward is recorded and alertable. |
| **In-memory fallback store** | The whole pipeline runs in one command with zero infra; Postgres is opt-in, not required to demo. |
| **Scoring in code, mirrored in n8n** | Testable pure functions for the model; a visual workflow for tuning without redeploying. |

Design principle throughout: **the instruction stack, persistent context, and
feedback loops matter more than the tools.** n8n and Postgres are swappable; the
scoring model, routing logic, and event history are the durable asset.

The `instruction stack` is made explicit rather than scattered:

| Layer | Where |
|---|---|
| 1. ICP + scoring | `pipeline_core/scoring.py` — weights and thresholds are constants |
| 2. Messaging framework | openers carried on the signal (Pipeline C) |
| 3. Personalization rules | Pipeline C |
| 4. Sequence logic | `pipeline_core/routing.py` — bucket → owner → SLA |

## Verified engineering evidence

These are real, reproducible checks (run `make test` and `make send-test`):

- `14` unit tests pass across signature, normalize, scoring, and routing.
- `ruff` lint clean.
- Signed webhook → `202 accepted`; replay → `200 duplicate` (idempotency);
  unsigned → `401`; tampered signature → `401` (constant-time HMAC).
- Sample signal scores `fit 50 / intent 70 / priority 59` → routed `warm` →
  `sdr_priority_queue`, SLA 240 min — deterministic and asserted in tests.

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
  verification, idempotency, scoring math, retries, event history.

The workflow JSON is committed to Git and imported via `make import-workflow`,
so orchestration is versioned like everything else.

## What's next

- **Pipeline B** — enrichment waterfall (free providers), real firmographic fit,
  a metrics dashboard. Seam: `score_signal` already accepts firmographic /
  technographic / behavioral inputs.
- **Pipeline C** — LLM-drafted openers on a free tier, a human review queue, and
  a feedback loop that re-weights scoring from real reply/meeting outcomes.
