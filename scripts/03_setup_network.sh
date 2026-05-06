#!/bin/bash
set -euo pipefail

echo "=== Step 3: Network Setup ==="

# The Pi is the DHCP server on eth0. The KSBU-N connects to eth0 and
# receives an address in 192.168.50.100-200. After first boot, discover
# the KSBU-N IP with: arp -n | grep eth0
#
# Raspberry Pi OS Bookworm uses NetworkManager (ipv4.method shared handles
# both the static IP and DHCP serving automatically via NM's built-in dnsmasq).
# Bullseye uses dhcpcd + a standalone dnsmasq install.

if command -v nmcli &>/dev/null; then
    if nmcli connection show "eth0-ksbu" &>/dev/null; then
        echo "eth0 config already present (NetworkManager)"
    else
        # 'shared' gives the Pi a static IP and runs NM's built-in dnsmasq
        # to serve DHCP to whatever connects on eth0.
        nmcli connection add type ethernet ifname eth0 con-name eth0-ksbu \
            ipv4.method shared \
            ipv4.addresses 192.168.50.1/24
        nmcli connection up eth0-ksbu
        echo "eth0 configured — Pi is 192.168.50.1, DHCP range auto-assigned by NetworkManager"
    fi
elif [ -f /etc/dhcpcd.conf ]; then
    # Static IP via dhcpcd
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

    # DHCP server for eth0 so the KSBU-N receives an address
    apt-get install -y dnsmasq
    cat > /etc/dnsmasq.d/ice-gateway-eth0.conf << 'EOF'
interface=eth0
bind-interfaces
dhcp-range=192.168.50.100,192.168.50.200,12h
EOF
    systemctl enable dnsmasq
    systemctl restart dnsmasq
    echo "dnsmasq configured — DHCP range 192.168.50.100-200 on eth0"
else
    echo "ERROR: Neither nmcli nor dhcpcd found — configure eth0 manually" >&2
    exit 1
fi

# Firewall
ufw --force reset
ufw default deny incoming
ufw default allow outgoing

# SSH stays open on all interfaces here — locked to tailscale0+eth0 in 04_setup_tailscale.sh
# after Tailscale is confirmed connected (locking before that risks an SSH lockout).
ufw allow ssh

# Dashboard: LAN (eth0) and Tailscale only — never exposed on wlan0
ufw allow in on eth0 to any port 8080 proto tcp comment 'Ice Gateway Dashboard (LAN)'
ufw allow in on tailscale0 to any port 8080 proto tcp comment 'Ice Gateway Dashboard (Tailscale)'

ufw --force enable

echo "=== Network setup complete ==="
echo "After cabling the KSBU-N to eth0 and rebooting, discover its IP with:"
echo "  arp -n | grep eth0"
