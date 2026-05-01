#!/bin/bash
set -euo pipefail

echo "=== Step 4: One-Wire (DS18B20) Setup ==="

CONFIG_FILE="/boot/firmware/config.txt"

if [ ! -f "$CONFIG_FILE" ]; then
    # Older Raspberry Pi OS path
    CONFIG_FILE="/boot/config.txt"
fi

if ! grep -q "dtoverlay=w1-gpio" "$CONFIG_FILE"; then
    echo "" >> "$CONFIG_FILE"
    echo "# DS18B20 One-Wire temperature sensors" >> "$CONFIG_FILE"
    echo "dtoverlay=w1-gpio,gpiopin=4" >> "$CONFIG_FILE"
    echo "Added 1-wire overlay to $CONFIG_FILE"
else
    echo "1-wire overlay already present in $CONFIG_FILE"
fi

modprobe w1-gpio 2>/dev/null || true
modprobe w1-therm 2>/dev/null || true

echo "=== One-Wire setup complete. REBOOT REQUIRED for permanent effect. ==="
echo "After reboot, sensor ROM IDs will appear in: ls /sys/bus/w1/devices/"
