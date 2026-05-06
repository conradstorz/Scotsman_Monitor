#!/bin/bash
set -euo pipefail

echo "=== Step 4: Tailscale Setup ==="

# Install Tailscale via GPG-verified apt repo — no curl-pipe-sh
if command -v tailscale &>/dev/null; then
    echo "Tailscale already installed — skipping install"
else
    curl -fsSL https://pkgs.tailscale.com/stable/debian/bookworm.gpg \
        | gpg --dearmor -o /usr/share/keyrings/tailscale-archive-keyring.gpg
    cat > /etc/apt/sources.list.d/tailscale.list << 'EOF'
deb [signed-by=/usr/share/keyrings/tailscale-archive-keyring.gpg] https://pkgs.tailscale.com/stable/debian bookworm main
EOF
    apt-get update -qq
    apt-get install -y tailscale
    echo "Tailscale installed via apt"
fi

# Connect only if not already authenticated
if tailscale status &>/dev/null; then
    echo "Tailscale already connected — skipping auth"
    echo "Tailscale IP: $(tailscale ip -4 2>/dev/null || echo 'unknown')"
else
    if [ -z "${TAILSCALE_AUTH_KEY:-}" ]; then
        echo ""
        echo "Enter your Tailscale auth key (https://login.tailscale.com/admin/settings/keys):"
        echo "(or pre-supply it: sudo TAILSCALE_AUTH_KEY=tskey-... bash setup.sh)"
        read -r -s TAILSCALE_AUTH_KEY
    fi
    # REQUIREMENT: auth key must be pre-authorized for tag:ice-gateway in
    # Tailscale admin → Keys → Generate auth key → add tag:ice-gateway
    tailscale up \
        --authkey="$TAILSCALE_AUTH_KEY" \
        --hostname="ice-gateway-$(hostname)" \
        --advertise-tags=tag:ice-gateway
    echo ""
    echo "Tailscale IP: $(tailscale ip -4 2>/dev/null || echo 'pending')"
fi

# Lock SSH to eth0 + tailscale0 only — safe now that Tailscale is confirmed up.
# Idempotent: delete is || true in case the broad rule was already removed.
ufw delete allow ssh 2>/dev/null || true
ufw allow in on eth0 to any port 22 proto tcp comment 'SSH (LAN)'
ufw allow in on tailscale0 to any port 22 proto tcp comment 'SSH (Tailscale)'
ufw reload
echo "SSH access locked to eth0 + tailscale0"

echo "=== Tailscale setup complete ==="
