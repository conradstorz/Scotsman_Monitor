#!/bin/bash
cat << 'EOF'
=== Ice Gateway Setup Guide ===

Run these scripts in order on a fresh Raspberry Pi OS (64-bit) installation:

  sudo bash scripts/01_setup_os.sh        # Update OS, install base packages
  sudo bash scripts/02_setup_network.sh   # Static IP on eth0, UFW firewall
  sudo bash scripts/03_setup_tailscale.sh # Install Tailscale (requires auth key)
  sudo bash scripts/04_setup_onewire.sh   # Enable DS18B20 1-wire sensors
       bash scripts/05_setup_python.sh    # Install uv and Python dependencies
  sudo bash scripts/06_deploy_app.sh      # Deploy app, install systemd service

After all scripts:
  1. Edit /opt/ice_gateway/config/config.local.toml — add sensor ROM IDs and site name
  2. Edit /etc/ice-gateway/ice-gateway.env — add any secrets
  3. sudo systemctl restart ice-gateway
  4. sudo reboot   (required for 1-wire overlay to activate)

Verify:
  systemctl status ice-gateway
  tailscale status
  ls /sys/bus/w1/devices/
  curl http://localhost:8080/api/health
EOF

echo ""
echo "Checking repository files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

for f in 01_setup_os.sh 02_setup_network.sh 03_setup_tailscale.sh \
          04_setup_onewire.sh 05_setup_python.sh 06_deploy_app.sh; do
    if [ -f "$PROJECT_DIR/scripts/$f" ]; then
        echo "  OK  $f"
    else
        echo "  MISSING  $f"
    fi
done
