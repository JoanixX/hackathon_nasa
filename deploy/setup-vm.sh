#!/usr/bin/env bash
# One-time setup of the production VM (Oracle Cloud Always Free, Ubuntu 22.04/24.04, arm64 or x86-64).
# Run as the default "ubuntu" user:  bash setup-vm.sh "<deploy public key>"
# Installs Docker Engine + Compose plugin, opens ports 80/443 in the OS firewall, prepares ~/ayumi and its .env,
# and authorises the GitHub Actions deploy key. Safe to run again.
set -euo pipefail

DEPLOY_PUBKEY="${1:-}"
APP_DIR="$HOME/ayumi"

echo "== Docker Engine and Compose plugin (official apt repository)"
if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl gnupg rsync
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
sudo usermod -aG docker "$USER" || true
sudo systemctl enable --now docker
command -v rsync >/dev/null || sudo apt-get install -y rsync

echo "== OS firewall: allow HTTP/HTTPS (Oracle Ubuntu images reject them by default)"
for port in 80 443; do
  sudo iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 6 -p tcp --dport "$port" -j ACCEPT
done
sudo iptables -C INPUT -p udp --dport 443 -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 6 -p udp --dport 443 -j ACCEPT
if command -v netfilter-persistent >/dev/null 2>&1; then sudo netfilter-persistent save; else
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent && sudo netfilter-persistent save; fi

echo "== Application folder and secrets file"
mkdir -p "$APP_DIR"
if [ ! -f "$APP_DIR/.env" ]; then
  cat > "$APP_DIR/.env" <<'EOF'
# Production secrets for www.ayumi.earth. Never commit this file. Edit with: nano ~/ayumi/.env
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.8-flash
RAIZ_AI_PROVIDER=gemini
RAIZ_AI_TIMEOUT_S=60
EARTHDATA_USERNAME=
EARTHDATA_PASSWORD=
RAIZ_MAX_QUEUE_DEPTH=20
RAIZ_JOB_LEASE_S=300
RAIZ_MAX_JOB_ATTEMPTS=3
EOF
  chmod 600 "$APP_DIR/.env"
  echo "Created $APP_DIR/.env (fill in the keys)."
fi

if [ -n "$DEPLOY_PUBKEY" ]; then
  echo "== Authorising the GitHub Actions deploy key"
  mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
  touch "$HOME/.ssh/authorized_keys" && chmod 600 "$HOME/.ssh/authorized_keys"
  grep -qF "$DEPLOY_PUBKEY" "$HOME/.ssh/authorized_keys" || echo "$DEPLOY_PUBKEY" >> "$HOME/.ssh/authorized_keys"
fi

echo "== Done. Log out and back in once so the docker group applies."
