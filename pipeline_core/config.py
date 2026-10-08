"""Environment-driven configuration.

Kept as a plain dataclass (no pydantic-settings dependency) so the core stays
importable from n8n Code nodes, scripts and tests alike.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _split_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


@dataclass(frozen=True)
class Settings:
    host: str = "0.0.0.0"
    port: int = 8080

    sygnal_webhook_secret: str = ""
    signature_header: str = "X-Sygnal-Signature"

    n8n_webhook_url: str = ""
    n8n_forward_attempts: int = 3
    n8n_forward_timeout_seconds: int = 10

    database_url: str = ""

    slack_webhook_url: str = ""

    route_hot_threshold: int = 70
    route_warm_threshold: int = 40

    # Optional: only route signals from these sources (empty = all).
    allowed_sources: list[str] = field(default_factory=list)

    @property
    def verification_enabled(self) -> bool:
        return bool(self.sygnal_webhook_secret)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        host=os.environ.get("RECEIVER_HOST", "0.0.0.0"),
        port=_int("RECEIVER_PORT", 8080),
        sygnal_webhook_secret=os.environ.get("SYGNAL_WEBHOOK_SECRET", ""),
        signature_header=os.environ.get("SYGNAL_SIGNATURE_HEADER", "X-Sygnal-Signature"),
        n8n_webhook_url=os.environ.get("N8N_WEBHOOK_URL", ""),
        n8n_forward_attempts=_int("N8N_FORWARD_ATTEMPTS", 3),
        n8n_forward_timeout_seconds=_int("N8N_FORWARD_TIMEOUT_SECONDS", 10),
        database_url=os.environ.get("DATABASE_URL", ""),
        slack_webhook_url=os.environ.get("SLACK_WEBHOOK_URL", ""),
        route_hot_threshold=_int("ROUTE_HOT_THRESHOLD", 70),
        route_warm_threshold=_int("ROUTE_WARM_THRESHOLD", 40),
        allowed_sources=_split_csv(os.environ.get("ALLOWED_SOURCES")),
    )
