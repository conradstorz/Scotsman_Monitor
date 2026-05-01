#!/bin/bash
set -euo pipefail

echo "=== Step 3: Tailscale Setup ==="

curl -fsSL https://tailscale.com/install.sh | sh

echo ""
echo "Enter your Tailscale auth key (from https://login.tailscale.com/admin/settings/keys):"
read -r -s TAILSCALE_AUTH_KEY

tailscale up --authkey="$TAILSCALE_AUTH_KEY" --hostname="ice-gateway-$(hostname)"

echo ""
echo "=== Tailscale setup complete ==="
echo "Tailscale IP: $(tailscale ip -4 2>/dev/null || echo 'pending')"
