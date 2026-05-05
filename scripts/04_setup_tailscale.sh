#!/bin/bash
set -euo pipefail

echo "=== Step 4: Tailscale Setup ==="

# Install Tailscale if not present
if command -v tailscale &>/dev/null; then
    echo "Tailscale already installed — skipping install"
else
    curl -fsSL https://tailscale.com/install.sh | sh
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
    tailscale up --authkey="$TAILSCALE_AUTH_KEY" --hostname="ice-gateway-$(hostname)"
    echo ""
    echo "Tailscale IP: $(tailscale ip -4 2>/dev/null || echo 'pending')"
fi

echo "=== Tailscale setup complete ==="
