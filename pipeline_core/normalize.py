"""Normalize a Sygnal payload into `NormalizedSignal`.

Sygnal exposes the verdict through two slightly different shapes:

* webhook envelope (documented delivery):
      {"event": "sygnal.signal", "signal": { "entities": {...},
       "suggested_action": "...", "blueprint_explanation": "...", ... }}
* REST `list_signals` / `get_signal` rows (richer):
      {"event": "sygnal.signal", "entity": {...}, "recommended_action": "...",
       "blueprint": {"explanation": "...", "direct_evidence": [...]},
       "score": null, "legacy_score": 8, "source_label": "...", ...}

This module maps both (and minor variants) onto `NormalizedSignal`. It is
deliberately tolerant: alias keys per field let the pipeline keep working across
payload revisions and when replaying older events from the store. The pipeline
treats Sygnal's `score` as the verdict and never recomputes it; when `score` is
null (legacy rows pending backfill) it falls back to `legacy_score`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pipeline_core.models import Entities, NormalizedSignal, SourceRef

_ID_KEYS = ("signal_id", "signalId", "id")
_SCORE_KEYS = ("score", "legacy_score", "intent_score", "intentScore", "overall_score")
_ICP_KEYS = ("icp_score", "icpScore")
_POSTED_KEYS = ("posted_at", "postedAt", "published_at", "created_at")
_ACTION_KEYS = ("suggested_action", "recommended_action")
_EXPLANATION_KEYS = ("blueprint_explanation", "explanation")


def _first(payload: dict, keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
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


def _unwrap(payload: dict) -> dict:
    """Return the inner `signal` object (or the payload itself)."""
    for key in ("signal", "data"):
        inner = payload.get(key)
        if isinstance(inner, dict):
            return inner
    return payload


def normalize_signal(payload: dict) -> NormalizedSignal:
    """Map a raw Sygnal payload to a `NormalizedSignal`.

    Raises ValueError if no stable identifier can be found (needed for
    idempotent processing).
    """
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")

    inner = _unwrap(payload)

    signal_id = _first(inner, _ID_KEYS)
    if signal_id is None:
        raise ValueError("payload has no signal id")

    entities_raw = inner.get("entities")
    if not isinstance(entities_raw, dict):
        entities_raw = inner.get("entity") if isinstance(inner.get("entity"), dict) else {}

    source_raw = inner.get("source") if isinstance(inner.get("source"), dict) else {}
    blueprint_raw = inner.get("blueprint") if isinstance(inner.get("blueprint"), dict) else {}
    timestamps_raw = inner.get("timestamps") if isinstance(inner.get("timestamps"), dict) else {}

    label = _first(source_raw, ("label",)) or _first(inner, ("source_label", "sourceLabel"))
    url = _first(source_raw, ("url",)) or _first(inner, ("source_url", "sourceUrl"))
    posted = (
        _first(source_raw, _POSTED_KEYS)
        or _first(inner, _POSTED_KEYS)
        or _first(timestamps_raw, _POSTED_KEYS)
    )

    suggested_action = _first(inner, _ACTION_KEYS) or _first(
        blueprint_raw, ("recommended_action",)
    )
    explanation = _first(inner, _EXPLANATION_KEYS) or _first(blueprint_raw, _EXPLANATION_KEYS)
    evidence = _as_list(inner.get("direct_evidence")) or _as_list(
        blueprint_raw.get("direct_evidence")
    )

    return NormalizedSignal(
        signal_id=str(signal_id),
        score=_parse_score(_first(inner, _SCORE_KEYS)),
        icp_score=_parse_score(_first(inner, _ICP_KEYS)),
        score_breakdown=inner.get("score_breakdown") or {},
        intent_signals=_as_list(inner.get("intent_signals")),
        intent_type=inner.get("intent_type"),
        signal_kind=inner.get("signal_kind"),
        trigger_type=inner.get("trigger_type"),
        entities=Entities(
            company_name=str(entities_raw.get("company_name") or ""),
            company_domain=str(entities_raw.get("company_domain") or ""),
            author=str(entities_raw.get("author") or ""),
            competitors=[str(c) for c in _as_list(entities_raw.get("competitors"))],
            tools=[str(t) for t in _as_list(entities_raw.get("tools"))],
        ),
        topics=[str(t) for t in _as_list(inner.get("topics") or entities_raw.get("topics"))],
        title=str(inner.get("title") or ""),
        direct_evidence=evidence,
        blueprint_explanation=str(explanation or ""),
        suggested_action=str(suggested_action or ""),
        source=SourceRef(
            label=str(label or ""),
            url=str(url or ""),
            posted_at=_parse_dt(posted),
        ),
        raw=payload,
    )
