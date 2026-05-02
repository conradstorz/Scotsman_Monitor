#!/bin/bash
set -euo pipefail

echo "=== Step 4: One-Wire (DS18B20) Setup ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
APP_CONFIG="$PROJECT_DIR/config/config.local.toml"
BOOT_CONFIG="/boot/firmware/config.txt"

# --- Boot overlay ---
if [ ! -f "$BOOT_CONFIG" ]; then
    BOOT_CONFIG="/boot/config.txt"
fi

if ! grep -q "dtoverlay=w1-gpio" "$BOOT_CONFIG"; then
    echo "" >> "$BOOT_CONFIG"
    echo "# DS18B20 One-Wire temperature sensors" >> "$BOOT_CONFIG"
    echo "dtoverlay=w1-gpio,gpiopin=4" >> "$BOOT_CONFIG"
    echo "Added 1-wire overlay to $BOOT_CONFIG"
else
    echo "1-wire overlay already present in $BOOT_CONFIG"
fi

# Load modules now so sensors are readable in this session without a reboot.
# The dtoverlay above ensures they load automatically on every subsequent boot.
modprobe w1-gpio 2>/dev/null || true
modprobe w1-therm 2>/dev/null || true

# --- App config ---
if [ ! -f "$APP_CONFIG" ]; then
    cp "$PROJECT_DIR/config/config.example.toml" "$APP_CONFIG"
    echo "Created config.local.toml from config.example.toml"
    echo "  Edit $APP_CONFIG to set site_name and remove placeholder sensor entries."
fi

# --- Discover and register sensors ---
FOUND=0
ADDED=0
SKIPPED=0

echo ""
echo "Scanning /sys/bus/w1/devices/ for DS18B20 sensors..."

for device_path in /sys/bus/w1/devices/28-*; do
    [ -d "$device_path" ] || continue
    sensor_id="$(basename "$device_path")"
    FOUND=$((FOUND + 1))

    if grep -q "\"$sensor_id\"" "$APP_CONFIG"; then
        echo "  SKIP (already in config): $sensor_id"
        SKIPPED=$((SKIPPED + 1))
    else
        # Use last 4 chars of ROM ID as a unique placeholder name suffix
        suffix="${sensor_id: -4}"
        cat >> "$APP_CONFIG" << EOF

[[temperature_sensors]]
id = "$sensor_id"
name = "sensor_$suffix"
location = "unknown"
enabled = true
EOF
        echo "  ADDED: $sensor_id  (name = \"sensor_$suffix\", location = \"unknown\")"
        ADDED=$((ADDED + 1))
    fi
done

echo ""
if [ "$FOUND" -eq 0 ]; then
    echo "No sensors detected on GPIO4."
    echo "  Check wiring and re-run this script, or add entries manually:"
    echo "  $APP_CONFIG"
else
    echo "$FOUND sensor(s) found — $ADDED added to config, $SKIPPED already listed."
    if [ "$ADDED" -gt 0 ]; then
        echo ""
        echo "Update the name and location for each new entry in:"
        echo "  $APP_CONFIG"
    fi
fi

echo ""
echo "=== One-Wire setup complete ==="
echo "NOTE: A reboot is required for the dtoverlay to activate at boot."
echo "After rebooting, verify with:  ls /sys/bus/w1/devices/"
