#!/usr/bin/env bash
# One-time (and safely re-runnable) setup of a fresh Ubuntu 24.04 VPS for Saathi (ADR-0008).
#
# Run as root on the server:
#   curl -fsSL https://raw.githubusercontent.com/md-sahil-analyst22/chatbot-platform/main/scripts/vps/setup.sh -o setup.sh
#   sudo bash setup.sh yourdomain.com you@example.com
#
# What it does: system updates, firewall (22/80/443 only), fail2ban, automatic security updates,
# swap, Docker, nginx + certbot, a non-root "deploy" user (SSH keys only), the repo checkout,
# the nginx site, HTTPS (once DNS points here) and a GitHub Actions deploy key that can ONLY run
# the deploy script. It never deletes data and can be run again at any time.
set -euo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"
REPO_URL="https://github.com/md-sahil-analyst22/chatbot-platform.git"
DEPLOY_USER="deploy"
APP_DIR="/home/${DEPLOY_USER}/chatbot-platform"
WEB_DIR="/var/www/saathi-studio"

say()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33mWARNING: %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "run as root: sudo bash setup.sh <domain> <email>"
[[ "$DOMAIN" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$ ]] \
  || die "usage: sudo bash setup.sh yourdomain.com you@example.com   (domain in lowercase, no https://)"
[[ "$EMAIL" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]] \
  || die "give an email for Let's Encrypt expiry notices as the 2nd argument"
# shellcheck source=/dev/null  # system file, exists on the server only
. /etc/os-release
[[ "${ID:-}" == "ubuntu" ]] || die "this script supports Ubuntu (24.04 recommended); found ${ID:-unknown}"
[[ "${VERSION_ID:-}" == "24.04" ]] || warn "tested on Ubuntu 24.04; you have ${VERSION_ID:-unknown}"

export DEBIAN_FRONTEND=noninteractive

say "1/11 System updates and base packages"
apt-get update -q
apt-get -y -q upgrade
apt-get -y -q install ca-certificates curl git rsync ufw fail2ban unattended-upgrades \
  nginx certbot python3-certbot-nginx

say "2/11 Automatic security updates"
dpkg-reconfigure -f noninteractive unattended-upgrades
systemctl enable --now unattended-upgrades

say "3/11 Swap (helps small VPS plans survive Docker builds)"
if ! swapon --show | grep -q .; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo "2 GB swap created"
else
  echo "swap already present - skipped"
fi

say "4/11 Docker Engine (official repository)"
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

say "5/11 Deploy user '${DEPLOY_USER}' (SSH keys only)"
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

say "6/11 SSH hardening (only if a key login is guaranteed to keep working)"
# A personal login key line starts with its type; the restricted CI key line starts with "restrict,".
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

say "7/11 Firewall: allow only SSH, HTTP, HTTPS"
ufw allow OpenSSH >/dev/null
ufw allow 'Nginx Full' >/dev/null
ufw --force enable
ufw status verbose | sed -n '1,12p'
systemctl enable --now fail2ban   # Ubuntu enables the sshd jail by default

say "8/11 Code checkout at ${APP_DIR}"
if [[ ! -d "${APP_DIR}/.git" ]]; then
  sudo -u "$DEPLOY_USER" git clone --quiet "$REPO_URL" "$APP_DIR"
else
  sudo -u "$DEPLOY_USER" git -C "$APP_DIR" fetch --quiet --prune origin
fi
install -d -o "$DEPLOY_USER" -g "$DEPLOY_USER" -m 755 "$WEB_DIR"
[[ -f "${WEB_DIR}/index.html" ]] || echo "<!doctype html><title>Saathi</title><p>Bot Studio will appear after the first deploy.</p>" \
  | sudo -u "$DEPLOY_USER" tee "${WEB_DIR}/index.html" >/dev/null
if [[ ! -f "${APP_DIR}/.env" ]]; then
  warn "${APP_DIR}/.env does not exist yet - create it before the first deploy (runbook step 6)."
fi

say "9/11 nginx site for api.${DOMAIN} and app.${DOMAIN}"
sed "s/__DOMAIN__/${DOMAIN}/g" "${APP_DIR}/infra/nginx/saathi.conf.template" > /etc/nginx/sites-available/saathi.conf
ln -sf /etc/nginx/sites-available/saathi.conf /etc/nginx/sites-enabled/saathi.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

say "10/11 HTTPS certificates (Let's Encrypt)"
SERVER_IP="$(curl -fsS4 https://api.ipify.org || true)"
ready=1
for host in "api.${DOMAIN}" "app.${DOMAIN}"; do
  resolved="$(getent ahostsv4 "$host" | awk 'NR==1{print $1}')"
  if [[ -z "$resolved" || "$resolved" != "$SERVER_IP" ]]; then
    warn "${host} points to '${resolved:-nothing}', not this server (${SERVER_IP:-unknown})."
    ready=0
  fi
done
if [[ $ready -eq 1 ]]; then
  certbot --nginx --non-interactive --agree-tos -m "$EMAIL" --redirect \
    -d "api.${DOMAIN}" -d "app.${DOMAIN}"
  systemctl list-timers | grep -q certbot && echo "automatic renewal: active"
else
  warn "Skipped HTTPS. Add the DNS records (runbook step 3), wait ~10 minutes, then re-run this script."
fi

say "11/11 GitHub Actions deploy key (can ONLY run the deploy script)"
if ! grep -q 'gha-deploy' "$AUTH"; then
  tmp="$(mktemp -d)"
  ssh-keygen -q -t ed25519 -N "" -C "gha-deploy" -f "${tmp}/key"
  echo "restrict,command=\"${APP_DIR}/scripts/vps/deploy.sh\" $(cat "${tmp}/key.pub")" >> "$AUTH"
  echo
  echo "Copy EVERYTHING between the lines into the GitHub secret VPS_SSH_KEY (runbook step 8)."
  echo "It is shown once and then deleted from this server."
  echo "-----------------------------------------------------------------------"
  cat "${tmp}/key"
  echo "-----------------------------------------------------------------------"
  rm -rf "$tmp"
else
  echo "deploy key already installed - skipped (remove the 'gha-deploy' line in ${AUTH} to rotate it)"
fi
echo
echo "GitHub secret VPS_HOST:        ${SERVER_IP}"
echo "GitHub secret VPS_KNOWN_HOSTS: ${SERVER_IP} $(cut -d' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub)"

say "Done. Next: create ${APP_DIR}/.env (runbook step 6), then run the first deploy (step 7)."
