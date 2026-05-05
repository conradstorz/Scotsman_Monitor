#!/bin/bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: Run as root: sudo bash setup.sh" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect the repo URL from the git remote — works for any fork.
# Convert SSH remotes (git@github.com:user/repo.git) to HTTPS so argus
# can clone without needing an SSH key on the Pi.
REPO_URL="$(git -C "$SCRIPT_DIR" remote get-url origin 2>/dev/null || echo '')"
if [ -z "$REPO_URL" ]; then
    echo "ERROR: Could not read git remote URL." >&2
    echo "Make sure you cloned the repo before running setup.sh." >&2
    exit 1
fi
REPO_URL="$(echo "$REPO_URL" | sed 's|git@\([^:]*\):|https://\1/|')"

echo "=== Ice Gateway Setup ==="
echo "Repo: $REPO_URL"
echo ""

run_step() {
    local name="$1"
    shift
    echo ">>> $name"
    if bash "$@"; then
        echo "    OK: $name"
    else
        echo "    FAILED: $name — aborting"
        exit 1
    fi
    echo ""
}

run_step "OS packages"       "$SCRIPT_DIR/scripts/01_setup_os.sh"
run_step "argus user"        "$SCRIPT_DIR/scripts/02_create_argus.sh"
run_step "Network"           "$SCRIPT_DIR/scripts/03_setup_network.sh"
run_step "Tailscale"         "$SCRIPT_DIR/scripts/04_setup_tailscale.sh"
run_step "One-Wire hardware" "$SCRIPT_DIR/scripts/05_setup_onewire.sh"
run_step "App install"       "$SCRIPT_DIR/scripts/06_setup_app.sh" "$REPO_URL"
run_step "Systemd service"   "$SCRIPT_DIR/scripts/07_deploy_service.sh"

echo "=== Setup complete. Next steps ==="
echo ""
echo "  1. Cable KSBU-N to eth0 and reboot"
echo "  2. Edit /home/argus/ice_gateway/config/config.local.toml"
echo "     (set site_name, ksbu_device_ip, sensor names)"
echo "  3. sudo systemctl restart ice-gateway"
echo ""
echo "  Verify:"
echo "    systemctl status ice-gateway"
echo "    tailscale status"
echo "    ls /sys/bus/w1/devices/"
echo "    curl http://localhost:8080/api/health"
