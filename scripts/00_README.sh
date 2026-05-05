#!/bin/bash
cat << 'EOF'
=== Ice Gateway Setup Guide ===

--- BEFORE YOU BEGIN: Tailscale credentials ---

Script 04 will prompt for a Tailscale auth key. Get one first:

  1. Create a Tailscale account at https://tailscale.com
  2. Go to Settings → Keys → Generate auth key
     https://login.tailscale.com/admin/settings/keys
  3. Recommended settings:
       Reusable:  No   (one-time key)
       Expiry:    90 days
       Ephemeral: No   (Pi must persist after reboots)
  4. Copy the key (starts with tskey-auth-...).
     Script 04 will prompt for it interactively and does not store it.

  Re-running setup.sh does NOT consume or invalidate the key. Script 04
  checks 'tailscale status' first — if already enrolled it skips the auth
  step entirely. Your existing tailnet node and Tailscale IP are preserved.

--- Moving to a different Tailscale network ---

  If the Pi needs to be re-assigned to a different tailnet:

    tailscale logout                        # removes Pi from current tailnet
    sudo bash scripts/04_setup_tailscale.sh # prompts for new auth key

  Generate the new key from the target tailnet's admin console first.
  The old auth key was already consumed on first use and cannot be reused.

--- Bootstrap (run on a fresh Raspberry Pi OS 64-bit install) ---

  git clone https://github.com/<YOUR_GITHUB_USERNAME>/Scotsman_Monitor
  cd Scotsman_Monitor
  sudo bash setup.sh

setup.sh calls these scripts in order (all run as root):

  scripts/01_setup_os.sh        Update OS, install base packages (snmp, tftpd-hpa, etc.)
  scripts/02_create_argus.sh    Create 'argus' service user, set groups, write sudoers
  scripts/03_setup_network.sh   Static IP + DHCP server on eth0, UFW firewall
  scripts/04_setup_tailscale.sh Install Tailscale (prompts for auth key once)
  scripts/05_setup_onewire.sh   Enable DS18B20 1-wire hardware (dtoverlay + modprobe)
  scripts/06_setup_app.sh       Clone repo as argus, install uv, sync deps, register sensors
  scripts/07_deploy_service.sh  Install and start the ice-gateway systemd service

--- Network layout after script 03 ---

  wlan0  — DHCP from site router, internet access, Tailscale
  eth0   — 192.168.50.1/24, Pi is DHCP server, KSBU-N connects here

--- Service account ---

  User:     argus
  Password: scotsman  (change this for production)
  Home:     /home/argus/
  App:      /home/argus/ice_gateway/

--- After setup ---

  1. Cable the KSBU-N to eth0 and reboot
  2. Discover the KSBU-N IP:  arp -n
  3. Edit /home/argus/ice_gateway/config/config.local.toml
       - Set ksbu_device_ip to the discovered address
       - Set site_name and machine_name
       - Update sensor name/location entries
  4. Add any secrets to /home/argus/ice_gateway/config/ice-gateway.env
  5. sudo systemctl restart ice-gateway

--- Verify ---

  systemctl status ice-gateway
  tailscale status
  ls /sys/bus/w1/devices/
  curl http://localhost:8080/api/health

--- Day-to-day deployment ---

  Pull the latest code and restart:
    ./deploy.sh          (runs as argus automatically, even if called as conrad)

EOF

echo ""
echo "Checking repository files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

for f in setup.sh deploy.sh; do
    if [ -f "$PROJECT_DIR/$f" ]; then
        echo "  OK  $f"
    else
        echo "  MISSING  $f"
    fi
done

for f in 01_setup_os.sh 02_create_argus.sh 03_setup_network.sh \
          04_setup_tailscale.sh 05_setup_onewire.sh \
          06_setup_app.sh 07_deploy_service.sh; do
    if [ -f "$PROJECT_DIR/scripts/$f" ]; then
        echo "  OK  scripts/$f"
    else
        echo "  MISSING  scripts/$f"
    fi
done
