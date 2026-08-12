#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "No .env found. Creating from .env.example..."
  cp .env.example .env
  echo
  echo "!!! STOP — edit .env first !!!"
  echo "  1. PORTAL_FILES_PATH   = the dataset folder filebrowser serves"
  echo "  2. PORTAL_DATA_PATH    = a small persistent folder for the portal DB"
  echo "  3. PORTAL_ADMIN_PASSWORD = your admin password"
  echo "Then run this script again."
  exit 1
fi

echo "Using configuration from .env:"
set -a; source .env; set +a
echo "  files:   $PORTAL_FILES_PATH"
echo "  data:    $PORTAL_DATA_PATH"
echo "  port:    ${PORTAL_PORT:-8080}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker CLI is not available."
  echo "Enable it in TrueNAS: System Settings -> Advanced -> 'Allow Docker command line interface'"
  echo "(or run: midclt call system.advanced.update '{\"allow_docker_cli\": true}')"
  exit 1
fi

mkdir -p "$PORTAL_DATA_PATH" 2>/dev/null || true

docker compose up -d --build || docker-compose up -d --build

sleep 3
echo
echo "--- container status ---"
docker compose ps 2>/dev/null || docker-compose ps 2>/dev/null || true
echo
echo "Portal admin:  http://<this-nas-ip>:${PORTAL_PORT:-8080}/admin"
