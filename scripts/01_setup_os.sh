#!/bin/bash
set -euo pipefail

echo "=== Step 1: OS Setup ==="

apt-get update
apt-get upgrade -y
apt-get install -y git sqlite3 i2c-tools chrony ufw openssh-server \
    curl unattended-upgrades

echo "Purging unneeded network listeners (snmp, tftpd-hpa)..."
# Purge unneeded network listeners if present from prior runs (idempotent)
apt-get purge -y --auto-remove snmp tftpd-hpa 2>/dev/null || true

timedatectl set-timezone UTC

systemctl enable ssh
systemctl start ssh

# Regenerate SSH host keys — Pi OS images ship with shared keys.
# Marker file prevents rotation on re-runs (which would break known_hosts).
HOSTKEY_MARKER="/etc/ssh/.host-keys-regenerated"
if [ ! -f "$HOSTKEY_MARKER" ]; then
    rm -f /etc/ssh/ssh_host_*
    DEBIAN_FRONTEND=noninteractive dpkg-reconfigure openssh-server
    touch "$HOSTKEY_MARKER"
    echo "SSH host keys regenerated"
else
    echo "SSH host keys already regenerated — skipping"
fi

# PREREQUISITE: SSH public key auth must already be working for the connecting user
# before this block runs. PasswordAuthentication no will lock out password-only access
# the moment sshd restarts. Verify with: ssh-copy-id user@pi before running setup.

# Write sshd hardening config — drop-in avoids editing sshd_config directly.
# Idempotent: overwriting the file with the same content is safe.
cat > /etc/ssh/sshd_config.d/99-ice-gateway-hardening.conf << 'EOF'
# Ice Gateway SSH hardening — written by 01_setup_os.sh — do not edit manually
PasswordAuthentication no
PermitRootLogin no
X11Forwarding no
AllowAgentForwarding no
MaxAuthTries 3
LoginGraceTime 20
EOF
chmod 644 /etc/ssh/sshd_config.d/99-ice-gateway-hardening.conf
sshd -t   # validate combined config — fails fast before restarting
systemctl restart ssh
echo "sshd hardening applied and service restarted"

systemctl enable chrony
systemctl start chrony

# --- Automatic security updates ---
# Run nightly; reboot at 03:00 if a kernel/libc update requires it.
# Security-only — full upgrades are done manually to avoid unexpected breakage.

cat > /etc/apt/apt.conf.d/20auto-upgrades << 'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

cat > /etc/apt/apt.conf.d/52ice-gateway << 'EOF'
Unattended-Upgrade::Origins-Pattern {
    "origin=Debian,codename=${distro_codename},label=Debian-Security";
    "origin=Raspbian,codename=${distro_codename},label=Raspbian";
    "origin=Raspberry Pi Foundation,codename=${distro_codename},label=Raspberry Pi Foundation";
};
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "03:00";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
EOF

systemctl enable unattended-upgrades
systemctl restart unattended-upgrades
echo "Automatic security updates configured — nightly, reboot window 03:00 if needed"

# --- Hardware watchdog ---
# dtparam=watchdog=on activates the BCM2835 hardware watchdog on the Pi.
# systemd then pets it every 14 s; if the system locks up the Pi reboots
# automatically within 15 s (the hardware timeout).

BOOT_CONFIG="/boot/firmware/config.txt"
if [ ! -f "$BOOT_CONFIG" ]; then
    BOOT_CONFIG="/boot/config.txt"
fi

if ! grep -q "dtparam=watchdog=on" "$BOOT_CONFIG"; then
    echo "" >> "$BOOT_CONFIG"
    echo "# Hardware watchdog — added by ice-gateway setup" >> "$BOOT_CONFIG"
    echo "dtparam=watchdog=on" >> "$BOOT_CONFIG"
    echo "Hardware watchdog enabled in $BOOT_CONFIG (takes effect after reboot)"
else
    echo "Hardware watchdog already enabled in $BOOT_CONFIG"
fi

if ! grep -q "^RuntimeWatchdogSec=" /etc/systemd/system.conf; then
    echo "RuntimeWatchdogSec=14" >> /etc/systemd/system.conf
    systemctl daemon-reexec
    echo "systemd watchdog armed (14 s)"
else
    echo "systemd watchdog already configured"
fi

echo "=== OS setup complete ==="
