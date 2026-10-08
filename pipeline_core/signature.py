"""HMAC-SHA256 webhook signature verification.

Sygnal signs each delivery with the project secret. We accept both the
`sha256=<hex>` GitHub-style format and a bare `<hex>` digest, and compare in
constant time to avoid timing attacks.
"""

from __future__ import annotations

import hashlib
import hmac


def compute_signature(body: bytes, secret: str) -> str:
    """Return `sha256=<hex>` for a raw request body."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _normalize(provided: str) -> str:
    provided = provided.strip()
    if provided.startswith("sha256="):
        return provided[len("sha256=") :]
    return provided


def verify_signature(body: bytes, provided: str | None, secret: str) -> bool:
    """Constant-time check of a webhook signature against the raw body."""
    if not secret:
        # Verification disabled: caller decides whether that is acceptable.
        return True
    if not provided:
        return False
    expected = _normalize(compute_signature(body, secret))
    candidate = _normalize(provided)
    return hmac.compare_digest(expected, candidate)
