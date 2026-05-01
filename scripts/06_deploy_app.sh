#!/bin/bash
set -euo pipefail

echo "=== Step 6: Deploy Application ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
APP_DIR="/opt/ice_gateway"
ENV_FILE="/etc/ice-gateway/ice-gateway.env"

# Copy project to /opt
mkdir -p "$APP_DIR"
rsync -a --exclude='.git' --exclude='.venv' "$PROJECT_DIR/" "$APP_DIR/"

# Re-sync dependencies in the installed location
cd "$APP_DIR"
export PATH="$HOME/.local/bin:$PATH"
uv sync

# Create config.local.toml if missing
if [ ! -f "$APP_DIR/config/config.local.toml" ]; then
    cp "$APP_DIR/config/config.example.toml" "$APP_DIR/config/config.local.toml"
    echo "Created config.local.toml — edit $APP_DIR/config/config.local.toml before starting"
fi

# Create env file if missing
mkdir -p "$(dirname "$ENV_FILE")"
if [ ! -f "$ENV_FILE" ]; then
    cp "$APP_DIR/.env.example" "$ENV_FILE"
    echo "Created $ENV_FILE — edit with your secrets"
fi

# Install and start systemd service
cp "$APP_DIR/systemd/ice-gateway.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable ice-gateway
systemctl start ice-gateway

echo ""
echo "=== Deployment complete ==="
systemctl status ice-gateway --no-pager
