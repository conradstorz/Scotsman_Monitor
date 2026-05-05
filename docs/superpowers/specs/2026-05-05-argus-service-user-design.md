# Argus Service User & Autonomous Operation Design

**Date:** 2026-05-05
**Status:** Approved

## Overview

Replace the current root-owned `/opt/ice_gateway` layout with a dedicated `argus` service user
whose home directory contains everything the application needs. This eliminates the root-owned
venv problem and gives the system a clear, autonomous operating identity.

The name `argus` comes from Greek mythology — the hundred-eyed giant who never slept, the
archetype of the tireless watcher.

---

## 1. The `argus` User & Ownership Model

### Account

| Property | Value |
|----------|-------|
| Username | `argus` |
| Password | `scotsman` (hardcoded for now; a future iteration will accept it as a prompt or env var at setup time) |
| Home | `/home/argus` |
| Shell | `/bin/bash` |
| Groups | `gpio`, `i2c`, `dialout` |

Groups cover: DS18B20 1-wire (GPIO4), UPS HAT (I2C), future NAFEM serial (dialout).

### Ownership guarantee

Every file under `/home/argus/` is owned by `argus`. This is enforced structurally, not by
operator discipline.

Every script that touches the app directory carries this self-correcting header:

```bash
if [ "$(whoami)" != "argus" ]; then
    exec sudo -u argus "$0" "$@"
fi
```

Running a script as `root` or `conrad` silently re-executes it as `argus`. Files can never be
created under the wrong owner.

### Sudoers rules

Written to `/etc/sudoers.d/ice-gateway` by `02_create_argus.sh`:

```
# conrad can invoke argus-owned scripts without a password prompt
conrad ALL=(argus) NOPASSWD: /home/argus/ice_gateway/deploy.sh

# argus can manage the service (needed by deploy.sh)
argus ALL=(root) NOPASSWD: /bin/systemctl start ice-gateway
argus ALL=(root) NOPASSWD: /bin/systemctl stop ice-gateway
argus ALL=(root) NOPASSWD: /bin/systemctl restart ice-gateway
```

`conrad` never writes into `/home/argus` directly. The only privileged action `argus` performs
is `systemctl restart`.

---

## 2. App Layout

```
/home/argus/
├── .local/bin/uv                  ← uv installed for argus
└── ice_gateway/                   ← git clone of the public repo
    ├── .venv/                     ← created by uv sync, owned by argus
    ├── src/ice_gateway/           ← application source
    ├── config/
    │   ├── config.example.toml    ← in git, template
    │   ├── config.local.toml      ← created by setup, git-ignored, edit here
    │   └── ice-gateway.env        ← secrets, git-ignored (from .env.example)
    ├── data/                      ← SQLite db, raw KSBU snapshots (git-ignored)
    ├── logs/                      ← Loguru output (git-ignored)
    ├── systemd/
    │   └── ice-gateway.service
    ├── scripts/
    │   └── 01..07_*.sh
    ├── deploy.sh                  ← self-correcting deployment script
    └── setup.sh                   ← orchestrator for bare-Pi provisioning
```

### Changes from current layout

| Before | After |
|--------|-------|
| `/opt/ice_gateway/` | `/home/argus/ice_gateway/` |
| `/etc/ice-gateway/ice-gateway.env` | `config/ice-gateway.env` (argus-owned) |
| `User=pi` in service | `User=argus` |
| `uv run ice-gateway` in ExecStart | `/home/argus/ice_gateway/.venv/bin/ice-gateway` |
| venv owned by root | venv owned by argus from first `uv sync` |

### Systemd service

```ini
[Unit]
Description=Ice Gateway Monitor
Documentation=https://github.com/conradstorz/Scotsman_Monitor  # update to actual repo URL
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

`ExecStart` calls the venv binary directly — `uv` is never invoked at runtime, so the service
never attempts to modify the venv and can never create root-owned files.

---

## 3. Bootstrap Sequence

### Initial setup (bare Pi)

```bash
git clone https://github.com/conradstorz/Scotsman_Monitor   # replace with actual repo URL
sudo bash Scotsman_Monitor/setup.sh
```

### `setup.sh` orchestration

Runs as root. Calls each numbered script in order. Stops immediately on failure.

```
01_setup_os.sh        root    apt packages (adds snmp, tftpd-hpa, curl)
02_create_argus.sh    root    create argus user, password, groups, sudoers
03_setup_network.sh   root    static IP + DHCP on eth0, UFW rules
04_setup_tailscale.sh root    install Tailscale, prompt for auth key (idempotent)
05_setup_onewire.sh   root    dtoverlay + modprobe only (hardware, no config writes)
06_setup_app.sh       root    clone repo as argus, install uv as argus, uv sync,
                              create config.local.toml, register discovered sensors
07_deploy_service.sh  root    install systemd service, enable, start
```

`06_setup_app.sh` uses `sudo -u argus` for all file-creating operations so the repo, uv, and
venv are argus-owned from their first moment of existence.

Sensor registration moves from step 05 into step 06 because the argus clone does not exist
until step 06. Step 05 only touches hardware (kernel modules and boot overlay) — no file writes
into the app directory.

### `setup.sh` structure

```bash
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

run_step() {
    local name="$1" script="$2"
    echo ""
    echo ">>> $name"
    bash "$SCRIPT_DIR/scripts/$script" \
        && echo "    OK: $name" \
        || { echo "    FAILED: $name — aborting"; exit 1; }
}

run_step "OS packages"       01_setup_os.sh
run_step "argus user"        02_create_argus.sh
run_step "Network"           03_setup_network.sh
run_step "Tailscale"         04_setup_tailscale.sh
run_step "One-Wire sensors"  05_setup_onewire.sh
run_step "App install"       06_setup_app.sh
run_step "Systemd service"   07_deploy_service.sh

echo ""
echo "=== Setup complete. Next steps ==="
echo "  1. Cable KSBU-N to eth0 and reboot"
echo "  2. Edit /home/argus/ice_gateway/config/config.local.toml"
echo "  3. sudo systemctl restart ice-gateway"
```

---

## 4. Deployment Workflow (post-setup)

### `deploy.sh` (self-correcting)

```bash
#!/bin/bash
set -euo pipefail

if [ "$(whoami)" != "argus" ]; then
    exec sudo -u argus "$0" "$@"
fi

APP_DIR="/home/argus/ice_gateway"

echo "=== Deploying ice-gateway ==="
echo "Commit before: $(git -C "$APP_DIR" rev-parse --short HEAD)"

git -C "$APP_DIR" pull
/home/argus/.local/bin/uv sync --project "$APP_DIR"

echo "Commit after:  $(git -C "$APP_DIR" rev-parse --short HEAD)"
echo "Restarting service..."

sudo systemctl restart ice-gateway
systemctl status ice-gateway --no-pager
```

`conrad` runs `./deploy.sh` (or `sudo -u argus ./deploy.sh`) — ownership is correct either way.

---

## 5. Script-by-Script Changes from Current State

### `01_setup_os.sh`
- Add `snmp tftpd-hpa curl` to apt install line

### `02_create_argus.sh` (new)
- `useradd` with home, shell, groups
- `chpasswd` to set `scotsman`
- Write `/etc/sudoers.d/ice-gateway`

### `03_setup_network.sh` (was `02`)
- No logic changes; UFW reset remains (acceptable for this project)

### `04_setup_tailscale.sh` (was `03`)
- Add idempotency check: skip `tailscale up` if already connected

### `05_setup_onewire.sh` (was `04`, hardware only)
- dtoverlay write to `/boot/firmware/config.txt` (idempotent check)
- `modprobe w1-gpio w1-therm`
- No config file writes — sensor registration moves to step 06

### `06_setup_app.sh` (replaces old `05` + `06`)
- `sudo -u argus git clone <actual-repo-url> /home/argus/ice_gateway` (skip if dir exists)
- `sudo -u argus curl -LsSf https://astral.sh/uv/install.sh | sh` to install uv for argus
- `sudo -u argus /home/argus/.local/bin/uv sync --project /home/argus/ice_gateway`
- `sudo -u argus cp config.example.toml config.local.toml` if missing
- `sudo -u argus cp .env.example config/ice-gateway.env` if missing
- Discover `/sys/bus/w1/devices/28-*` and register any new sensors into `config.local.toml` as argus

### `07_deploy_service.sh` (was `06`, simplified)
- Copy service file, `daemon-reload`, `enable`, `systemctl restart` (not `start`)

### `systemd/ice-gateway.service`
- `User=argus`, `Group=argus`
- `PATH=/home/argus/.local/bin:...`
- `ExecStart=/home/argus/ice_gateway/.venv/bin/ice-gateway`
- `EnvironmentFile=/home/argus/ice_gateway/config/ice-gateway.env`

---

## 6. Idempotency Summary

| Script | Re-run safe? | Notes |
|--------|-------------|-------|
| `01_setup_os.sh` | Yes | apt idempotent |
| `02_create_argus.sh` | Yes | check `id argus` before useradd; overwrite sudoers is safe |
| `03_setup_network.sh` | Mostly | UFW reset wipes manual rules (acceptable) |
| `04_setup_tailscale.sh` | Yes | skips auth if already connected |
| `05_setup_onewire.sh` | Yes | all steps guarded |
| `06_setup_app.sh` | Yes | skip clone if dir exists; uv sync always idempotent |
| `07_deploy_service.sh` | Yes | restart instead of start |
| `deploy.sh` | Yes | git pull + uv sync + restart |
