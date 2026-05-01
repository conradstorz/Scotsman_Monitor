#!/bin/bash
cat << 'EOF'
=== Ice Gateway Setup Guide ===

--- BEFORE YOU BEGIN: Tailscale credentials ---

Script 03 will prompt for a Tailscale auth key. Get one before you start:

  1. Create a free Tailscale account at https://tailscale.com if you don't have one.

  2. In the admin console, go to:
       Settings → Keys → Generate auth key
       https://login.tailscale.com/admin/settings/keys

  3. Recommended key settings:
       Reusable:    No  (one-time key, revokes itself after use)
       Expiry:      90 days (or as short as you're comfortable with)
       Ephemeral:   No  (Pi must persist in your tailnet after reboots)
       Tags:        optional — tag:ice-gateway if you use ACL tags

  4. Copy the key (starts with tskey-auth-...). Script 03 will prompt for it
     interactively. It is not stored anywhere by the setup scripts.

  5. After setup, the Pi appears in your tailnet as ice-gateway-<hostname>.
     Access the dashboard from any device on your tailnet:
       http://<tailscale-ip>:8080

-----------------------------------------------

Run these scripts in order on a fresh Raspberry Pi OS (64-bit) installation:

  sudo bash scripts/01_setup_os.sh        # Update OS, install base packages
  sudo bash scripts/02_setup_network.sh   # Static IP + DHCP server on eth0, UFW firewall
  sudo bash scripts/03_setup_tailscale.sh # Install Tailscale (requires auth key)
  sudo bash scripts/04_setup_onewire.sh   # Enable DS18B20 1-wire sensors
       bash scripts/05_setup_python.sh    # Install uv and Python dependencies
  sudo bash scripts/06_deploy_app.sh      # Deploy app, install systemd service

Network layout after script 02:
  wlan0  — DHCP from site router, internet access, Tailscale
  eth0   — 192.168.50.1/24, Pi is DHCP server, KSBU-N connects here

After all scripts:
  1. Cable the KSBU-N to eth0 and reboot the Pi
  2. Discover the KSBU-N's assigned IP:  arp -n | grep eth0
  3. Edit /opt/ice_gateway/config/config.local.toml:
       - Set ksbu_device_ip to the discovered address
       - Add sensor ROM IDs and site name
  4. Edit /etc/ice-gateway/ice-gateway.env — add any secrets
  5. sudo systemctl restart ice-gateway

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
