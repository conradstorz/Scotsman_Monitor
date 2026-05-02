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

# Load modules now so sensors are readable in this session without a reboot.
# The dtoverlay above ensures they load automatically on every subsequent boot.
modprobe w1-gpio 2>/dev/null || true
modprobe w1-therm 2>/dev/null || true

echo ""
echo "Sensors connected to GPIO4 right now:"
ls /sys/bus/w1/devices/ 2>/dev/null | grep "^28-" || echo "  (none detected — connect sensors and re-run, or check wiring)"

echo ""
echo "=== One-Wire setup complete ==="
echo "NOTE: A reboot is required for the dtoverlay to activate at boot."
echo "After rebooting, verify with:  ls /sys/bus/w1/devices/"
echo "Copy the 28-xxxxxxxxxxxx IDs into config/config.local.toml under [[temperature_sensors]]."
