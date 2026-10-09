#!/usr/bin/env python3
"""Send a signed test webhook to the local receiver.

    uv run python scripts/send_test_signal.py
    uv run python scripts/send_test_signal.py --url http://localhost:8080/webhooks/sygnal

Uses SYGNAL_WEBHOOK_SECRET from the environment (or .env) as the shared-secret
header value, mirroring the exact verification path Sygnal uses in production.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "fixtures" / "sample_sygnal_signal.json"


def load_env() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8080/webhooks/sygnal")
    parser.add_argument("--fixture", default=str(FIXTURE))
    args = parser.parse_args()

    load_env()
    secret = os.environ.get("SYGNAL_WEBHOOK_SECRET", "")
    header = os.environ.get("SYGNAL_SIGNATURE_HEADER", "X-Sygnal-Secret")

    body = pathlib.Path(args.fixture).read_bytes()
    headers = {"Content-Type": "application/json"}
    if secret:
        # Mirror Sygnal: send the static shared secret verbatim in the header.
        headers[header] = secret

    request = urllib.request.Request(args.url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request) as response:
        print(response.status, response.read().decode())


if __name__ == "__main__":
    main()
