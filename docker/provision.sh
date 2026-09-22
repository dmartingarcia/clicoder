#!/usr/bin/env bash
set -euo pipefail

REPO_URL="git@github.com:dmartingarcia/CIE-10.git"  # SSH, requiere clave en GitHub
REPO_DIR="/home/app/CIE-10"
SSH_KEY="/home/app/.ssh/id_ed25519"

# Crear usuario app
if ! id app &>/dev/null; then
  useradd -m -s /bin/bash app
fi

# SSH key
if [ ! -f "$SSH_KEY" ]; then
  sudo -u app ssh-keygen -t ed25519 -C "app@$(hostname)" -N "" -f "$SSH_KEY"
fi
echo ""
echo "Añade esta clave pública a GitHub antes de continuar:"
cat "${SSH_KEY}.pub"
echo ""
read -rp "Pulsa Enter cuando hayas añadido la clave a GitHub..."

# Docker
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
usermod -aG docker app

# Emacs
if ! command -v emacs &>/dev/null; then
  apt-get update -q && apt-get install -y emacs
fi

# Repo
mkdir -p "$(dirname "$REPO_DIR")"
if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" pull --ff-only
else
  sudo -u app git clone "$REPO_URL" "$REPO_DIR"
fi

if [ ! -f "$REPO_DIR/.env" ]; then
  cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
  echo "Edita $REPO_DIR/.env antes de arrancar los servicios"
fi

# Fail2ban: protección SSH + brute force HTTP vía logs de Traefik
if ! command -v fail2ban-client &>/dev/null; then
  apt-get update -q && apt-get install -y fail2ban
fi

mkdir -p /var/log/traefik
touch /var/log/traefik/access.log
mkdir -p /etc/fail2ban/filter.d

cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime  = 1h
findtime = 10m
maxretry = 5
banaction = iptables-multiport
ignoreip  = 127.0.0.1/8 ::1

# SSH: 3 intentos fallidos → ban 24h
[sshd]
enabled  = true
port     = ssh
filter   = sshd
logpath  = /var/log/auth.log
maxretry = 3
bantime  = 24h

# Traefik: 10 respuestas 401 en 5 min → ban 1h
# Cubre login de backend (Phoenix) y dashboard de Traefik
[traefik-auth]
enabled  = true
port     = http,https
filter   = traefik-auth
logpath  = /var/log/traefik/access.log
maxretry = 10
bantime  = 1h
findtime = 5m
EOF

# Traefik escribe access logs en JSON: extraemos ClientHost de cada 401
cat > /etc/fail2ban/filter.d/traefik-auth.conf << 'EOF'
[Definition]
failregex = ^.*"ClientHost":"<HOST>".*"DownstreamStatus":401.*$
ignoreregex =
EOF

systemctl enable fail2ban
systemctl restart fail2ban
echo "Fail2ban activo. Estado: $(fail2ban-client status)"
