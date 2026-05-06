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

# Don't start ice-gateway yet: config.local.toml must be edited first.
# setup.sh prints the next-steps instructions.

# Install root-owned deploy script — sudoers rule points here (not the in-repo copy).
# argus cannot modify /usr/local/sbin, so this prevents privilege escalation via
# sudo + writable script.
DEPLOY_TARGET="/usr/local/sbin/ice-gateway-deploy"
cp "$APP_DIR/deploy.sh" "$DEPLOY_TARGET"
chown root:root "$DEPLOY_TARGET"
chmod 755 "$DEPLOY_TARGET"
echo "Deploy script installed at $DEPLOY_TARGET (root-owned)"
echo "NOTE: re-run this step after any changes to deploy.sh"

echo ""
echo "=== Services deployed ==="
systemctl status ice-gateway-watchdog --no-pager --lines=0 || true
systemctl status ice-gateway --no-pager || true
