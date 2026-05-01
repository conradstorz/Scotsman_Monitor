#!/bin/bash
set -euo pipefail

echo "=== Step 5: Python/uv Setup ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

export PATH="$HOME/.local/bin:$PATH"

cd "$PROJECT_DIR"
uv sync

echo "=== Python setup complete ==="
echo "Test: uv run python -c \"from ice_gateway.main import main; print('ok')\""
