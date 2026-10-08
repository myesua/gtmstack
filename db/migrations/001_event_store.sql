-- Pipeline A schema: append-only event store + signal state + dead letters.
-- Apply with: psql "$DATABASE_URL" -f db/migrations/001_event_store.sql
-- (docker-compose applies it automatically via /docker-entrypoint-initdb.d)

CREATE TABLE IF NOT EXISTS raw_events (
    event_id        TEXT PRIMARY KEY,
    source          TEXT NOT NULL DEFAULT 'unknown',
    signature_valid BOOLEAN NOT NULL DEFAULT FALSE,
    payload         JSONB NOT NULL,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS raw_events_received_at_idx ON raw_events (received_at DESC);

-- Append-only pipeline audit log (event sourcing): ingest -> score -> route -> notify.
CREATE TABLE IF NOT EXISTS pipeline_events (
    id          BIGSERIAL PRIMARY KEY,
    pipeline_id TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS pipeline_events_pipeline_idx ON pipeline_events (pipeline_id, created_at DESC);

-- Current state of each scoreable signal.
CREATE TABLE IF NOT EXISTS signals (
    signal_id      TEXT PRIMARY KEY,
    source         TEXT NOT NULL DEFAULT 'unknown',
    url            TEXT NOT NULL DEFAULT '',
    author         TEXT NOT NULL DEFAULT '',
    text           TEXT NOT NULL DEFAULT '',
    sygnal_score   NUMERIC(4,1),
    fit_score      INTEGER NOT NULL DEFAULT 0,
    intent_score   INTEGER NOT NULL DEFAULT 0,
    priority       INTEGER NOT NULL DEFAULT 0,
    bucket         TEXT NOT NULL DEFAULT 'archive',
    status         TEXT NOT NULL DEFAULT 'new',
    payload        JSONB NOT NULL DEFAULT '{}'::jsonb,
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_scored_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS signals_bucket_priority_idx ON signals (bucket, priority DESC);

-- Failed downstream forwards, kept for replay / alerting (dead letter queue).
CREATE TABLE IF NOT EXISTS dead_letters (
    id         BIGSERIAL PRIMARY KEY,
    event_id   TEXT NOT NULL,
    attempt    INTEGER NOT NULL DEFAULT 1,
    error      TEXT NOT NULL DEFAULT '',
    payload    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS dead_letters_event_idx ON dead_letters (event_id, created_at DESC);
