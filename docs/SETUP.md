# Setup

Everything here is free / free tier. No paid hosting required.

## 1. Prerequisites

| Tool | Why | Install (macOS) |
|---|---|---|
| uv | Python env + deps | `brew install uv` |
| Docker Desktop | Postgres + n8n | `brew install --cask docker` |
| cloudflared | public HTTPS tunnel to your machine | `brew install cloudflared` |

## 2. Install and configure

```bash
make install
cp .env.example .env
```

Edit `.env`:

- `SYGNAL_WEBHOOK_SECRET` — the signing secret for your Sygnal webhook. **While blank, signature verification is disabled** (handy for the first run, unsafe for anything real).
- `DATABASE_URL` — leave the default once Postgres is up; blank it to fall back to the in-memory store.
- `N8N_WEBHOOK_URL` / `SLACK_WEBHOOK_URL` — optional until you wire the orchestration layer.

## 3. Run without Docker (fastest path)

```bash
make run          # terminal 1 - receiver on :8080
make send-test    # terminal 2 - signed sample signal -> 202 accepted
curl localhost:8080/signals/recent
```

The receiver uses an in-memory store when `DATABASE_URL` is blank, so you can see the full flow before touching Postgres.

## 4. Full local stack (Postgres + n8n)

```bash
make up               # postgres + n8n; schema auto-applies from db/migrations
make import-workflow  # load Pipeline A into n8n
open http://localhost:5678
```

n8n stores its own data in the `n8n_data` Docker volume and its config lives in the compose file.

If you already run Postgres locally on `5432`, set `POSTGRES_HOST_PORT=5433` in `.env` (and update `DATABASE_URL` to match) so the container doesn't collide.

### n8n environment for the workflow

The Pipeline A workflow reads `ROUTE_HOT_THRESHOLD`, `ROUTE_WARM_THRESHOLD` and `SLACK_WEBHOOK_URL` from the environment. They are already set in `docker-compose.yml`; set `SLACK_WEBHOOK_URL` in your shell before `make up` to enable notifications.

## 5. Public webhook URL via Cloudflare Tunnel

Sygnal needs a public HTTPS endpoint. Keep it free with a quick tunnel:

```bash
make tunnel
# prints something like https://blue-river-1234.trycloudflare.com
```

Register `https://<random>.trycloudflare.com/webhooks/sygnal` as the webhook target in Sygnal for the `sygnal.signal` event, then set the same `SYGNAL_WEBHOOK_SECRET`.

Notes:

- Quick tunnels get a new random URL each restart. For a stable hostname, create a free named tunnel (`cloudflared tunnel create`) tied to a domain you own.
- Your machine must be awake to receive events. Fine for building and demos; for always-on, a small free VM is the next step.

## 6. Verify end-to-end

```bash
make send-test                          # signed sample -> 202
curl -s localhost:8080/healthz | jq     # verification/store/n8n status
make psql                               # select * from pipeline_events order by id desc limit 20;
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `401 invalid_signature` | secret mismatch | align `SYGNAL_WEBHOOK_SECRET` with the Sygnal webhook secret |
| `duplicate` on every send | same fixture `event_id` | expected — dedupe works; edit `event_id` in the fixture to test new events |
| `durable_store: false` | Postgres not reachable | `make up`, then check `DATABASE_URL` |
| n8n not called | `N8N_WEBHOOK_URL` blank or workflow inactive | set the URL and activate the workflow in n8n |
| Forensics on a failed forward | dead letter queue | `select * from dead_letters order by id desc;` |
