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

-- Current state of each signal. The score/icp_score/score_breakdown columns
-- carry Sygnal's verdict; `priority` is the pipeline's 0-100 threshold scale.
CREATE TABLE IF NOT EXISTS signals (
    signal_id        TEXT PRIMARY KEY,
    score            NUMERIC(4,1),
    icp_score        NUMERIC(4,1),
    priority         INTEGER NOT NULL DEFAULT 0,
    bucket           TEXT NOT NULL DEFAULT 'archive',
    play             TEXT NOT NULL DEFAULT 'standard',
    intent_type      TEXT,
    signal_kind      TEXT,
    has_competitor   BOOLEAN NOT NULL DEFAULT FALSE,
    competitors      JSONB NOT NULL DEFAULT '[]'::jsonb,
    topics           JSONB NOT NULL DEFAULT '[]'::jsonb,
    company_name     TEXT NOT NULL DEFAULT '',
    company_domain   TEXT NOT NULL DEFAULT '',
    author           TEXT NOT NULL DEFAULT '',
    title            TEXT NOT NULL DEFAULT '',
    url              TEXT NOT NULL DEFAULT '',
    source_label     TEXT NOT NULL DEFAULT '',
    suggested_action TEXT NOT NULL DEFAULT '',
    status           TEXT NOT NULL DEFAULT 'new',
    payload          JSONB NOT NULL DEFAULT '{}'::jsonb,
    first_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_scored_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS signals_bucket_priority_idx ON signals (bucket, priority DESC);
CREATE INDEX IF NOT EXISTS signals_competitor_idx ON signals (has_competitor) WHERE has_competitor;

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
