"""Verdict adapters (instruction-stack Layer 1, delegated to Sygnal).

Sygnal classifies and scores every signal. This module holds the *only* scoring
logic the pipeline owns: a deterministic, dependency-free mapping from Sygnal's
0-10 verdict onto a 0-100 priority used for thresholding, plus small helpers the
routing layer reads.

There is intentionally NO parallel fit/intent model here. Recomputing Sygnal's
score would duplicate the product's core competency and risk disagreeing with
the source of truth.
"""

from __future__ import annotations

from pipeline_core.models import NormalizedSignal

_SCORE_MIN = 0.0
_SCORE_MAX = 10.0


def priority_from_score(score: float | None) -> int:
    """Map Sygnal's 0-10 overall score onto a 0-100 priority for thresholds."""
    if score is None:
        return 0
    clamped = max(_SCORE_MIN, min(_SCORE_MAX, float(score)))
    return int(round(clamped * 10))


def is_competitive(signal: NormalizedSignal) -> bool:
    """True when Sygnal named a competitor (drives the competitive play)."""
    return bool(signal.entities.competitors)


def has_icp_match(signal: NormalizedSignal, *, minimum: float = 6.0) -> bool:
    """Whether the signal clears the ICP-fit bar (Sygnal's `icp_score`)."""
    return signal.icp_score is not None and signal.icp_score >= minimum
