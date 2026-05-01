#!/bin/bash
set -euo pipefail

echo "=== Step 2: Network Setup ==="

# Static IP on eth0 for KSBU-N private subnet.
# Raspberry Pi OS Bookworm uses NetworkManager; Bullseye uses dhcpcd.
if command -v nmcli &>/dev/null; then
    if nmcli connection show "eth0-ksbu" &>/dev/null; then
        echo "eth0 static config already present (NetworkManager)"
    else
        nmcli connection add type ethernet ifname eth0 con-name eth0-ksbu \
            ipv4.method manual ipv4.addresses 192.168.50.1/24 \
            ipv4.never-default yes
        nmcli connection up eth0-ksbu
        echo "Added static eth0 config via NetworkManager"
    fi
elif [ -f /etc/dhcpcd.conf ]; then
    if ! grep -q "interface eth0" /etc/dhcpcd.conf; then
        cat >> /etc/dhcpcd.conf << 'EOF'

# KSBU-N private subnet — added by ice-gateway setup
interface eth0
static ip_address=192.168.50.1/24
norouter
nogateway
EOF
        echo "Added static eth0 config to /etc/dhcpcd.conf"
        systemctl restart dhcpcd
    else
        echo "eth0 static config already present (dhcpcd)"
    fi
else
    echo "ERROR: Neither nmcli nor dhcpcd found — configure eth0 manually" >&2
    exit 1
fi

# Firewall
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 8080/tcp comment 'Ice Gateway Dashboard'
ufw --force enable

echo "=== Network setup complete ==="
