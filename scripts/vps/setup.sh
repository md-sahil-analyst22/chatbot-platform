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

# The first argument: the base domain (empty if not given).
DOMAIN="${1:-}"
# A second argument (an email) was needed by old versions; now it's ignored with a note.
[[ -z "${2:-}" ]] || echo "note: the email argument is no longer needed (Traefik issues certificates) - ignored"
# Where the code is downloaded from.
REPO_URL="https://github.com/md-sahil-analyst22/chatbot-platform.git"
# The non-root user that runs the app.
DEPLOY_USER="deploy"
# Where the code lives on the server.
APP_DIR="/home/${DEPLOY_USER}/chatbot-platform"

# say: print a blue step heading.
say()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
# warn: print a yellow warning.
warn() { printf '\033[1;33mWARNING: %s\033[0m\n' "$*"; }
# die: print a red error and stop the script.
die()  { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# Must run as root (user id 0), otherwise stop.
[[ $EUID -eq 0 ]] || die "run as root: sudo bash setup.sh saathi.yourdomain.com"
# The domain must look like a real lowercase domain, otherwise stop:
[[ "$DOMAIN" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$ ]] \
  || die "usage: sudo bash setup.sh saathi.yourdomain.com   (base address, lowercase, no https://, no api./app.)"
# It must be the BASE domain, not api.<...> or app.<...>:
[[ "$DOMAIN" != api.* && "$DOMAIN" != app.* ]] \
  || die "give the BASE address (e.g. saathi.yourdomain.com); the script adds api. and app. itself"
# It must not be the example domain from the guide:
[[ "$DOMAIN" != *yourdomain.com && "$DOMAIN" != *example.com ]] \
  || die "'${DOMAIN}' is the guide's example - use YOUR real domain (e.g. saathi.mydomain.in)"
# shellcheck source=/dev/null  # system file, exists on the server only
. /etc/os-release
# Only Ubuntu is supported...
[[ "${ID:-}" == "ubuntu" ]] || die "this script supports Ubuntu (24.04 recommended); found ${ID:-unknown}"
# ...and 24.04 is the tested version (others just get a warning).
[[ "${VERSION_ID:-}" == "24.04" ]] || warn "tested on Ubuntu 24.04; you have ${VERSION_ID:-unknown}"

# Make apt never stop to ask questions.
export DEBIAN_FRONTEND=noninteractive

# When Docker was last (re)started. System updates below can restart Docker; a container that
# mounts /var/run/docker.sock (Traefik) then keeps a dead socket and stops seeing containers.
docker_started() { systemctl show docker -p ActiveEnterTimestampMonotonic --value 2>/dev/null || echo none; }
# Remember when Docker last started, to spot a restart later.
DOCKER_STARTED_BEFORE="$(docker_started)"

# Step 1:
say "1/10 System updates and base packages"
# refresh the package lists,
apt-get update -q
# install all updates,
apt-get -y -q upgrade
# and install the tools this script needs (certificates, curl, git, firewall, fail2ban,
#   auto-updates).
apt-get -y -q install ca-certificates curl git ufw fail2ban unattended-upgrades

# Step 2:
say "2/10 Automatic security updates"
# switch on automatic security updates,
dpkg-reconfigure -f noninteractive unattended-upgrades
# and start that service now and at every boot.
systemctl enable --now unattended-upgrades

# Step 3:
say "3/10 Swap (helps small VPS plans survive Docker builds)"
# If there's no swap yet:
if ! swapon --show | grep -q .; then
  # create a 2 GB swap file, lock it down and switch it on,
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  # make it permanent (unless already listed in /etc/fstab),
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  # and say so.
  echo "2 GB swap created"
else
  # Otherwise say it was skipped.
  echo "swap already present - skipped"
fi

# Step 4:
say "4/10 Docker Engine (official repository)"
# If Docker isn't installed yet:
if ! command -v docker >/dev/null; then
  # create the folder for package-signing keys,
  install -m 0755 -d /etc/apt/keyrings
  # download Docker's signing key,
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  # let apt read it,
  chmod a+r /etc/apt/keyrings/docker.asc
  # add Docker's official package source:
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  # refresh the package lists,
  apt-get update -q
  # and install Docker Engine plus the build and compose plugins.
  apt-get -y -q install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
# Start Docker now and at every boot.
systemctl enable --now docker
# Show the Compose version (proves it works).
docker compose version

# Step 5:
say "5/10 Deploy user '${DEPLOY_USER}' (SSH keys only)"
# Create the deploy user (no password; SSH keys only) unless it exists.
id "$DEPLOY_USER" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "$DEPLOY_USER"
usermod -aG docker "$DEPLOY_USER"   # note: docker access is root-equivalent; protect its keys
# Create its private .ssh folder.
install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "/home/${DEPLOY_USER}/.ssh"
# Its list of allowed SSH keys.
AUTH="/home/${DEPLOY_USER}/.ssh/authorized_keys"
# Make sure that file exists.
touch "$AUTH"
# Give the deploy user the same key(s) you use for root (Hostinger adds yours at purchase).
if [[ -s /root/.ssh/authorized_keys ]]; then
  # For each line of root's allowed keys:
  while IFS= read -r line; do
    # skip blank lines and comments,
    [[ -z "$line" || "$line" == \#* ]] && continue
    # add the key unless it's already there.
    grep -qxF "$line" "$AUTH" || echo "$line" >> "$AUTH"
  done < /root/.ssh/authorized_keys
fi
# The file must belong to the deploy user and be private.
chown "$DEPLOY_USER:$DEPLOY_USER" "$AUTH" && chmod 600 "$AUTH"

# Step 6:
say "6/10 SSH hardening (only if a key login is guaranteed to keep working)"
# Only if the deploy user has at least one real SSH key:
if grep -qE '^(ssh-(ed25519|rsa)|ecdsa-sha2-)' "$AUTH"; then
  # write an SSH config that turns off password and root logins:
  cat > /etc/ssh/sshd_config.d/99-saathi-hardening.conf <<'SSHD'
# Managed by scripts/vps/setup.sh (ADR-0008)
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
SSHD
  # check the SSH config is valid, then reload SSH,
  sshd -t && systemctl reload ssh
  # and say how to log in from now on.
  echo "password and root logins disabled - log in as: ssh ${DEPLOY_USER}@<server-ip>"
else
  # Otherwise warn that password/root login stays on...
  warn "no SSH key found for ${DEPLOY_USER}: password/root login left ON so you don't get locked out."
  # ...and how to fix it.
  warn "Add your public key to ${AUTH}, then re-run this script."
fi

# Step 7:
say "7/10 Firewall: allow only SSH, HTTP, HTTPS"
# allow SSH,
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null    # Traefik: HTTP (redirects to HTTPS) + certificate challenges
ufw allow 443/tcp >/dev/null   # Traefik: HTTPS
# switch the firewall on (without asking),
ufw --force enable
# and show the first lines of its status.
ufw status verbose | sed -n '1,12p'
systemctl enable --now fail2ban   # Ubuntu enables the sshd jail by default

# Step 8:
say "8/10 Code checkout at ${APP_DIR}"
# If the code isn't there yet:
if [[ ! -d "${APP_DIR}/.git" ]]; then
  # download it as the deploy user.
  sudo -u "$DEPLOY_USER" git clone --quiet "$REPO_URL" "$APP_DIR"
else
  # Otherwise fetch the latest changes (the release itself is done by hand).
  sudo -u "$DEPLOY_USER" git -C "$APP_DIR" fetch --quiet --prune origin
fi
# Short command for releases: `saathi down`, `saathi up -d --build`, `saathi ps`, `saathi logs -f api`.
ALIAS_LINE="alias saathi='docker compose --env-file ${APP_DIR}/.env -f ${APP_DIR}/infra/docker-compose.prod.yml'"
# Add the 'saathi' shortcut to the deploy user's shell, unless it's there already.
grep -qxF "$ALIAS_LINE" "/home/${DEPLOY_USER}/.bashrc" || echo "$ALIAS_LINE" >> "/home/${DEPLOY_USER}/.bashrc"
# If the .env settings file doesn't exist yet:
if [[ ! -f "${APP_DIR}/.env" ]]; then
  # remind to create it before the first release.
  warn "${APP_DIR}/.env does not exist yet - create it before the first deploy (runbook step 6)."
fi

# Step 9:
say "9/10 Front door: the existing Traefik"
# An earlier version of this script installed host nginx + certbot. On a Traefik server nginx
# can't bind 80/443, so it has never served anything: remove it (only if it isn't running).
if dpkg -s nginx >/dev/null 2>&1 && ! systemctl is-active --quiet nginx; then
  # stop and disable it,
  systemctl disable --now nginx >/dev/null 2>&1 || true
  # remove it and certbot,
  apt-get -y -q purge nginx nginx-common certbot python3-certbot-nginx >/dev/null
  # clean up leftover packages,
  apt-get -y -q autoremove >/dev/null
  # and say so.
  echo "removed the unused host nginx/certbot left by an earlier version of this script"
fi
# Find the running Traefik container's name.
TRAEFIK="$(docker ps --format '{{.Names}} {{.Image}}' | awk '$2 ~ /traefik/ {print $1; exit}')"
# None running: stop with an explanation (this setup needs the n8n template's Traefik).
[[ -n "$TRAEFIK" ]] || die "no running Traefik container found. This setup expects Hostinger's n8n VPS template (Traefik + n8n). Tell your developer what runs on ports 80/443: ss -ltnp | grep -E ':(80|443) '"
# Read the settings Traefik was started with.
TRAEFIK_CMD="$(docker inspect "$TRAEFIK" --format '{{json .Config.Cmd}}')"
# Check each setting our routing needs:
for needed in "providers.docker=true" "entrypoints.websecure.address=:443" "certificatesresolvers.letsencrypt"; do
  # missing -> stop and name it.
  [[ "$TRAEFIK_CMD" == *"$needed"* ]] || die "Traefik (${TRAEFIK}) is missing '${needed}', which Saathi's routing labels rely on"
done
# Reconnect Traefik to Docker if Docker restarted during this run (e.g. a Docker package update),
# or if Traefik already lost it. Symptom otherwise: every site, n8n included, answers
# "404 page not found" with Traefik's default certificate. Restart takes ~5 s.
if [[ "$(docker_started)" != "$DOCKER_STARTED_BEFORE" ]] \
   || docker logs --since 15m "$TRAEFIK" 2>&1 | grep -q "Cannot connect to the Docker daemon"; then
  # say why we're restarting Traefik,
  echo "Docker was restarted (or Traefik lost its Docker connection): restarting ${TRAEFIK} (~5 s; n8n blinks)"
  # restart it (n8n blinks for a few seconds),
  docker restart "$TRAEFIK" >/dev/null
  # give it 8 seconds,
  sleep 8
  # and if it still can't reach Docker...
  if docker logs --since 8s "$TRAEFIK" 2>&1 | grep -q "Cannot connect to the Docker daemon"; then
    # ...warn with the command to investigate.
    warn "Traefik still can't reach Docker. Check: docker logs --tail 20 ${TRAEFIK}"
  else
    # Otherwise confirm it reconnected.
    echo "Traefik reconnected to Docker"
  fi
fi
# Traefik is ready.
echo "Traefik '${TRAEFIK}' is ready: Docker provider, websecure entrypoint, letsencrypt certificates"

# Step 10:
say "10/10 DNS check for api.${DOMAIN} and app.${DOMAIN}"
# This server's public IP address (empty if the lookup fails).
SERVER_IP="$(curl -fsS4 https://api.ipify.org || true)"
# For each of the two addresses:
for host in "api.${DOMAIN}" "app.${DOMAIN}"; do
  # look up the IP it points to,
  resolved="$(getent ahostsv4 "$host" | awk 'NR==1{print $1}')"
  # if it points to this server...
  if [[ -n "$resolved" && "$resolved" == "$SERVER_IP" ]]; then
    # ...say so,
    echo "${host} -> ${resolved} (this server)"
  else
    # otherwise warn and explain how to fix the DNS record.
    warn "${host} points to '${resolved:-nothing}', not this server (${SERVER_IP:-unknown}). Fix the DNS record (runbook step 2); HTTPS works once it points here."
  fi
done

# Finished: print the next steps...
say "Done. Next: create ${APP_DIR}/.env with SAATHI_BASE_DOMAIN=${DOMAIN} (runbook step 6), then release (step 7):"
# ...including the release command.
echo "  ssh ${DEPLOY_USER}@<server-ip>, then: cd ~/chatbot-platform && saathi up -d --build"
