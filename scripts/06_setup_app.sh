#!/bin/bash
set -euo pipefail

echo "=== Step 6: App Install ==="

REPO_URL="${1:?ERROR: pass repo URL as first argument (called automatically by setup.sh)}"
APP_DIR="/home/argus/ice_gateway"

# Clone if not already present
if [ -d "$APP_DIR/.git" ]; then
    echo "App directory already exists — skipping clone"
else
    sudo -u argus git clone "$REPO_URL" "$APP_DIR"
    echo "Cloned $REPO_URL → $APP_DIR"
fi

# Install uv for argus if not present
if [ -f "/home/argus/.local/bin/uv" ]; then
    echo "uv already installed for argus — skipping"
else
    sudo -u argus bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
    echo "Installed uv for argus"
fi

# Install Python dependencies (no dev tools on the Pi)
sudo -u argus bash -c "cd '$APP_DIR' && /home/argus/.local/bin/uv sync --no-dev"
echo "uv sync complete"

# Create config.local.toml if missing
if [ ! -f "$APP_DIR/config/config.local.toml" ]; then
    sudo -u argus cp "$APP_DIR/config/config.example.toml" \
        "$APP_DIR/config/config.local.toml"
    echo "Created config.local.toml — edit $APP_DIR/config/config.local.toml before starting"
else
    echo "config.local.toml already exists — skipping"
fi

# Create ice-gateway.env if missing
if [ ! -f "$APP_DIR/config/ice-gateway.env" ]; then
    sudo -u argus cp "$APP_DIR/.env.example" \
        "$APP_DIR/config/ice-gateway.env"
    echo "Created ice-gateway.env — edit $APP_DIR/config/ice-gateway.env to add secrets"
else
    echo "ice-gateway.env already exists — skipping"
fi

# Register discovered DS18B20 sensors into config.local.toml
echo ""
echo "Scanning /sys/bus/w1/devices/ for DS18B20 sensors..."
APP_CONFIG="$APP_DIR/config/config.local.toml"
FOUND=0; ADDED=0; SKIPPED=0

for device_path in /sys/bus/w1/devices/28-*; do
    [ -d "$device_path" ] || continue
    sensor_id="$(basename "$device_path")"
    FOUND=$((FOUND + 1))

    if grep -q "\"$sensor_id\"" "$APP_CONFIG"; then
        echo "  SKIP (already in config): $sensor_id"
        SKIPPED=$((SKIPPED + 1))
    else
        suffix="${sensor_id: -4}"
        sudo -u argus tee -a "$APP_CONFIG" > /dev/null << EOF

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
    echo "No sensors detected (expected if 1-wire wiring not yet in place)."
    echo "Re-run this script after wiring sensors, or add entries manually:"
    echo "  $APP_CONFIG"
else
    echo "$FOUND sensor(s) found — $ADDED added to config, $SKIPPED already listed."
    if [ "$ADDED" -gt 0 ]; then
        echo "Update name and location for each new entry in $APP_CONFIG"
    fi
fi

echo ""
echo "=== App install complete ==="
