#!/bin/bash
set -euo pipefail

echo "=== Step 6: App Install ==="

REPO_URL="${1:?ERROR: pass repo URL as first argument (called automatically by setup.sh)}"
REPO_BRANCH="${2:-master}"
APP_DIR="/home/argus/ice_gateway"

# Clone as root (avoids per-user git config issues), then fix ownership.
if [ -d "$APP_DIR/.git" ] && [ -f "$APP_DIR/pyproject.toml" ]; then
    echo "App directory already exists — skipping clone"
elif [ -d "$APP_DIR/.git" ] && [ ! -f "$APP_DIR/pyproject.toml" ]; then
    echo "Incomplete clone detected — fetching and checking out branch '$REPO_BRANCH'"
    git config --global --add safe.directory "$APP_DIR"
    git -C "$APP_DIR" fetch origin "$REPO_BRANCH"
    git -C "$APP_DIR" checkout "$REPO_BRANCH"
    chown -R argus:argus "$APP_DIR"
else
    git clone --branch "$REPO_BRANCH" "$REPO_URL" "$APP_DIR"
    chown -R argus:argus "$APP_DIR"
    echo "Cloned $REPO_URL → $APP_DIR"
fi

if [ ! -f "$APP_DIR/pyproject.toml" ]; then
    echo "ERROR: pyproject.toml missing from clone" >&2
    ls -la "$APP_DIR/" >&2
    exit 1
fi

# Install uv for argus if not present — pinned binary from GitHub releases with SHA256 verify.
# To update: change UV_VERSION. The .sha256 file is fetched from the same GitHub release.
# Release page: https://github.com/astral-sh/uv/releases
UV_VERSION="0.7.3"
UV_ARCH="aarch64-unknown-linux-musl"
UV_TARBALL="uv-${UV_ARCH}.tar.gz"
UV_RELEASE_BASE="https://github.com/astral-sh/uv/releases/download/${UV_VERSION}"

if [ -f "/home/argus/.local/bin/uv" ]; then
    echo "uv already installed for argus — skipping"
else
    TMPDIR_UV="$(mktemp -d)"
    trap 'rm -rf "$TMPDIR_UV"' EXIT

    echo "Downloading uv ${UV_VERSION} for ${UV_ARCH}..."
    curl -LsSf "${UV_RELEASE_BASE}/${UV_TARBALL}" -o "${TMPDIR_UV}/${UV_TARBALL}"
    curl -LsSf "${UV_RELEASE_BASE}/${UV_TARBALL}.sha256" -o "${TMPDIR_UV}/${UV_TARBALL}.sha256"

    # Verify integrity — exits non-zero and aborts (set -e) if mismatch
    (cd "${TMPDIR_UV}" && sha256sum -c "${UV_TARBALL}.sha256")

    tar -xzf "${TMPDIR_UV}/${UV_TARBALL}" -C "${TMPDIR_UV}"
    sudo -u argus mkdir -p /home/argus/.local/bin
    install -o argus -g argus -m 755 "${TMPDIR_UV}/uv"  /home/argus/.local/bin/uv
    install -o argus -g argus -m 755 "${TMPDIR_UV}/uvx" /home/argus/.local/bin/uvx

    echo "uv ${UV_VERSION} installed for argus"
fi

# Install Python dependencies (no dev tools on the Pi)
(cd "$APP_DIR" && sudo -u argus /home/argus/.local/bin/uv sync --no-dev)
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
    chmod 600 "$APP_DIR/config/ice-gateway.env"
    echo "Created ice-gateway.env (mode 600) — edit $APP_DIR/config/ice-gateway.env to add secrets"
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
