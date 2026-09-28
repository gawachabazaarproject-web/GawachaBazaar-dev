#!/usr/bin/env bash
# One-time setup of a fresh Contabo VPS (Ubuntu 22.04 / 24.04) for
# Gawacha Bazaar. Run as root:
#
#   curl -fsSL <raw url of this file> -o bootstrap-server.sh   # or scp it
#   bash bootstrap-server.sh <deploy-username>
#
# Installs Docker Engine + compose plugin from Docker's official apt repo,
# enables a firewall (SSH/80/443 only), unattended security upgrades,
# fail2ban for SSH, a swap file, and a non-root deploy user in the docker
# group. It deliberately does NOT disable SSH password login - do that
# yourself only after confirming key-based login works for the deploy
# user, or you can lock yourself out (see deploy/README.md).
set -euo pipefail

DEPLOY_USER="${1:?usage: bootstrap-server.sh <deploy-username>}"
SWAP_SIZE="${SWAP_SIZE:-4G}"

[ "$(id -u)" -eq 0 ] || { echo "Run as root." >&2; exit 1; }

echo "==> System update"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y
apt-get install -y ca-certificates curl gnupg git ufw fail2ban unattended-upgrades

echo "==> Docker Engine (official repo)"
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
	> /etc/apt/sources.list.d/docker.list
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

echo "==> Deploy user: $DEPLOY_USER"
if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
	adduser --disabled-password --gecos "" "$DEPLOY_USER"
fi
usermod -aG docker "$DEPLOY_USER"
if [ -f /root/.ssh/authorized_keys ] && [ ! -f "/home/$DEPLOY_USER/.ssh/authorized_keys" ]; then
	install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "/home/$DEPLOY_USER/.ssh"
	install -m 600 -o "$DEPLOY_USER" -g "$DEPLOY_USER" /root/.ssh/authorized_keys "/home/$DEPLOY_USER/.ssh/authorized_keys"
fi
install -d -o "$DEPLOY_USER" -g "$DEPLOY_USER" /opt/gawachabazaar

echo "==> Firewall (SSH, HTTP, HTTPS, HTTP/3)"
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable
# Note: Docker-published ports bypass ufw. Only Caddy publishes ports in
# docker-compose.prod.yml (80/443), which is exactly what's allowed here -
# never add `ports:` to db/backend.

echo "==> fail2ban (sshd)"
cat > /etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled = true
maxretry = 5
bantime = 1h
EOF
systemctl enable --now fail2ban
systemctl restart fail2ban

echo "==> Unattended security upgrades"
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "==> Swap ($SWAP_SIZE)"
if ! swapon --show | grep -q .; then
	fallocate -l "$SWAP_SIZE" /swapfile
	chmod 600 /swapfile
	mkswap /swapfile
	swapon /swapfile
	echo '/swapfile none swap sw 0 0' >> /etc/fstab
	sysctl -w vm.swappiness=10
	echo 'vm.swappiness=10' > /etc/sysctl.d/99-swappiness.conf
fi

echo "==> Docker log rotation defaults"
cat > /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "5" }
}
EOF
systemctl restart docker

echo
echo "Done. Next, as $DEPLOY_USER:"
echo "  git clone <repo> /opt/gawachabazaar && cd /opt/gawachabazaar"
echo "  cp .env.production.example .env.production && chmod 600 .env.production && nano .env.production"
echo "  deploy/scripts/deploy.sh"
