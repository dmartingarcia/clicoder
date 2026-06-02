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
sudo -u app newgrp docker

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
