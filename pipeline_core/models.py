"""Domain models for the Sygnal-driven signal pipeline.

Design pivot: Sygnal owns classification and scoring (five-dimension
`score_breakdown`, `score`, `icp_score`, entities, suggested action). This
pipeline does NOT re-score. It normalizes Sygnal's verdict, decides *where the
signal should go* (routing), and acts. Everything here mirrors the fields in
Sygnal's webhook payload schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class Entities:
    """Entities Sygnal extracted from (and around) the signal."""

    company_name: str = ""
    company_domain: str = ""
    author: str = ""
    competitors: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)


@dataclass
class SourceRef:
    """Where the signal came from (Sygnal's `source` object)."""

    label: str = ""
    url: str = ""
    posted_at: datetime | None = None


@dataclass
class NormalizedSignal:
    """Sygnal's verdict, normalized to one stable schema for the pipeline."""

    signal_id: str

    # --- Sygnal's verdict (authoritative; the pipeline does not recompute) ---
    score: float | None = None  # overall intent score, 0-10
    icp_score: float | None = None  # fit against the account profile, 0-10
    score_breakdown: dict = field(default_factory=dict)  # factor -> {score, evidence}
    intent_signals: list[str] = field(default_factory=list)
    intent_type: str | None = None
    signal_kind: str | None = None
    trigger_type: str | None = None
    entities: Entities = field(default_factory=Entities)
    topics: list[str] = field(default_factory=list)
    title: str = ""
    direct_evidence: list[dict] = field(default_factory=list)
    blueprint_explanation: str = ""
    suggested_action: str = ""
    source: SourceRef = field(default_factory=SourceRef)

    # --- Pipeline state (derived) ---
    priority: int = 0  # score scaled to 0-100 for thresholding
    bucket: str = "archive"
    raw: dict = field(default_factory=dict)


@dataclass
class RouteDecision:
    """Output of routing, consumed by the notify/act layer."""

    bucket: str
    priority: int
    play: str  # "competitive" when a competitor is named, else "standard"
    action: str
    owner: str
    sla_minutes: int
    notify: bool
    suggested_action: str = ""


@dataclass(frozen=True)
class PipelineEvent:
    """Append-only event-store record (event sourcing for the pipeline)."""

    pipeline_id: str
    event_type: str
    payload: dict
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
