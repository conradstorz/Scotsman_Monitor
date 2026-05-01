#!/bin/bash
set -euo pipefail

echo "=== Step 2: Network Setup ==="

# Static IP on eth0 for KSBU-N private subnet
if ! grep -q "interface eth0" /etc/dhcpcd.conf; then
    cat >> /etc/dhcpcd.conf << 'EOF'

# KSBU-N private subnet — added by ice-gateway setup
interface eth0
static ip_address=192.168.50.1/24
norouter
nogateway
EOF
    echo "Added static eth0 config to /etc/dhcpcd.conf"
else
    echo "eth0 static config already present"
fi

systemctl restart dhcpcd || true

# Firewall
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 8080/tcp comment 'Ice Gateway Dashboard'
ufw --force enable

echo "=== Network setup complete ==="
