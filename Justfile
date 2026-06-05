import '.claude/Justfile'

# List available recipes (default when `just` is invoked without arguments)
default:
    @just --list

# -----------------------------------------------------------------------------
# Local dev (Windows / Docker Desktop)
# -----------------------------------------------------------------------------
# Layers docker-compose.local.yml on top of the production base:
#   - drops Traefik labels
#   - publishes api on 127.0.0.1:${API_PORT:-8000}
#   - publishes mariadb on 127.0.0.1:${DB_PORT:-3306}
up-local:
    docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build

down-local:
    docker compose -f docker-compose.yml -f docker-compose.local.yml down

# -----------------------------------------------------------------------------
# Production (Linux host running Traefik)
# -----------------------------------------------------------------------------
# Uses docker-compose.yml only. The external `web` network must already exist
# on the host (created by the Traefik stack) — see environments.md.
# IMAGE_TAG defaults to `latest`; pin a specific tag for a controlled deploy:
#   IMAGE_TAG=sha-abc1234 just up-prod
pull-prod:
    docker compose pull

up-prod:
    docker compose up -d

down-prod:
    docker compose down

# -----------------------------------------------------------------------------
# Logs (works for both local and prod — compose picks the active project)
# -----------------------------------------------------------------------------
logs-api:
    docker compose logs -f api

logs-watcher:
    docker compose logs -f watcher

logs-mariadb:
    docker compose logs -f mariadb
