#!/usr/bin/env bash
# Deploy a commit to the VPS (ADR-0008). Runs as the "deploy" user on the server.
#
#   ./scripts/vps/deploy.sh <commit-sha>     deploy that commit (rollback = an older sha)
#   ./scripts/vps/deploy.sh main             deploy the latest main
#
# GitHub Actions calls it through a restricted SSH key whose only allowed command is this script;
# the commit then arrives in SSH_ORIGINAL_COMMAND.
#
# Order matters (R25): build -> migrate -> restart -> health check -> publish Bot Studio.
# If the build or the migration fails, the running version keeps serving traffic.
set -euo pipefail

APP_DIR="/home/deploy/chatbot-platform"
WEB_DIR="/var/www/saathi-studio"
COMPOSE=(docker compose --env-file .env -f infra/docker-compose.prod.yml)

log() { printf '[deploy %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
die() { printf '[deploy] ERROR: %s\n' "$*" >&2; exit 1; }

TARGET="${1:-${SSH_ORIGINAL_COMMAND:-}}"
# Only a commit id or "main": never pass an arbitrary string to git or the shell.
[[ "$TARGET" =~ ^([0-9a-f]{7,40}|main)$ ]] || die "usage: deploy.sh <commit-sha>|main (got '${TARGET}')"

cd "$APP_DIR"
exec 9>"${APP_DIR}/.deploy.lock"
flock -n 9 || die "another deploy is running"

[[ -f .env ]] || die ".env missing in ${APP_DIR} (runbook step 6)"
[[ "$(stat -c %a .env)" == "600" ]] || die ".env must be private: chmod 600 ${APP_DIR}/.env"
env_value() { grep -E "^$1=" .env | tail -1 | cut -d= -f2- | sed -e "s/^['\"]//" -e "s/['\"]$//"; }
STUDIO_API_BASE_URL="$(env_value STUDIO_API_BASE_URL)"
[[ "$STUDIO_API_BASE_URL" =~ ^https://[a-z0-9.-]+$ ]] \
  || die "set STUDIO_API_BASE_URL=https://api.yourdomain.com in .env (no trailing slash)"

log "fetching ${TARGET}"
git fetch --quiet --prune origin
[[ "$TARGET" == "main" ]] && TARGET="$(git rev-parse origin/main)"
git checkout --quiet --detach "$TARGET"
SHA="$(git rev-parse --short HEAD)"
log "deploying ${SHA}: $(git log -1 --format=%s)"

log "building backend image"
"${COMPOSE[@]}" build --pull api

log "running database migrations (before the new code serves traffic)"
"${COMPOSE[@]}" --profile tools run --rm migrate

log "starting redis, api, worker"
"${COMPOSE[@]}" up -d --remove-orphans redis api worker

log "waiting for the API to report healthy"
for _ in $(seq 1 30); do
  if curl -fsS --max-time 3 http://127.0.0.1:8000/health >/dev/null; then
    healthy=1; break
  fi
  sleep 2
done
if [[ "${healthy:-0}" != 1 ]]; then
  "${COMPOSE[@]}" logs --tail 80 api >&2 || true
  die "API not healthy after 60 s. Roll back with: ./scripts/vps/deploy.sh <previous-sha>"
fi

log "building Bot Studio for ${STUDIO_API_BASE_URL}"
# Built in a throwaway Node container: no Node on the host, same version as CI (24 LTS).
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -e VITE_API_BASE_URL="$STUDIO_API_BASE_URL" \
  -v "${APP_DIR}/dashboard:/app" -w /app node:24-alpine \
  sh -c "npm ci --no-fund --no-audit && npm run build"
rsync -a --delete "${APP_DIR}/dashboard/dist/" "${WEB_DIR}/"

docker image prune -f >/dev/null
log "done: ${SHA} is live (api: http://127.0.0.1:8000/health, studio: ${WEB_DIR})"
