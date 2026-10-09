"""Pipeline A edge service.

    Sygnal webhook -> [this receiver] -> n8n (orchestration) -> Slack / CRM

Responsibilities (everything that must be correct before downstream work):
  1. Verify the HMAC signature on the raw body.
  2. Enforce idempotency via an append-only raw_events table.
  3. ACK fast (202) and process asynchronously.
  4. Normalize Sygnal's verdict and route it (no re-scoring).
  5. Forward to n8n with retries; dead-letter on final failure.

Run:
    uv run uvicorn services.webhook_receiver.app:app --reload --port 8080
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse

from pipeline_core.config import get_settings
from pipeline_core.db import build_store
from pipeline_core.models import NormalizedSignal, RouteDecision
from pipeline_core.normalize import normalize_signal
from pipeline_core.routing import route_signal
from pipeline_core.signature import verify_signature

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("pipeline.receiver")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.store = build_store(settings.database_url)
    app.state.http = httpx.AsyncClient(timeout=settings.n8n_forward_timeout_seconds)
    log.info(
        "receiver up | verification=%s | durable_store=%s | n8n=%s",
        settings.verification_enabled,
        type(app.state.store).__name__ == "PostgresStore",
        settings.n8n_webhook_url or "disabled",
    )
    try:
        yield
    finally:
        await app.state.http.aclose()


app = FastAPI(title="GTM Pipeline A - Sygnal Signal Router", version="0.2.0", lifespan=lifespan)


def _extract_event_id(payload: dict, signal: NormalizedSignal) -> str:
    # Sygnal's webhook envelope is {"event": ..., "signal": {...}} and carries no
    # delivery id, so the signal id is the idempotency key.
    for key in ("event_id", "eventId"):
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return signal.signal_id


def _signal_dict(signal: NormalizedSignal, decision: RouteDecision | None = None) -> dict:
    data = {
        "signal_id": signal.signal_id,
        "score": signal.score,
        "icp_score": signal.icp_score,
        "priority": signal.priority,
        "intent_type": signal.intent_type,
        "signal_kind": signal.signal_kind,
        "trigger_type": signal.trigger_type,
        "title": signal.title,
        "source_label": signal.source.label,
        "url": signal.source.url,
        "posted_at": signal.source.posted_at.isoformat() if signal.source.posted_at else None,
        "company": signal.entities.company_name,
        "company_domain": signal.entities.company_domain,
        "author": signal.entities.author,
        "competitors": signal.entities.competitors,
        "tools": signal.entities.tools,
        "topics": signal.topics,
        "suggested_action": signal.suggested_action,
    }
    if decision is not None:
        data.update(
            {
                "bucket": decision.bucket,
                "play": decision.play,
                "action": decision.action,
                "owner": decision.owner,
                "sla_minutes": decision.sla_minutes,
                "notify": decision.notify,
            }
        )
    return data


async def _forward_to_n8n(app: FastAPI, body: dict) -> None:
    settings = app.state.settings
    if not settings.n8n_webhook_url:
        log.info("n8n not configured - skipping forward")
        return

    last_error = ""
    for attempt in range(1, settings.n8n_forward_attempts + 1):
        try:
            response = await app.state.http.post(settings.n8n_webhook_url, json=body)
            response.raise_for_status()
            log.info("forwarded to n8n (attempt %d)", attempt)
            app.state.store.append_pipeline_event(
                body["event_id"], "forward.sent", {"target": settings.n8n_webhook_url}
            )
            return
        except Exception as exc:  # noqa: BLE001 - retry anything transient
            last_error = str(exc)
            log.warning("n8n forward attempt %d failed: %s", attempt, last_error)
            if attempt < settings.n8n_forward_attempts:
                await asyncio.sleep(2 ** (attempt - 1))

    app.state.store.record_dead_letter(
        event_id=body["event_id"],
        attempt=settings.n8n_forward_attempts,
        error=last_error,
        payload=body,
    )
    app.state.store.append_pipeline_event(
        body["event_id"],
        "forward.failed",
        {"error": last_error, "target": settings.n8n_webhook_url},
    )


async def _send_slack(app: FastAPI, signal: NormalizedSignal, decision: RouteDecision) -> None:
    url = app.state.settings.slack_webhook_url
    if not (decision.notify and url):
        return
    competitor = ""
    if decision.play == "competitive":
        competitor = f" · competitor: {signal.entities.competitors[0]}"
    text = (
        f":rotating_light: *{decision.bucket.upper()}* signal "
        f"(score {signal.score}/10, icp {signal.icp_score}, priority {signal.priority})\n"
        f"*{signal.source.label}*{competitor}\n"
        f"{signal.title}\n{signal.source.url}\n"
        f"_{signal.suggested_action}_"
    )
    try:
        await app.state.http.post(url, json={"text": text})
    except Exception as exc:  # noqa: BLE001
        log.warning("slack notify failed: %s", exc)


async def _process(app: FastAPI, event_id: str, signal: NormalizedSignal) -> None:
    store = app.state.store
    store.append_pipeline_event(event_id, "signal.received", _signal_dict(signal))

    # Sygnal already scored/classified this signal; we only route the verdict.
    decision = route_signal(signal)
    store.append_pipeline_event(
        event_id,
        "signal.routed",
        {
            "bucket": decision.bucket,
            "play": decision.play,
            "action": decision.action,
            "priority": decision.priority,
            "sla_minutes": decision.sla_minutes,
        },
    )
    store.upsert_signal(signal, decision)

    await _forward_to_n8n(app, {"event_id": event_id, "signal": _signal_dict(signal, decision)})
    await _send_slack(app, signal, decision)


@app.post("/webhooks/sygnal")
async def sygnal_webhook(request: Request, background: BackgroundTasks):
    settings = get_settings()
    raw = await request.body()
    provided = request.headers.get(settings.signature_header)
    signature_valid = verify_signature(raw, provided, settings.sygnal_webhook_secret)

    if settings.verification_enabled and not signature_valid:
        log.warning("rejected webhook: bad signature")
        return JSONResponse(status_code=401, content={"status": "invalid_signature"})

    try:
        payload: Any = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"status": "invalid_json"})

    try:
        signal = normalize_signal(payload)
    except ValueError as exc:
        return JSONResponse(
            status_code=422, content={"status": "invalid_payload", "detail": str(exc)}
        )

    event_id = _extract_event_id(payload, signal)
    is_new = request.app.state.store.record_raw_event(
        event_id=event_id,
        source=signal.source.label or "sygnal",
        payload=payload,
        signature_valid=signature_valid,
    )
    if not is_new:
        log.info("duplicate delivery %s - acked, not reprocessed", event_id)
        return {"status": "duplicate", "event_id": event_id}

    background.add_task(_process, request.app, event_id, signal)
    return JSONResponse(status_code=202, content={"status": "accepted", "event_id": event_id})


@app.get("/healthz")
async def healthz():
    settings = get_settings()
    store = app.state.store
    return {
        "status": "ok",
        "verification_enabled": settings.verification_enabled,
        "durable_store": type(store).__name__ == "PostgresStore",
        "n8n_configured": bool(settings.n8n_webhook_url),
    }


@app.get("/signals/recent")
async def recent_signals(limit: int = 20):
    return {"signals": app.state.store.recent_signals(limit)}


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "services.webhook_receiver.app:app", host=settings.host, port=settings.port, reload=True
    )
