#!/bin/bash
set -euo pipefail

echo "=== Step 5: One-Wire (DS18B20) Hardware Setup ==="

BOOT_CONFIG="/boot/firmware/config.txt"
if [ ! -f "$BOOT_CONFIG" ]; then
    BOOT_CONFIG="/boot/config.txt"
fi

if ! grep -q "dtoverlay=w1-gpio" "$BOOT_CONFIG"; then
    echo "" >> "$BOOT_CONFIG"
    echo "# DS18B20 One-Wire temperature sensors — added by ice-gateway setup" >> "$BOOT_CONFIG"
    echo "dtoverlay=w1-gpio,gpiopin=4" >> "$BOOT_CONFIG"
    echo "Added 1-wire overlay to $BOOT_CONFIG"
else
    echo "1-wire overlay already present in $BOOT_CONFIG"
fi

modprobe w1-gpio 2>/dev/null || true
modprobe w1-therm 2>/dev/null || true

echo ""
echo "=== One-Wire hardware setup complete ==="
echo "Sensor registration happens in the next step after the app is cloned."
echo "NOTE: A reboot is required for the dtoverlay to activate at every boot."
