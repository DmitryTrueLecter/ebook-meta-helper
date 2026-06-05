# Environments

Single source of truth for environment topology, service endpoints, deploy mechanics, and access constraints. Read by `agents/devops.md` on every spawn. Update whenever an environment changes.

**Never paste real secrets in this file.** Use placeholders (`<DB_PASSWORD>`) and reference where the human reads the actual value (vault, CI secret store, password manager).

## Local

- **Status:** Active — primary development environment (Windows 11 / Docker Desktop).
- **Runtime:** Docker Compose — `docker-compose.yml` (prod base) overridden by `docker-compose.local.yml`. Images built locally from source (no registry pull). No Traefik; API is hit directly.
- **Services:**
  - `api` — FastAPI backend + Vue 3 SPA static files, bound to `127.0.0.1:${API_PORT:-8000}` on the host.
  - `watcher` — background file-watcher process (same image, different command).
  - `mariadb` — MariaDB 11, bound to `127.0.0.1:${DB_PORT:-3306}` on the host.
- **Networks:** `backend` bridge (internal to the stack). The `web` network is declared with `external: false` in the local override so Compose never requires it to exist.
- **Database:** `ebook_meta` (default). Reach via `127.0.0.1:3306` with credentials from `.env` (`DB_USER` / `DB_PASSWORD` / `DB_ROOT_PASSWORD`). Reference: `.env.example`.
- **Build / start:** `just up-local` (builds images from source each time). Stop: `just down-local`.
- **Logs:** `just logs-api`, `just logs-watcher`, `just logs-mariadb` (docker compose logs to stdout).
- **Host path requirements:** `HOST_NEW_BOOKS_DIR`, `HOST_BOOKS_READY_DIR` must be set in `.env`. Windows paths (e.g. `D:\Books\inbox`) are valid; Docker Desktop translates them. The host drive must be enabled under Docker Desktop > Settings > Resources > File sharing.
- **Common breakage modes:**
  - `HOST_NEW_BOOKS_DIR` / `HOST_BOOKS_READY_DIR` not set → compose fails at volume mount.
  - Windows path with backslash in `.env` needs forward slashes, or use double-backslash.
  - MariaDB healthcheck fails on first-ever start if init is slow → increase `start_period` or re-run `just up-local`.
  - `RUN_MIGRATIONS=1` triggers Alembic on every `up-local`; migration failures abort the api container start.

## Staging

- **Status:** Does not exist for this project. No staging environment is provisioned.

## Production

- **Status:** Active.
- **Host:** Linux server (host details provided by operator; `<PROD_HOST_IP>` placeholder). SSH access via `ssh <DEPLOY_USER>@<PROD_HOST_IP>`.
- **Domain:** `meta.dmitry.work` (A record → `<PROD_HOST_IP>`; must exist before ACME issues a certificate).
- **Traefik topology:** A shared Traefik stack (separate `docker-compose.yml`, not part of this repo) runs on the same host. It owns:
  - Ports `80` and `443`.
  - HTTP→HTTPS global redirect (entrypoint `web` → `websecure`).
  - TLS certificate provisioning via Let's Encrypt HTTP-01 challenge (resolver name `letsencrypt`, storage `/letsencrypt/acme.json`).
  - `exposedbydefault=false` — services must opt in with `traefik.enable=true`.
  - Docker network: `web` (external, created by the Traefik stack, must exist before `docker compose up`).
  - The app does **not** ship its own Traefik. The `api` container joins the shared `web` network and opts in via labels only.
- **Services:**
  - `api` — FastAPI + Vue 3 SPA, exposed through Traefik at `https://meta.dmitry.work`. Internal port `8000`. No host port binding (traffic reaches it via the `web` Docker network only).
  - `watcher` — background watcher process; `backend` network only, no public exposure.
  - `mariadb` — MariaDB 11; `backend` network only, no host port binding.
- **Networks:**
  - `web` — external, shared with Traefik. Only `api` joins it.
  - `backend` — internal bridge; `api`, `watcher`, and `mariadb` join it. `internal: false` because `api` needs outbound internet access (OpenAI API calls).
- **Image delivery:** CI (GitHub Actions `build-push.yml`) builds and pushes `ghcr.io/dmitrytruelecter/ebook-meta-helper:<tag>` to GHCR on every push to `dev` (tag `sha-<short>` + `dev`) and on every semver tag push (tag `<version>` + `latest`). The prod compose references `ghcr.io/dmitrytruelecter/ebook-meta-helper:${IMAGE_TAG:-latest}`. Set `IMAGE_TAG` in the server `.env` to pin a specific digest.
- **Deploy mechanic (manual):**
  1. SSH onto the prod host.
  2. `docker login ghcr.io` (once, or use a PAT stored in the server's Docker credential store).
  3. `cd <DEPLOY_DIR>` (e.g. `/srv/ebook-meta-helper`).
  4. Update `IMAGE_TAG` in `.env` to the desired `sha-<short>` or version tag.
  5. `just pull-prod` — pulls the new image from GHCR.
  6. `just up-prod` — recreates containers with the new image.
  7. Verify: `docker compose ps`, `curl -fsSL https://meta.dmitry.work/api/health`.
- **Migrations:** `RUN_MIGRATIONS=1` is set in `docker-compose.yml`. On every `api` container start, `docker-entrypoint.sh` runs `alembic upgrade head` before the app process starts. Migrations run against the live database — see IRREVERSIBLE actions below.
- **Logs:** `just logs-api`, `just logs-watcher`, `just logs-mariadb` (docker compose stdout). No centralised log aggregation configured; retention is Docker's default JSON log driver (rotate as needed with `--log-opt max-size=10m --log-opt max-file=5` if desired).
- **Database:**
  - Engine: MariaDB 11, volume `mariadb_data`.
  - Reach from host: not exposed — connect via `docker exec -it ebook-meta-helper-mariadb-1 mariadb -u<DB_USER> -p<DB_PASSWORD> <DB_NAME>`.
  - Credentials: `DB_USER`, `DB_PASSWORD`, `DB_ROOT_PASSWORD`, `DB_NAME` from `.env` on the server (keep in 1Password or equivalent; never commit).
- **Access:** SSH to `<DEPLOY_USER>@<PROD_HOST_IP>`. No jump host currently documented; update this section when access method is confirmed.
- **Backup policy:** No automated backup configured yet. Manual backup: `docker run --rm -v ebook-meta-helper_mariadb_data:/data -v $(pwd):/backup alpine tar czf /backup/mariadb-$(date +%F).tar.gz /data`. Schedule via cron on the host. Target: daily, retain 7 days minimum.
- **Rollback:** Set `IMAGE_TAG` in `.env` to the previous pinned tag (or the previous `sha-<short>` tag from GHCR), then `just pull-prod && just up-prod`. Time-to-rollback: ~2 minutes (image pull + container restart). Database migrations applied on the previous run are **not** automatically reversed — see IRREVERSIBLE actions.
- **Common breakage modes:**
  - `web` Docker network missing → `docker compose up` fails with "network web declared as external, but could not be found". Fix: `docker network create web`.
  - Traefik stack not running → HTTPS traffic never reaches `api`; Traefik labels are ignored.
  - DNS A record for `meta.dmitry.work` not yet pointing at the server → Let's Encrypt HTTP-01 challenge fails; cert is not issued; HTTPS is unavailable.
  - `ACME_EMAIL` not set in the Traefik stack `.env` → Let's Encrypt registration fails.
  - `RUN_MIGRATIONS=1` + failed migration → api container exits at entrypoint; check `just logs-api`.
  - MariaDB volume permission errors after host path changes → recreate the volume (destructive).
- **IRREVERSIBLE actions:**
  - `alembic upgrade head` runs on every `api` container start (`RUN_MIGRATIONS=1`). Schema-changing migrations (column drops, renames, table drops) **cannot be automatically reversed**. Always back up `mariadb_data` before deploying a new image that contains a new migration. Manual downgrade: `docker exec -it <api-container> alembic downgrade -1` (must be scripted per migration; not always possible).
  - Dropping the `mariadb_data` Docker volume deletes all library metadata irreversibly.
  - Cutting the DNS A record for `meta.dmitry.work` to a new IP invalidates the current Let's Encrypt cert immediately (new cert issuance takes ~1 minute via HTTP-01 on the new IP).

---

## Update log

- 2026-06-05 — DMI-116: filled Local and Production sections; GHCR image delivery; shared Traefik topology documented; server-setup runbook in issue.
