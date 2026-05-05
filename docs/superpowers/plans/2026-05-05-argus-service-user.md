# Argus Service User Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the root-owned `/opt/ice_gateway` layout with a dedicated `argus` service user whose home directory owns everything, eliminating the permission problem where `uv` creates root-owned venv files.

**Architecture:** A new system user `argus` owns `/home/argus/ice_gateway/` (a git clone of the public repo). All setup scripts are either idempotent or self-correcting — they re-exec as `argus` when invoked as another user. The systemd service runs as `argus` and calls the venv binary directly, never invoking `uv` at runtime.

**Tech Stack:** bash, systemd, uv, git, sudoers, Raspberry Pi OS (Bookworm/Bullseye)

---

## File Map

| Action | File |
|--------|------|
| Modify | `.gitignore` |
| Rewrite | `systemd/ice-gateway.service` |
| Modify | `scripts/01_setup_os.sh` |
| Create | `scripts/02_create_argus.sh` |
| Rename (git mv) | `scripts/02_setup_network.sh` → `scripts/03_setup_network.sh` |
| Rename + modify | `scripts/03_setup_tailscale.sh` → `scripts/04_setup_tailscale.sh` |
| Rename + rewrite | `scripts/04_setup_onewire.sh` → `scripts/05_setup_onewire.sh` |
| Delete | `scripts/05_setup_python.sh` |
| Create | `scripts/06_setup_app.sh` |
| Delete + create | `scripts/06_deploy_app.sh` → `scripts/07_deploy_service.sh` |
| Create | `deploy.sh` |
| Create | `setup.sh` |
| Rewrite | `scripts/00_README.sh` |

---

## Task 1: Update `.gitignore`

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add missing ignores**

Open `.gitignore` and add these lines under the `# Machine config and secrets` section:

```
# Machine config and secrets
config/config.local.toml
config/ice-gateway.env
.env
```

And add under the `# Project runtime` section:

```
# Project runtime — keep directory, ignore contents
data/*.sqlite
data/raw_ksbu/
data/ksbun_*
logs/*.log
logs/*.gz
```

- [ ] **Step 2: Verify syntax**

```bash
bash -n /dev/null   # gitignore has no syntax to check — visually confirm the file looks right
git check-ignore -v config/ice-gateway.env
```

Expected output: `.gitignore:N  config/ice-gateway.env`

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: ignore ice-gateway.env and ksbun tool output in data/"
```

---

## Task 2: Rewrite `systemd/ice-gateway.service`

**Files:**
- Rewrite: `systemd/ice-gateway.service`

- [ ] **Step 1: Replace the service file**

Overwrite `systemd/ice-gateway.service` with:

```ini
[Unit]
Description=Ice Gateway Monitor
Documentation=https://github.com/conradstorz/Scotsman_Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=argus
Group=argus
WorkingDirectory=/home/argus/ice_gateway
EnvironmentFile=/home/argus/ice_gateway/config/ice-gateway.env
Environment="PATH=/home/argus/.local/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/argus/ice_gateway/.venv/bin/ice-gateway
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ice-gateway

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Verify**

```bash
bash -n /dev/null
systemd-analyze verify systemd/ice-gateway.service 2>&1 || true
```

The `systemd-analyze verify` may warn about missing files (argus doesn't exist on the dev machine) — that is expected. Fatal errors are not.

- [ ] **Step 3: Commit**

```bash
git add systemd/ice-gateway.service
git commit -m "fix: run ice-gateway as argus, call venv binary directly"
```

---

## Task 3: Update `scripts/01_setup_os.sh`

**Files:**
- Modify: `scripts/01_setup_os.sh`

- [ ] **Step 1: Add missing packages**

Replace the apt-get install line:

Old:
```bash
apt-get install -y git sqlite3 i2c-tools chrony ufw openssh-server
```

New:
```bash
apt-get install -y git sqlite3 i2c-tools chrony ufw openssh-server \
    curl snmp tftpd-hpa
```

- [ ] **Step 2: Verify syntax**

```bash
bash -n scripts/01_setup_os.sh
```

Expected: no output (clean).

- [ ] **Step 3: Commit**

```bash
git add scripts/01_setup_os.sh
git commit -m "fix: add snmp and tftpd-hpa packages required for KSBU-N tool"
```

---

## Task 4: Create `scripts/02_create_argus.sh`

**Files:**
- Create: `scripts/02_create_argus.sh`

- [ ] **Step 1: Write the script**

Create `scripts/02_create_argus.sh`:

```bash
#!/bin/bash
set -euo pipefail

echo "=== Step 2: Create argus service user ==="

# Create user if not exists
if id "argus" &>/dev/null; then
    echo "argus user already exists — skipping creation"
else
    useradd --create-home --shell /bin/bash \
        --comment "Ice Gateway service account" argus
    echo "argus:scotsman" | chpasswd
    echo "Created argus user with password 'scotsman'"
    echo "NOTE: Change this password after setup for production use."
fi

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

cat > "$SUDOERS_FILE" << EOF
# Ice Gateway — written by 02_create_argus.sh — do not edit manually
# conrad can invoke the argus deploy script without a password
conrad ALL=(argus) NOPASSWD: /home/argus/ice_gateway/deploy.sh

# argus can manage the ice-gateway service
argus ALL=(root) NOPASSWD: $SYSTEMCTL start ice-gateway
argus ALL=(root) NOPASSWD: $SYSTEMCTL stop ice-gateway
argus ALL=(root) NOPASSWD: $SYSTEMCTL restart ice-gateway
EOF

chmod 440 "$SUDOERS_FILE"
visudo -cf "$SUDOERS_FILE"
echo "Wrote and validated sudoers rules: $SUDOERS_FILE"

echo "=== argus user setup complete ==="
```

- [ ] **Step 2: Verify syntax**

```bash
bash -n scripts/02_create_argus.sh
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add scripts/02_create_argus.sh
git commit -m "feat: add script to create argus service user with sudoers rules"
```

---

## Task 5: Rename network script (02 → 03)

**Files:**
- Rename: `scripts/02_setup_network.sh` → `scripts/03_setup_network.sh`

No logic changes needed in this file — it was already correct.

- [ ] **Step 1: Rename with git**

```bash
git mv scripts/02_setup_network.sh scripts/03_setup_network.sh
```

- [ ] **Step 2: Verify**

```bash
bash -n scripts/03_setup_network.sh
ls scripts/
```

Expected: `02_setup_network.sh` is gone, `03_setup_network.sh` is present.

- [ ] **Step 3: Commit**

```bash
git add scripts/
git commit -m "refactor: renumber network script to 03 (02 is now create_argus)"
```

---

## Task 6: Rename and fix Tailscale script (03 → 04)

**Files:**
- Rename + modify: `scripts/03_setup_tailscale.sh` → `scripts/04_setup_tailscale.sh`

- [ ] **Step 1: Rename**

```bash
git mv scripts/03_setup_tailscale.sh scripts/04_setup_tailscale.sh
```

- [ ] **Step 2: Add idempotency check**

Replace the full contents of `scripts/04_setup_tailscale.sh` with:

```bash
#!/bin/bash
set -euo pipefail

echo "=== Step 4: Tailscale Setup ==="

# Install Tailscale if not present
if command -v tailscale &>/dev/null; then
    echo "Tailscale already installed — skipping install"
else
    curl -fsSL https://tailscale.com/install.sh | sh
fi

# Connect only if not already authenticated
if tailscale status &>/dev/null; then
    echo "Tailscale already connected — skipping auth"
    echo "Tailscale IP: $(tailscale ip -4 2>/dev/null || echo 'unknown')"
else
    echo ""
    echo "Enter your Tailscale auth key (https://login.tailscale.com/admin/settings/keys):"
    read -r -s TAILSCALE_AUTH_KEY
    tailscale up --authkey="$TAILSCALE_AUTH_KEY" --hostname="ice-gateway-$(hostname)"
    echo ""
    echo "Tailscale IP: $(tailscale ip -4 2>/dev/null || echo 'pending')"
fi

echo "=== Tailscale setup complete ==="
```

- [ ] **Step 3: Verify syntax**

```bash
bash -n scripts/04_setup_tailscale.sh
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add scripts/
git commit -m "fix: renumber tailscale to 04, add idempotency check for existing connection"
```

---

## Task 7: Rename and strip One-Wire script (04 → 05)

**Files:**
- Rename + rewrite: `scripts/04_setup_onewire.sh` → `scripts/05_setup_onewire.sh`

Sensor registration moves to Task 9 (`06_setup_app.sh`) because the argus clone does not exist until that step.

- [ ] **Step 1: Rename**

```bash
git mv scripts/04_setup_onewire.sh scripts/05_setup_onewire.sh
```

- [ ] **Step 2: Rewrite to hardware-only**

Replace the full contents of `scripts/05_setup_onewire.sh` with:

```bash
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
```

- [ ] **Step 3: Verify syntax**

```bash
bash -n scripts/05_setup_onewire.sh
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add scripts/
git commit -m "refactor: renumber onewire to 05, move sensor registration to 06_setup_app"
```

---

## Task 8: Delete old Python and deploy scripts

**Files:**
- Delete: `scripts/05_setup_python.sh`
- Delete: `scripts/06_deploy_app.sh`

Both are replaced by Task 9 and Task 10.

- [ ] **Step 1: Delete**

```bash
git rm scripts/05_setup_python.sh scripts/06_deploy_app.sh
```

- [ ] **Step 2: Commit**

```bash
git commit -m "remove: delete old python setup and deploy scripts (replaced by 06_setup_app and 07_deploy_service)"
```

---

## Task 9: Create `scripts/06_setup_app.sh`

**Files:**
- Create: `scripts/06_setup_app.sh`

This script clones the repo as `argus`, installs uv as `argus`, runs `uv sync`, creates config files, and registers any detected sensors.

- [ ] **Step 1: Write the script**

Create `scripts/06_setup_app.sh`:

```bash
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
```

- [ ] **Step 2: Verify syntax**

```bash
bash -n scripts/06_setup_app.sh
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add scripts/06_setup_app.sh
git commit -m "feat: add 06_setup_app — clone as argus, install uv, sync, register sensors"
```

---

## Task 10: Create `scripts/07_deploy_service.sh`

**Files:**
- Create: `scripts/07_deploy_service.sh`

- [ ] **Step 1: Write the script**

Create `scripts/07_deploy_service.sh`:

```bash
#!/bin/bash
set -euo pipefail

echo "=== Step 7: Deploy systemd service ==="

APP_DIR="/home/argus/ice_gateway"
SERVICE_SRC="$APP_DIR/systemd/ice-gateway.service"
SERVICE_DEST="/etc/systemd/system/ice-gateway.service"

if [ ! -f "$SERVICE_SRC" ]; then
    echo "ERROR: service file not found at $SERVICE_SRC" >&2
    echo "Run 06_setup_app.sh first." >&2
    exit 1
fi

cp "$SERVICE_SRC" "$SERVICE_DEST"
systemctl daemon-reload
systemctl enable ice-gateway
systemctl restart ice-gateway

echo ""
echo "=== Service deployed ==="
systemctl status ice-gateway --no-pager
```

- [ ] **Step 2: Verify syntax**

```bash
bash -n scripts/07_deploy_service.sh
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add scripts/07_deploy_service.sh
git commit -m "feat: add 07_deploy_service — installs and starts ice-gateway systemd service"
```

---

## Task 11: Create `deploy.sh`

**Files:**
- Create: `deploy.sh`

This is the day-to-day update script. It re-execs as `argus` if called as anyone else.

- [ ] **Step 1: Write the script**

Create `deploy.sh` at the repo root:

```bash
#!/bin/bash
set -euo pipefail

# Self-correcting: if not running as argus, re-exec as argus.
# Use realpath so the absolute path survives being called from any directory.
SELF="$(realpath "$0")"
if [ "$(whoami)" != "argus" ]; then
    exec sudo -u argus "$SELF" "$@"
fi

APP_DIR="/home/argus/ice_gateway"

echo "=== Deploying ice-gateway ==="
echo "Before: $(git -C "$APP_DIR" rev-parse --short HEAD)"

git -C "$APP_DIR" pull --ff-only
cd "$APP_DIR"
/home/argus/.local/bin/uv sync --no-dev

echo "After:  $(git -C "$APP_DIR" rev-parse --short HEAD)"
echo "Restarting service..."

sudo systemctl restart ice-gateway
systemctl status ice-gateway --no-pager
```

- [ ] **Step 2: Make it executable and verify syntax**

```bash
chmod +x deploy.sh
bash -n deploy.sh
```

Expected: no output from `bash -n`.

- [ ] **Step 3: Commit**

```bash
git add deploy.sh
git commit -m "feat: add self-correcting deploy.sh — always runs as argus"
```

---

## Task 12: Create `setup.sh`

**Files:**
- Create: `setup.sh`

The single orchestrator. Detects repo URL from git remote so it works for any fork.

- [ ] **Step 1: Write the script**

Create `setup.sh` at the repo root:

```bash
#!/bin/bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: Run as root: sudo bash setup.sh" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect the repo URL from the git remote — works for any fork
REPO_URL="$(git -C "$SCRIPT_DIR" remote get-url origin 2>/dev/null || echo '')"
if [ -z "$REPO_URL" ]; then
    echo "ERROR: Could not read git remote URL." >&2
    echo "Make sure you cloned the repo before running setup.sh." >&2
    exit 1
fi

echo "=== Ice Gateway Setup ==="
echo "Repo: $REPO_URL"
echo ""

run_step() {
    local name="$1"
    shift
    echo ">>> $name"
    if bash "$@"; then
        echo "    OK: $name"
    else
        echo "    FAILED: $name — aborting"
        exit 1
    fi
    echo ""
}

run_step "OS packages"       "$SCRIPT_DIR/scripts/01_setup_os.sh"
run_step "argus user"        "$SCRIPT_DIR/scripts/02_create_argus.sh"
run_step "Network"           "$SCRIPT_DIR/scripts/03_setup_network.sh"
run_step "Tailscale"         "$SCRIPT_DIR/scripts/04_setup_tailscale.sh"
run_step "One-Wire hardware" "$SCRIPT_DIR/scripts/05_setup_onewire.sh"
run_step "App install"       "$SCRIPT_DIR/scripts/06_setup_app.sh" "$REPO_URL"
run_step "Systemd service"   "$SCRIPT_DIR/scripts/07_deploy_service.sh"

echo "=== Setup complete. Next steps ==="
echo ""
echo "  1. Cable KSBU-N to eth0 and reboot"
echo "  2. Edit /home/argus/ice_gateway/config/config.local.toml"
echo "     (set site_name, ksbu_device_ip, sensor names)"
echo "  3. sudo systemctl restart ice-gateway"
echo ""
echo "  Verify:"
echo "    systemctl status ice-gateway"
echo "    tailscale status"
echo "    ls /sys/bus/w1/devices/"
echo "    curl http://localhost:8080/api/health"
```

- [ ] **Step 2: Make executable and verify syntax**

```bash
chmod +x setup.sh
bash -n setup.sh
```

Expected: no output from `bash -n`.

- [ ] **Step 3: Commit**

```bash
git add setup.sh
git commit -m "feat: add setup.sh orchestrator — single command bare-Pi provisioning"
```

---

## Task 13: Rewrite `scripts/00_README.sh`

**Files:**
- Rewrite: `scripts/00_README.sh`

- [ ] **Step 1: Rewrite with updated paths and script names**

Replace the full contents of `scripts/00_README.sh` with:

```bash
#!/bin/bash
cat << 'EOF'
=== Ice Gateway Setup Guide ===

--- BEFORE YOU BEGIN: Tailscale credentials ---

Script 04 will prompt for a Tailscale auth key. Get one first:

  1. Create a Tailscale account at https://tailscale.com
  2. Go to Settings → Keys → Generate auth key
     https://login.tailscale.com/admin/settings/keys
  3. Recommended settings:
       Reusable:  No   (one-time key)
       Expiry:    90 days
       Ephemeral: No   (Pi must persist after reboots)
  4. Copy the key (starts with tskey-auth-...).
     Script 04 will prompt for it interactively and does not store it.

--- Bootstrap (run on a fresh Raspberry Pi OS 64-bit install) ---

  git clone https://github.com/<YOUR_GITHUB_USERNAME>/Scotsman_Monitor
  cd Scotsman_Monitor
  sudo bash setup.sh

setup.sh calls these scripts in order (all run as root):

  scripts/01_setup_os.sh        Update OS, install base packages (snmp, tftpd-hpa, etc.)
  scripts/02_create_argus.sh    Create 'argus' service user, set groups, write sudoers
  scripts/03_setup_network.sh   Static IP + DHCP server on eth0, UFW firewall
  scripts/04_setup_tailscale.sh Install Tailscale (prompts for auth key once)
  scripts/05_setup_onewire.sh   Enable DS18B20 1-wire hardware (dtoverlay + modprobe)
  scripts/06_setup_app.sh       Clone repo as argus, install uv, sync deps, register sensors
  scripts/07_deploy_service.sh  Install and start the ice-gateway systemd service

--- Network layout after script 03 ---

  wlan0  — DHCP from site router, internet access, Tailscale
  eth0   — 192.168.50.1/24, Pi is DHCP server, KSBU-N connects here

--- Service account ---

  User:     argus
  Password: scotsman  (change this for production)
  Home:     /home/argus/
  App:      /home/argus/ice_gateway/

--- After setup ---

  1. Cable the KSBU-N to eth0 and reboot
  2. Discover the KSBU-N IP:  arp -n
  3. Edit /home/argus/ice_gateway/config/config.local.toml
       - Set ksbu_device_ip to the discovered address
       - Set site_name and machine_name
       - Update sensor name/location entries
  4. Add any secrets to /home/argus/ice_gateway/config/ice-gateway.env
  5. sudo systemctl restart ice-gateway

--- Verify ---

  systemctl status ice-gateway
  tailscale status
  ls /sys/bus/w1/devices/
  curl http://localhost:8080/api/health

--- Day-to-day deployment ---

  Pull the latest code and restart:
    ./deploy.sh          (runs as argus automatically, even if called as conrad)

EOF

echo ""
echo "Checking repository files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

for f in setup.sh deploy.sh; do
    if [ -f "$PROJECT_DIR/$f" ]; then
        echo "  OK  $f"
    else
        echo "  MISSING  $f"
    fi
done

for f in 01_setup_os.sh 02_create_argus.sh 03_setup_network.sh \
          04_setup_tailscale.sh 05_setup_onewire.sh \
          06_setup_app.sh 07_deploy_service.sh; do
    if [ -f "$PROJECT_DIR/scripts/$f" ]; then
        echo "  OK  scripts/$f"
    else
        echo "  MISSING  scripts/$f"
    fi
done
```

- [ ] **Step 2: Verify syntax**

```bash
bash -n scripts/00_README.sh
```

Expected: no output.

- [ ] **Step 3: Run it to confirm the checklist output looks right**

```bash
bash scripts/00_README.sh
```

Expected: prints the guide, then lists all scripts as `OK` (since they all exist after Tasks 1-12).

- [ ] **Step 4: Commit**

```bash
git add scripts/00_README.sh
git commit -m "docs: update README script for argus user layout and new script numbering"
```

---

## Task 14: Final verification

- [ ] **Step 1: Confirm all old scripts are gone**

```bash
ls scripts/
```

Expected: `00_README.sh  01_setup_os.sh  02_create_argus.sh  03_setup_network.sh  04_setup_tailscale.sh  05_setup_onewire.sh  06_setup_app.sh  07_deploy_service.sh`

No `05_setup_python.sh` or `06_deploy_app.sh`.

- [ ] **Step 2: Syntax-check every script**

```bash
for f in setup.sh deploy.sh scripts/*.sh; do
    bash -n "$f" && echo "OK: $f" || echo "FAIL: $f"
done
```

Expected: `OK` for every file.

- [ ] **Step 3: Confirm git log tells the story**

```bash
git log --oneline -14
```

Expected: 14 commits matching the tasks above, from `chore: ignore...` through `docs: update README...`.

- [ ] **Step 4: Run `00_README.sh` as final smoke test**

```bash
bash scripts/00_README.sh
```

Expected: all files listed as `OK`, none `MISSING`.
