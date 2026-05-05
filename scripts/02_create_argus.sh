#!/bin/bash
set -euo pipefail

echo "=== Step 2: Create argus service user ==="

# Create user if not exists
if id "argus" &>/dev/null; then
    echo "argus user already exists — skipping creation"
else
    useradd --create-home --shell /bin/bash \
        --comment "Ice Gateway service account" argus
    echo "Created argus user"
fi

# Always ensure account is locked — idempotent on re-runs
passwd --lock argus
echo "argus account locked (no login — uses sudoers only)"

# Add to required groups (warn if group missing — may need hardware packages)
for group in gpio i2c dialout; do
    if getent group "$group" &>/dev/null; then
        usermod -aG "$group" argus
        echo "  Added argus to group: $group"
    else
        echo "  WARNING: group '$group' not found — skipping (install hardware packages first)"
    fi
done

# Write sudoers rules
SUDOERS_FILE="/etc/sudoers.d/ice-gateway"
SYSTEMCTL="$(command -v systemctl)"

# Determine which user invoked sudo so the deploy rule isn't hardcoded.
DEPLOY_USER="${SUDO_USER:-}"
if [ -n "$DEPLOY_USER" ]; then
    DEPLOY_RULE="${DEPLOY_USER} ALL=(argus) NOPASSWD: /home/argus/ice_gateway/deploy.sh"
    echo "  Personal deploy rule: $DEPLOY_USER can invoke deploy.sh as argus"
else
    DEPLOY_RULE="# No invoking user detected — add manually: <user> ALL=(argus) NOPASSWD: /home/argus/ice_gateway/deploy.sh"
    echo "  WARNING: SUDO_USER not set — personal deploy rule skipped; add manually to $SUDOERS_FILE"
fi

cat > "$SUDOERS_FILE" << EOF
# Ice Gateway — written by 02_create_argus.sh — do not edit manually
$DEPLOY_RULE

# argus can manage the ice-gateway service
argus ALL=(root) NOPASSWD: $SYSTEMCTL start ice-gateway
argus ALL=(root) NOPASSWD: $SYSTEMCTL stop ice-gateway
argus ALL=(root) NOPASSWD: $SYSTEMCTL restart ice-gateway
EOF

chmod 440 "$SUDOERS_FILE"
visudo -cf "$SUDOERS_FILE"
echo "Wrote and validated sudoers rules: $SUDOERS_FILE"

echo "=== argus user setup complete ==="
