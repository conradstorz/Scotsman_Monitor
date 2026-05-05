#!/bin/bash
set -euo pipefail

# Self-correcting: if not running as argus, re-exec as argus.
# Use realpath so the absolute path survives being called from any directory.
SELF="$(realpath "$0")"
if [ "$(whoami)" != "argus" ]; then
    exec sudo -u argus "$SELF" "$@"
fi

APP_DIR="/home/argus/ice_gateway"

echo "=== Deploying ice-gateway ==="
echo "Before: $(git -C "$APP_DIR" rev-parse --short HEAD)"

git -C "$APP_DIR" pull --ff-only
cd "$APP_DIR"
/home/argus/.local/bin/uv sync --no-dev

echo "After:  $(git -C "$APP_DIR" rev-parse --short HEAD)"
echo "Restarting service..."

sudo systemctl restart ice-gateway
systemctl status ice-gateway --no-pager
