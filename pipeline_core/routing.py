"""Routing stage (instruction-stack Layer 4: sequence logic).

Turns Sygnal's verdict into a destination: a bucket, an owner, an SLA, and a
*play*. Routing reads the verdict (score -> priority) and Sygnal's extracted
entities (competitor named -> competitive play); it never recomputes the score.
"""

from __future__ import annotations

from pipeline_core.config import get_settings
from pipeline_core.models import NormalizedSignal, RouteDecision
from pipeline_core.verdict import is_competitive, priority_from_score

# bucket -> (action, owner, sla_minutes, notify)
_ROUTES: dict[str, tuple[str, str, int, bool]] = {
    "hot": ("ae_direct", "ae", 60, True),
    "warm": ("sdr_priority_queue", "sdr", 240, False),
    "monitor": ("sdr_research_queue", "sdr", 1440, False),
    "nurture": ("nurture_sequence", "marketing", 10080, False),
    "archive": ("none", "none", 0, False),
}


def bucket_for(priority: int, *, hot: int, warm: int) -> str:
    if priority >= hot:
        return "hot"
    if priority >= warm:
        return "warm"
    if priority >= 20:
        return "monitor"
    return "archive"


def route(
    signal: NormalizedSignal,
    *,
    hot_threshold: int | None = None,
    warm_threshold: int | None = None,
) -> RouteDecision:
    settings = get_settings()
    hot = settings.route_hot_threshold if hot_threshold is None else hot_threshold
    warm = settings.route_warm_threshold if warm_threshold is None else warm_threshold

    priority = priority_from_score(signal.score)
    bucket = bucket_for(priority, hot=hot, warm=warm)
    action, owner, sla, notify = _ROUTES[bucket]
    play = "competitive" if is_competitive(signal) else "standard"

    return RouteDecision(
        bucket=bucket,
        priority=priority,
        play=play,
        action=action,
        owner=owner,
        sla_minutes=sla,
        notify=notify,
        suggested_action=signal.suggested_action,
    )


def route_signal(signal: NormalizedSignal) -> RouteDecision:
    decision = route(signal)
    signal.priority = decision.priority
    signal.bucket = decision.bucket
    return decision
