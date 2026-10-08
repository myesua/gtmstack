"""Routing stage (instruction-stack Layer 4: sequence logic).

Maps a scored signal to a bucket, an owner and an SLA. The bucket determines
whether a human is alerted and which sequence the signal enters.
"""

from __future__ import annotations

from pipeline_core.config import get_settings
from pipeline_core.models import RouteDecision

# bucket -> (action, owner, sla_minutes, notify)
_ROUTES: dict[str, tuple[str, str, int, bool]] = {
    "hot": ("ae_direct", "ae", 60, True),
    "warm": ("sdr_priority_queue", "sdr", 240, False),
    "monitor": ("sdr_research_queue", "sdr", 1440, False),
    "nurture": ("nurture_sequence", "marketing", 10080, False),
    "archive": ("none", "none", 0, False),
}


def route(
    priority: int,
    *,
    hot_threshold: int | None = None,
    warm_threshold: int | None = None,
) -> RouteDecision:
    settings = get_settings()
    hot = settings.route_hot_threshold if hot_threshold is None else hot_threshold
    warm = settings.route_warm_threshold if warm_threshold is None else warm_threshold

    if priority >= hot:
        bucket = "hot"
    elif priority >= warm:
        bucket = "warm"
    elif priority >= 20:
        bucket = "monitor"
    else:
        bucket = "archive"

    action, owner, sla, notify = _ROUTES[bucket]
    return RouteDecision(
        bucket=bucket,
        priority=priority,
        action=action,
        owner=owner,
        sla_minutes=sla,
        notify=notify,
    )


def route_signal(signal) -> RouteDecision:
    decision = route(signal.priority)
    signal.bucket = decision.bucket
    return decision
