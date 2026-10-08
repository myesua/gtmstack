"""Persistence layer.

Two implementations behind one small interface:

* `PostgresStore`  - production path (docker-compose provisions Postgres).
* `MemoryStore`    - zero-dependency fallback so the receiver runs before you
                     start Docker (state is lost on restart).

Idempotency contract: `record_raw_event` returns False when the event id was
already seen, so the receiver can safely ack duplicate deliveries.
"""

from __future__ import annotations

import json
import logging
from typing import Protocol

from pipeline_core.models import NormalizedSignal, RouteDecision

log = logging.getLogger("pipeline.db")


class Store(Protocol):
    def record_raw_event(
        self, event_id: str, source: str, payload: dict, signature_valid: bool
    ) -> bool: ...

    def append_pipeline_event(self, pipeline_id: str, event_type: str, payload: dict) -> None: ...

    def upsert_signal(
        self, signal: NormalizedSignal, decision: RouteDecision
    ) -> None: ...

    def record_dead_letter(
        self, event_id: str, attempt: int, error: str, payload: dict
    ) -> None: ...

    def recent_signals(self, limit: int = 20) -> list[dict]: ...


class MemoryStore:
    """In-process store for local testing / no-DB mode."""

    def __init__(self) -> None:
        self._event_ids: set[str] = set()
        self._events: list[dict] = []
        self._signals: dict[str, dict] = {}
        self._dead_letters: list[dict] = []

    def record_raw_event(
        self, event_id: str, source: str, payload: dict, signature_valid: bool
    ) -> bool:
        if event_id in self._event_ids:
            return False
        self._event_ids.add(event_id)
        self._events.append(
            {
                "event_id": event_id,
                "source": source,
                "signature_valid": signature_valid,
                "payload": payload,
            }
        )
        return True

    def append_pipeline_event(self, pipeline_id: str, event_type: str, payload: dict) -> None:
        self._events.append(
            {"pipeline_id": pipeline_id, "event_type": event_type, "payload": payload}
        )

    def upsert_signal(self, signal: NormalizedSignal, decision: RouteDecision) -> None:
        self._signals[signal.signal_id] = {
            "signal_id": signal.signal_id,
            "source": signal.source,
            "url": signal.url,
            "author": signal.author,
            "text": signal.text,
            "sygnal_score": signal.sygnal_score,
            "fit_score": signal.fit_score,
            "intent_score": signal.intent_score,
            "priority": signal.priority,
            "bucket": decision.bucket,
        }

    def record_dead_letter(
        self, event_id: str, attempt: int, error: str, payload: dict
    ) -> None:
        self._dead_letters.append(
            {"event_id": event_id, "attempt": attempt, "error": error, "payload": payload}
        )

    def recent_signals(self, limit: int = 20) -> list[dict]:
        return list(self._signals.values())[-limit:]


class PostgresStore:
    """Postgres-backed store. Import errors are raised lazily by the caller."""

    def __init__(self, dsn: str) -> None:
        from psycopg_pool import ConnectionPool

        self._pool = ConnectionPool(conninfo=dsn, min_size=1, max_size=5, open=True)

    def close(self) -> None:
        self._pool.close()

    def record_raw_event(
        self, event_id: str, source: str, payload: dict, signature_valid: bool
    ) -> bool:
        with self._pool.connection() as conn:
            row = conn.execute(
                """
                INSERT INTO raw_events (event_id, source, signature_valid, payload)
                VALUES (%s, %s, %s, %s::jsonb)
                ON CONFLICT (event_id) DO NOTHING
                RETURNING event_id
                """,
                (event_id, source, signature_valid, json.dumps(payload)),
            ).fetchone()
        return row is not None

    def append_pipeline_event(self, pipeline_id: str, event_type: str, payload: dict) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO pipeline_events (pipeline_id, event_type, payload)
                VALUES (%s, %s, %s::jsonb)
                """,
                (pipeline_id, event_type, json.dumps(payload, default=str)),
            )

    def upsert_signal(self, signal: NormalizedSignal, decision: RouteDecision) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO signals (
                    signal_id, source, url, author, text, sygnal_score,
                    fit_score, intent_score, priority, bucket, payload, last_scored_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, now())
                ON CONFLICT (signal_id) DO UPDATE SET
                    fit_score = EXCLUDED.fit_score,
                    intent_score = EXCLUDED.intent_score,
                    priority = EXCLUDED.priority,
                    bucket = EXCLUDED.bucket,
                    last_scored_at = now(),
                    payload = EXCLUDED.payload
                """,
                (
                    signal.signal_id,
                    signal.source,
                    signal.url,
                    signal.author,
                    signal.text,
                    signal.sygnal_score,
                    signal.fit_score,
                    signal.intent_score,
                    signal.priority,
                    decision.bucket,
                    json.dumps(signal.raw, default=str),
                ),
            )

    def record_dead_letter(
        self, event_id: str, attempt: int, error: str, payload: dict
    ) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO dead_letters (event_id, attempt, error, payload)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (event_id, attempt, error, json.dumps(payload, default=str)),
            )

    def recent_signals(self, limit: int = 20) -> list[dict]:
        with self._pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT signal_id, source, url, author, text, sygnal_score,
                       fit_score, intent_score, priority, bucket, last_scored_at
                FROM signals
                ORDER BY last_scored_at DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        columns = (
            "signal_id", "source", "url", "author", "text", "sygnal_score",
            "fit_score", "intent_score", "priority", "bucket", "last_scored_at",
        )
        return [dict(zip(columns, row, strict=True)) for row in rows]


def build_store(database_url: str) -> Store:
    """Return a Postgres store when configured, else the in-memory fallback."""
    if not database_url:
        log.warning("DATABASE_URL not set - using in-memory store (state is not durable)")
        return MemoryStore()
    try:
        return PostgresStore(database_url)
    except Exception as exc:  # pragma: no cover - depends on local infra
        log.error("Postgres unavailable (%s) - falling back to in-memory store", exc)
        return MemoryStore()
