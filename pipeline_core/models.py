"""Domain models for the signal pipeline.

A Sygnal webhook payload is normalized into a `NormalizedSignal` at ingest so
every downstream stage works against one stable schema. `RouteDecision` is the
output of the routing stage, consumed by the n8n workflow / notification sink.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class NormalizedSignal:
    signal_id: str
    source: str
    url: str = ""
    author: str = ""
    text: str = ""
    published_at: datetime | None = None
    # Sygnal's own evidence-backed buyer-intent score (0-10).
    sygnal_score: float | None = None
    # Scoring outputs (populated by pipeline_core.scoring).
    fit_score: int = 0
    intent_score: int = 0
    priority: int = 0
    bucket: str = "archive"
    raw: dict = field(default_factory=dict)


@dataclass
class RouteDecision:
    bucket: str
    priority: int
    action: str
    owner: str
    sla_minutes: int
    notify: bool


@dataclass(frozen=True)
class PipelineEvent:
    """Append-only event-store record (event sourcing for the pipeline)."""

    pipeline_id: str
    event_type: str
    payload: dict
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
