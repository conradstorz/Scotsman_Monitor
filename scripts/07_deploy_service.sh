#!/bin/bash
set -euo pipefail

echo "=== Step 7: Deploy systemd service ==="

APP_DIR="/home/argus/ice_gateway"
SERVICE_SRC="$APP_DIR/systemd/ice-gateway.service"
SERVICE_DEST="/etc/systemd/system/ice-gateway.service"

if [ ! -f "$SERVICE_SRC" ]; then
    echo "ERROR: service file not found at $SERVICE_SRC" >&2
    echo "Run 06_setup_app.sh first." >&2
    exit 1
fi

cp "$SERVICE_SRC" "$SERVICE_DEST"
systemctl daemon-reload
systemctl enable ice-gateway
systemctl restart ice-gateway

echo ""
echo "=== Service deployed ==="
systemctl status ice-gateway --no-pager
