#!/bin/bash
set -euo pipefail

# Intended call chain:
#   admin user → sudo /usr/local/sbin/ice-gateway-deploy (runs as root)
#   → re-execs as argus (below) → git pull + uv sync + sudo systemctl restart
# realpath prevents symlink attacks on $SELF. The sudoers rule is in /etc/sudoers.d/ice-gateway.
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
