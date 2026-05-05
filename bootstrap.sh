#!/bin/bash
# Bootstrap the Ice Gateway setup on a fresh Raspberry Pi.
# Usage: curl -fsSL https://raw.githubusercontent.com/conradstorz/Scotsman_Monitor/master/bootstrap.sh | sudo bash
set -euo pipefail

REPO="https://github.com/conradstorz/Scotsman_Monitor.git"
BRANCH="master"

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: pipe this script to sudo bash" >&2
    exit 1
fi

# Clone into the invoking user's home, not root's.
INSTALL_USER="${SUDO_USER:-}"
if [ -z "$INSTALL_USER" ]; then
    echo "ERROR: run via sudo so the repo is cloned to your home directory:" >&2
    echo "  curl -fsSL <url> | sudo bash" >&2
    exit 1
fi
INSTALL_HOME="$(getent passwd "$INSTALL_USER" | cut -d: -f6)"
DEST="$INSTALL_HOME/Scotsman_Monitor"

# Install git if missing (common on minimal OS images)
if ! command -v git &>/dev/null; then
    echo "--- Installing git ---"
    apt-get update -qq
    apt-get install -y --no-install-recommends git
fi

# Clone or pull
if [ -d "$DEST/.git" ]; then
    echo "--- Repo exists at $DEST — pulling latest ---"
    git -C "$DEST" pull
else
    echo "--- Cloning into $DEST ---"
    git clone --branch "$BRANCH" "$REPO" "$DEST"
    chown -R "$INSTALL_USER:$INSTALL_USER" "$DEST"
fi

echo ""
cd "$DEST"
exec bash setup.sh
