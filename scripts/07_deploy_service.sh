#!/bin/bash
set -euo pipefail

echo "=== Step 7: Deploy systemd service ==="

APP_DIR="/home/argus/ice_gateway"

install_service() {
    local name="$1"
    local src="$APP_DIR/systemd/${name}.service"
    local dest="/etc/systemd/system/${name}.service"
    if [ ! -f "$src" ]; then
        echo "ERROR: service file not found at $src" >&2
        echo "Run 06_setup_app.sh first." >&2
        exit 1
    fi
    cp "$src" "$dest"
    echo "Installed $dest"
}

install_service ice-gateway-watchdog
install_service ice-gateway

systemctl daemon-reload

systemctl enable ice-gateway-watchdog
systemctl enable ice-gateway

# Watchdog checker is oneshot — starting it now runs the check immediately.
systemctl restart ice-gateway-watchdog
systemctl restart ice-gateway

echo ""
echo "=== Services deployed ==="
systemctl status ice-gateway-watchdog --no-pager --lines=0
systemctl status ice-gateway --no-pager
