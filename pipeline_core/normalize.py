"""Normalize a raw Sygnal webhook payload into `NormalizedSignal`.

Sygnal's payload schema is the source of truth (see trysygnal.com sample
payload). This function is intentionally tolerant: it accepts a set of alias
keys per field so the pipeline keeps working across minor payload revisions and
when replaying older events from the store.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pipeline_core.models import NormalizedSignal

_ID_KEYS = ("signal_id", "signalId", "id")
_SOURCE_KEYS = ("source", "platform")
_URL_KEYS = ("url", "source_url", "sourceUrl", "permalink", "link")
_AUTHOR_KEYS = ("author", "author_handle", "authorHandle", "username", "user")
_TEXT_KEYS = ("text", "body", "content", "excerpt", "title")
_PUBLISHED_KEYS = ("published_at", "publishedAt", "created_at", "createdAt", "posted_at")
_SCORE_KEYS = ("score", "intent_score", "intentScore", "buyer_intent_score")


def _first(payload: dict, keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        # Unix seconds or milliseconds.
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=UTC)
    if isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _parse_score(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_signal(payload: dict) -> NormalizedSignal:
    """Map a raw payload dict to a `NormalizedSignal`.

    Raises ValueError if no stable identifier can be found (needed for
    idempotent processing).
    """
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")

    # Some senders wrap the signal: {"event": "...", "data": {...}}
    inner = payload.get("data") if isinstance(payload.get("data"), dict) else payload

    signal_id = _first(inner, _ID_KEYS)
    if signal_id is None:
        raise ValueError("payload has no signal id")

    source = _first(inner, _SOURCE_KEYS) or "unknown"
    text = _first(inner, _TEXT_KEYS) or ""

    return NormalizedSignal(
        signal_id=str(signal_id),
        source=str(source).lower(),
        url=str(_first(inner, _URL_KEYS) or ""),
        author=str(_first(inner, _AUTHOR_KEYS) or ""),
        text=str(text),
        published_at=_parse_dt(_first(inner, _PUBLISHED_KEYS)),
        sygnal_score=_parse_score(_first(inner, _SCORE_KEYS)),
        raw=payload,
    )
