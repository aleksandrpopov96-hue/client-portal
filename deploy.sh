#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "No .env found. Creating from .env.example..."
  cp .env.example .env
  echo
  echo "!!! STOP - edit .env first !!!"
  echo "  1. PORTAL_FILES_PATH     = the SMB dataset folder the portal serves"
  echo "  2. PORTAL_DATA_PATH      = a small persistent folder for the portal DB"
  echo "  3. PUID/PGID             = the numeric owner (uid:gid) of those folders"
  echo "                              (check with:  ls -dn <path>)"
  echo "  4. PORTAL_ADMIN_PASSWORD = your admin password"
  echo "  Optionally set CLOUDFLARED_TOKEN and uncomment the tunnel service."
  echo "Then run this script again."
  exit 1
fi

echo "Using configuration from .env:"
set -a; source .env; set +a
PORTAL_FILES_PATH="${PORTAL_FILES_PATH:-}"
PORTAL_DATA_PATH="${PORTAL_DATA_PATH:-}"
if [ -z "$PORTAL_FILES_PATH" ]; then
  echo "ERROR: PORTAL_FILES_PATH is not set in .env."
  grep -n "PORTAL_FILES_PATH" .env 2>/dev/null || true
  echo "Make sure the line is present and NOT commented out, e.g.:"
  echo "  PORTAL_FILES_PATH=/mnt"
  exit 1
fi
if [ -z "$PORTAL_DATA_PATH" ]; then
  echo "ERROR: PORTAL_DATA_PATH is not set in .env (e.g. PORTAL_DATA_PATH=/mnt/NormalusNAS/portal-data)."
  exit 1
fi
echo "  files:   $PORTAL_FILES_PATH"
echo "  data:    $PORTAL_DATA_PATH"
echo "  uid:gid: ${PUID:-3000}:${PGID:-3000}"
echo "  port:    ${PORTAL_PORT:-8080}"
if [ -n "${CLOUDFLARED_TOKEN:-}" ]; then
  echo "  tunnel:  enabled (Cloudflare token set)"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker CLI is not available."
  echo "Enable it in TrueNAS: System Settings -> Advanced -> 'Allow Docker command line interface'"
  echo "(or run: midclt call system.advanced.update '{\"allow_docker_cli\": true}')"
  exit 1
fi

PUID="${PUID:-3000}"
PGID="${PGID:-3000}"

# Sanity-check the files path exists (your storage root - /mnt to browse the whole NAS).
if [ ! -d "$PORTAL_FILES_PATH" ]; then
  echo "ERROR: PORTAL_FILES_PATH '$PORTAL_FILES_PATH' does not exist."
  echo "It must be a mounted path on this host - e.g. /mnt (whole NAS) or a dataset"
  echo "such as /mnt/NormalusNAS/SUBKINAS. Fix .env, then run this script again."
  exit 1
fi

echo
echo "Making sure mount points exist and are owned by $PUID:$PGID ..."
mkdir -p "$PORTAL_FILES_PATH" "$PORTAL_DATA_PATH"
if command -v chown >/dev/null 2>&1; then
  # Only the top-level dirs are chowned - never recursively touch the dataset,
  # that would clobber existing SMB permissions on files already in it.
  chown "$PUID:$PGID" "$PORTAL_FILES_PATH" "$PORTAL_DATA_PATH" 2>/dev/null \
    && echo "Ownership set to $PUID:$PGID." \
    || echo "WARNING: could not chown (running as non-root). Check Dataset Permissions in the TrueNAS UI."
fi

echo
echo "Building and starting containers (this takes a few minutes the first time)..."
docker compose up -d --build

# Verify the container can actually write into the served dataset (this is the
# whole point of the PUID/PGID setup).
sleep 3
if docker exec client-portal sh -c 'touch /data/files/.portal-write-test && rm -f /data/files/.portal-write-test'; then
  echo
  echo "OK - the portal can read and write '$PORTAL_FILES_PATH'."
else
  echo
  echo "WARNING: the container cannot write to '$PORTAL_FILES_PATH'."
  echo "Give that dataset rwx permission for uid:gid $PUID:$PGID in the TrueNAS UI"
  echo "(Storage -> Datasets -> Edit Permissions), then run:  docker compose up -d"
fi

echo
echo "--- container status ---"
docker compose ps 2>/dev/null || true
echo
echo "Portal admin:  http://<this-nas-ip>:${PORTAL_PORT:-8080}/admin"
if [ -n "${CLOUDFLARED_TOKEN:-}" ]; then
  echo "Access via tunnel: route your Cloudflare hostname's service to http://localhost:8080"
fi