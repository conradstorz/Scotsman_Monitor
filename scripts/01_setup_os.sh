#!/bin/bash
set -euo pipefail

echo "=== Step 1: OS Setup ==="
apt-get update
apt-get upgrade -y
apt-get install -y git sqlite3 i2c-tools chrony ufw openssh-server \
    curl snmp tftpd-hpa

timedatectl set-timezone UTC

systemctl enable ssh
systemctl start ssh

systemctl enable chrony
systemctl start chrony

echo "=== OS setup complete ==="
