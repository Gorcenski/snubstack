# snubstack

Firehose-driven Bluesky labeler for link platforms. Substack first;
architecture generalizes to any platform via pluggable detectors.

## Architecture

- `consumer` — subscribes to Jetstream, extracts URLs, routes each to
  `red` (enqueue label), `green` (drop), or `unknown` (queue domain + buffer post).
- `worker` — claims hosts from `fetch_queue`, fetches HTML, runs detectors,
  updates `domains`, back-labels buffered posts. Also runs the **outbox loop**
  that drains pending labels to Ozone.
- `ozone` — Bluesky's moderation + labeler service. Owns the public xrpc
  surface (`com.atproto.label.queryLabels`, `subscribeLabels`) and the
  signing key. snubstack pushes labels into Ozone via
  `tools.ozone.moderation.emitEvent`.
- `postgres` — snubstack's own state (`domains`, `fetch_queue`,
  `pending_posts`, `labels_emitted` outbox). Ozone has its own Postgres.
- `nginx` (host) — TLS + reverse proxy `/xrpc/` → Ozone.

```
Jetstream ──▶ consumer ──▶ enqueue_label (pending)
                                 │
                                 ▼
fetch_queue ◀── worker ──▶ outbox_loop ──▶ Ozone /xrpc/tools.ozone...emitEvent
                                                    │
                                                    ▼
                                          public /xrpc/com.atproto.label.*
```

## Local dev

```sh
cp .env.example .env
# fill in: POSTGRES_PASSWORD, LABELER_DID, OZONE_* (signing key hex, admin password)

docker compose build
docker compose up -d
# Ozone admin UI proxied via the labeler service at http://localhost:3000

# load seeds
docker compose run --rm consumer \
    python -m snubstack.ops.seed seeds/substack_red.txt --state red --platform substack
docker compose run --rm consumer \
    python -m snubstack.ops.seed seeds/green.txt --state green
```

## Deploy (Exoscale, GHA)

Mirrors the registryblue deploy pattern:

1. Push to `main` → GHA builds + pushes `ghcr.io/<owner>/snubstack:{sha,latest}`.
2. Workflow SSHes to the VM, copies `docker-compose.prod.yml` →
   `/opt/snubstack/docker-compose.yml`, writes `/opt/snubstack/.env`,
   runs `docker compose up -d`.
3. Host nginx terminates TLS and proxies `:443` → `127.0.0.1:7401` (Ozone).

**Required GitHub Actions secrets:**
- `EXOSCALE_SSH_PRIVATE_KEY`, `EXOSCALE_SSH_HOST`, `EXOSCALE_SSH_USER`
- `POSTGRES_PASSWORD` — snubstack DB
- `OZONE_DB_PASSWORD` — Ozone DB (separate)
- `LABELER_DID` — your labeler DID (`did:plc:...`)
- `OZONE_PUBLIC_URL` — e.g. `https://labeler.example.com`
- `OZONE_ADMIN_DIDS` — comma-separated admin DIDs (yours)
- `OZONE_ADMIN_PASSWORD` — long random string; also used by snubstack
  to authenticate to Ozone's admin API
- `OZONE_SIGNING_KEY_HEX` — secp256k1 private key in hex; generate with
  `openssl ecparam -name secp256k1 -genkey -noout -outform DER | tail -c 32 | xxd -p -c 32`
- `EMIT_LABELS` (optional) — `true` to leave shadow mode

**One-time host setup:**
- Install Docker + compose plugin, nginx (you're managing certbot).
- `sudo mkdir -p /opt/snubstack` then chown to deploy user (workflow does this automatically).
- Install `nginx/snubstack.conf` into `/etc/nginx/sites-available/`,
  symlink, edit `server_name` and cert paths.

## Operating posture

- **Shadow mode is default.** `EMIT_LABELS=false` makes the outbox skip
  Ozone — labels land in `labels_emitted` with `status='shadow'` so you can
  inspect what *would* have been emitted. Flip to true after spot-checking.
- **Auto-promote threshold `0.9`, review threshold `0.6`.** Medium-confidence
  domains land in `pending_review` for manual triage in Ozone's UI.

## Before production

- [ ] Publish your labeler DID with the service endpoint (Ozone's public URL).
- [ ] Verify Ozone admin auth header — code currently sends Bearer; older builds
      expected Basic auth (`admin:<password>`). Adjust `ozone/client.py` if needed.
- [ ] Populate `seeds/green.txt` (Tranco top-10k) before first run.
- [ ] Shortener resolver worker (consumer currently skips known shorteners).
- [ ] Re-validation sweep for `red` domains (30-day cadence).
- [ ] Prometheus metrics on each service.

## Layout

```
src/snubstack/
  config.py, db.py, models.py, urls.py, queue.py, labels.py, logging_setup.py
  consumer/   jetstream.py, extract.py, routing.py, main.py
  worker/     fetcher.py, classify.py, main.py   # also runs the outbox loop
  detectors/  base.py, domain_match.py, substack.py
  ozone/      client.py                          # tools.ozone.moderation.emitEvent
  ops/        seed.py
migrations/versions/0001_initial.py, 0002_label_outbox.py
nginx/snubstack.conf
seeds/substack_red.txt, seeds/green.txt
.github/workflows/deploy.yml
```
