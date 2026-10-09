"""Webhook authenticity for Sygnal deliveries.

Sygnal's model is an optional **static shared secret**: you set a value in the
webhook config and it is sent verbatim in the `X-Sygnal-Secret` header on every
delivery. Sygnal does not sign the body, so verification is a constant-time
comparison of the header value to the configured secret.

For senders that do sign (our own test sender, or a future Sygnal revision) we
also accept an HMAC-SHA256 form: `sha256=<hex>` computed over the raw body.

Both paths use `hmac.compare_digest` to avoid timing attacks.
"""

from __future__ import annotations

import hashlib
import hmac


def compute_signature(body: bytes, secret: str) -> str:
    """Return `sha256=<hex>` HMAC for a raw request body."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(body: bytes, provided: str | None, secret: str) -> bool:
    """Constant-time webhook check.

    Accepts either:
      * the static shared secret sent verbatim (`X-Sygnal-Secret`), or
      * an HMAC of the raw body in `sha256=<hex>` form.

    Returns True when no secret is configured (verification disabled; the caller
    decides whether that is acceptable).
    """
    if not secret:
        return True
    if not provided:
        return False

    provided = provided.strip()
    if provided.startswith("sha256="):
        return hmac.compare_digest(compute_signature(body, secret), provided)
    return hmac.compare_digest(provided, secret)
