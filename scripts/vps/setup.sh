#!/usr/bin/env bash
# One-time (and safely re-runnable) setup of a fresh Ubuntu 24.04 VPS for Saathi (ADR-0008).
#
# Run as root on the server:
#   curl -fsSL https://raw.githubusercontent.com/md-sahil-analyst22/chatbot-platform/main/scripts/vps/setup.sh -o setup.sh
#   sudo bash setup.sh saathi.yourdomain.com
#
# The argument is the project's BASE address; the app is served at api.<base> and app.<base>
# (e.g. api.saathi.yourdomain.com), so one domain can host several projects.
#
# Built for Hostinger's n8n VPS template: the server's EXISTING Traefik (which also serves n8n)
# is the front door and issues HTTPS certificates. This script never stops, changes or
# restarts Traefik or n8n.
#
# What it does: system updates, firewall (22/80/443 only), fail2ban, automatic security updates,
# swap, Docker, a non-root "deploy" user (SSH keys only), the repo checkout, a check that Traefik
# is ready, and a DNS check. Releases are done by hand (runbook step 7); no CI system gets access
# to the server. It never deletes data and can be run again at any time.
set -euo pipefail

DOMAIN="${1:-}"
[[ -z "${2:-}" ]] || echo "note: the email argument is no longer needed (Traefik issues certificates) - ignored"
REPO_URL="https://github.com/md-sahil-analyst22/chatbot-platform.git"
DEPLOY_USER="deploy"
APP_DIR="/home/${DEPLOY_USER}/chatbot-platform"

say()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33mWARNING: %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "run as root: sudo bash setup.sh saathi.yourdomain.com"
[[ "$DOMAIN" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$ ]] \
  || die "usage: sudo bash setup.sh saathi.yourdomain.com   (base address, lowercase, no https://, no api./app.)"
[[ "$DOMAIN" != api.* && "$DOMAIN" != app.* ]] \
  || die "give the BASE address (e.g. saathi.yourdomain.com); the script adds api. and app. itself"
[[ "$DOMAIN" != *yourdomain.com && "$DOMAIN" != *example.com ]] \
  || die "'${DOMAIN}' is the guide's example - use YOUR real domain (e.g. saathi.mydomain.in)"
# shellcheck source=/dev/null  # system file, exists on the server only
. /etc/os-release
[[ "${ID:-}" == "ubuntu" ]] || die "this script supports Ubuntu (24.04 recommended); found ${ID:-unknown}"
[[ "${VERSION_ID:-}" == "24.04" ]] || warn "tested on Ubuntu 24.04; you have ${VERSION_ID:-unknown}"

export DEBIAN_FRONTEND=noninteractive

# When Docker was last (re)started. System updates below can restart Docker; a container that
# mounts /var/run/docker.sock (Traefik) then keeps a dead socket and stops seeing containers.
docker_started() { systemctl show docker -p ActiveEnterTimestampMonotonic --value 2>/dev/null || echo none; }
DOCKER_STARTED_BEFORE="$(docker_started)"

say "1/10 System updates and base packages"
apt-get update -q
apt-get -y -q upgrade
apt-get -y -q install ca-certificates curl git ufw fail2ban unattended-upgrades

say "2/10 Automatic security updates"
dpkg-reconfigure -f noninteractive unattended-upgrades
systemctl enable --now unattended-upgrades

say "3/10 Swap (helps small VPS plans survive Docker builds)"
if ! swapon --show | grep -q .; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo "2 GB swap created"
else
  echo "swap already present - skipped"
fi

say "4/10 Docker Engine (official repository)"
if ! command -v docker >/dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get -y -q install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
docker compose version

say "5/10 Deploy user '${DEPLOY_USER}' (SSH keys only)"
id "$DEPLOY_USER" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "$DEPLOY_USER"
usermod -aG docker "$DEPLOY_USER"   # note: docker access is root-equivalent; protect its keys
install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "/home/${DEPLOY_USER}/.ssh"
AUTH="/home/${DEPLOY_USER}/.ssh/authorized_keys"
touch "$AUTH"
# Give the deploy user the same key(s) you use for root (Hostinger adds yours at purchase).
if [[ -s /root/.ssh/authorized_keys ]]; then
  while IFS= read -r line; do
    [[ -z "$line" || "$line" == \#* ]] && continue
    grep -qxF "$line" "$AUTH" || echo "$line" >> "$AUTH"
  done < /root/.ssh/authorized_keys
fi
chown "$DEPLOY_USER:$DEPLOY_USER" "$AUTH" && chmod 600 "$AUTH"

say "6/10 SSH hardening (only if a key login is guaranteed to keep working)"
if grep -qE '^(ssh-(ed25519|rsa)|ecdsa-sha2-)' "$AUTH"; then
  cat > /etc/ssh/sshd_config.d/99-saathi-hardening.conf <<'SSHD'
# Managed by scripts/vps/setup.sh (ADR-0008)
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
SSHD
  sshd -t && systemctl reload ssh
  echo "password and root logins disabled - log in as: ssh ${DEPLOY_USER}@<server-ip>"
else
  warn "no SSH key found for ${DEPLOY_USER}: password/root login left ON so you don't get locked out."
  warn "Add your public key to ${AUTH}, then re-run this script."
fi

say "7/10 Firewall: allow only SSH, HTTP, HTTPS"
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null    # Traefik: HTTP (redirects to HTTPS) + certificate challenges
ufw allow 443/tcp >/dev/null   # Traefik: HTTPS
ufw --force enable
ufw status verbose | sed -n '1,12p'
systemctl enable --now fail2ban   # Ubuntu enables the sshd jail by default

say "8/10 Code checkout at ${APP_DIR}"
if [[ ! -d "${APP_DIR}/.git" ]]; then
  sudo -u "$DEPLOY_USER" git clone --quiet "$REPO_URL" "$APP_DIR"
else
  sudo -u "$DEPLOY_USER" git -C "$APP_DIR" fetch --quiet --prune origin
fi
# Short command for releases: `saathi down`, `saathi up -d --build`, `saathi ps`, `saathi logs -f api`.
ALIAS_LINE="alias saathi='docker compose --env-file ${APP_DIR}/.env -f ${APP_DIR}/infra/docker-compose.prod.yml'"
grep -qxF "$ALIAS_LINE" "/home/${DEPLOY_USER}/.bashrc" || echo "$ALIAS_LINE" >> "/home/${DEPLOY_USER}/.bashrc"
if [[ ! -f "${APP_DIR}/.env" ]]; then
  warn "${APP_DIR}/.env does not exist yet - create it before the first deploy (runbook step 6)."
fi

say "9/10 Front door: the existing Traefik"
# An earlier version of this script installed host nginx + certbot. On a Traefik server nginx
# can't bind 80/443, so it has never served anything: remove it (only if it isn't running).
if dpkg -s nginx >/dev/null 2>&1 && ! systemctl is-active --quiet nginx; then
  systemctl disable --now nginx >/dev/null 2>&1 || true
  apt-get -y -q purge nginx nginx-common certbot python3-certbot-nginx >/dev/null
  apt-get -y -q autoremove >/dev/null
  echo "removed the unused host nginx/certbot left by an earlier version of this script"
fi
TRAEFIK="$(docker ps --format '{{.Names}} {{.Image}}' | awk '$2 ~ /traefik/ {print $1; exit}')"
[[ -n "$TRAEFIK" ]] || die "no running Traefik container found. This setup expects Hostinger's n8n VPS template (Traefik + n8n). Tell your developer what runs on ports 80/443: ss -ltnp | grep -E ':(80|443) '"
TRAEFIK_CMD="$(docker inspect "$TRAEFIK" --format '{{json .Config.Cmd}}')"
for needed in "providers.docker=true" "entrypoints.websecure.address=:443" "certificatesresolvers.letsencrypt"; do
  [[ "$TRAEFIK_CMD" == *"$needed"* ]] || die "Traefik (${TRAEFIK}) is missing '${needed}', which Saathi's routing labels rely on"
done
# Reconnect Traefik to Docker if Docker restarted during this run (e.g. a Docker package update),
# or if Traefik already lost it. Symptom otherwise: every site, n8n included, answers
# "404 page not found" with Traefik's default certificate. Restart takes ~5 s.
if [[ "$(docker_started)" != "$DOCKER_STARTED_BEFORE" ]] \
   || docker logs --since 15m "$TRAEFIK" 2>&1 | grep -q "Cannot connect to the Docker daemon"; then
  echo "Docker was restarted (or Traefik lost its Docker connection): restarting ${TRAEFIK} (~5 s; n8n blinks)"
  docker restart "$TRAEFIK" >/dev/null
  sleep 8
  if docker logs --since 8s "$TRAEFIK" 2>&1 | grep -q "Cannot connect to the Docker daemon"; then
    warn "Traefik still can't reach Docker. Check: docker logs --tail 20 ${TRAEFIK}"
  else
    echo "Traefik reconnected to Docker"
  fi
fi
echo "Traefik '${TRAEFIK}' is ready: Docker provider, websecure entrypoint, letsencrypt certificates"

say "10/10 DNS check for api.${DOMAIN} and app.${DOMAIN}"
SERVER_IP="$(curl -fsS4 https://api.ipify.org || true)"
for host in "api.${DOMAIN}" "app.${DOMAIN}"; do
  resolved="$(getent ahostsv4 "$host" | awk 'NR==1{print $1}')"
  if [[ -n "$resolved" && "$resolved" == "$SERVER_IP" ]]; then
    echo "${host} -> ${resolved} (this server)"
  else
    warn "${host} points to '${resolved:-nothing}', not this server (${SERVER_IP:-unknown}). Fix the DNS record (runbook step 2); HTTPS works once it points here."
  fi
done

say "Done. Next: create ${APP_DIR}/.env with SAATHI_BASE_DOMAIN=${DOMAIN} (runbook step 6), then release (step 7):"
echo "  ssh ${DEPLOY_USER}@<server-ip>, then: cd ~/chatbot-platform && saathi up -d --build"
