"""Scoring model (instruction-stack Layer 1: ICP definition + scoring).

Two independent scores feed a composite priority, mirroring the standard GTM
formulas:

    Fit    = firmographic*0.40 + technographic*0.35 + behavioral*0.25
    Intent = first_party*0.40 + third_party*0.35 + trigger*0.25
    Priority = fit*0.55 + intent*0.45

All inputs are 0-100. `sygnal_score` (0-10) is Sygnal's evidence-backed
buyer-intent score and is used as the third-party intent component unless a
caller supplies an explicit value.
"""

from __future__ import annotations

from dataclasses import dataclass

from pipeline_core.models import NormalizedSignal

FIT_WEIGHTS = {"firmographic": 0.40, "technographic": 0.35, "behavioral": 0.25}
INTENT_WEIGHTS = {"first_party": 0.40, "third_party": 0.35, "trigger": 0.25}
PRIORITY_FIT_WEIGHT = 0.55
PRIORITY_INTENT_WEIGHT = 0.45

_HIGH_INTENT_TERMS = (
    "looking for",
    "recommend",
    "alternative to",
    "replacing",
    "migrating from",
    "how do i",
    "anyone using",
    "need a tool",
    "budget",
    "quote",
    " pricing",
)


@dataclass
class ScoreBreakdown:
    fit_score: int
    intent_score: int
    priority: int


def _clip(value: float) -> int:
    return int(max(0, min(100, round(value))))


def fit_score(
    *,
    firmographic: float = 50,
    technographic: float = 50,
    behavioral: float = 50,
) -> int:
    return _clip(
        firmographic * FIT_WEIGHTS["firmographic"]
        + technographic * FIT_WEIGHTS["technographic"]
        + behavioral * FIT_WEIGHTS["behavioral"]
    )


def intent_score(
    *,
    first_party: float = 0,
    third_party: float = 0,
    trigger: float = 0,
) -> int:
    return _clip(
        first_party * INTENT_WEIGHTS["first_party"]
        + third_party * INTENT_WEIGHTS["third_party"]
        + trigger * INTENT_WEIGHTS["trigger"]
    )


def priority(fit: int, intent: int) -> int:
    return _clip(fit * PRIORITY_FIT_WEIGHT + intent * PRIORITY_INTENT_WEIGHT)


def _sygnal_to_third_party(sygnal_score: float | None) -> float:
    """Map Sygnal's 0-10 buyer-intent score onto the 0-100 third-party axis."""
    if sygnal_score is None:
        return 0.0
    return max(0.0, min(10.0, sygnal_score)) * 10.0


def _first_party_hint(text: str) -> float:
    """Cheap, deterministic first-party signal from the post text.

    Pipeline B replaces this with real behavior data (site visits, prior
    engagement). Kept here so Pipeline A is self-contained.
    """
    lowered = (text or "").lower()
    if not lowered:
        return 0.0
    hits = sum(1 for term in _HIGH_INTENT_TERMS if term in lowered)
    return min(100.0, hits * 34.0)


def score_signal(signal: NormalizedSignal) -> ScoreBreakdown:
    """Compute fit/intent/priority for a normalized signal.

    Fit defaults to the ICP midline for Pipeline A (no enrichment yet); Pass
    explicit firmographic/technographic values once Pipeline B enrichment is
    wired in.
    """
    intent = intent_score(
        first_party=_first_party_hint(signal.text),
        third_party=_sygnal_to_third_party(signal.sygnal_score),
        trigger=0.0,
    )
    fit = fit_score()
    prio = priority(fit, intent)

    signal.fit_score = fit
    signal.intent_score = intent
    signal.priority = prio
    return ScoreBreakdown(fit_score=fit, intent_score=intent, priority=prio)
