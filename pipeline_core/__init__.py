"""GTM engineering pipeline core.

Shared, dependency-light domain logic used by the webhook receiver, the n8n
workflows and (later) the enrichment/personalization services.

Stages of the pipeline this package covers:
    normalize -> score -> route
"""

from pipeline_core.models import NormalizedSignal, RouteDecision

__all__ = ["NormalizedSignal", "RouteDecision"]
