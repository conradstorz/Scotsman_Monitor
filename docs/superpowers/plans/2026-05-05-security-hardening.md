# Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all Critical, Important, and Minor security issues identified in the Phase 1 review, baked into idempotent setup scripts and production source files.

**Architecture:** In-place edits to existing scripts and Python source — no new scripts. Every change is idempotent: safe to re-run on an already-configured Pi. Shell script changes are verified by inspecting the resulting configuration; Python changes follow TDD.

**Tech Stack:** bash, ufw, systemd, Tailscale apt repo, GPG, uv (pinned binary), Python 3.13, SQLAlchemy, Loguru, gitleaks pre-commit hook.

---

## File Map

| File | Tasks |
|---|---|
| `scripts/01_setup_os.sh` | Task 1 |
| `scripts/02_create_argus.sh` | Task 2 |
| `scripts/03_setup_network.sh` | Task 3 |
| `scripts/04_setup_tailscale.sh` | Task 4 |
| `scripts/06_setup_app.sh` | Task 5 |
| `scripts/07_deploy_service.sh` | Task 6 |
| `systemd/ice-gateway.service` | Task 7 |
| `src/ice_gateway/logging_setup.py` | Task 8 |
| `src/ice_gateway/database.py` | Task 9 |
| `.pre-commit-config.yaml` (new) | Task 10 |
| `pyproject.toml` | Task 10 |
| `tools/scotsman_ksbun_tool.py` (moved) | Task 11 |

---

### Task 1: OS hardening — remove attack surface, harden SSH (I3, I5, I6)

**Files:**
- Modify: `scripts/01_setup_os.sh`

Context: `01_setup_os.sh` currently installs `snmp` and `tftpd-hpa` (unneeded, both open network listeners), does not harden sshd, and does not regenerate the Pi OS image's shared host keys.

- [ ] **Step 1: Remove snmp and tftpd-hpa from the install list**

In `scripts/01_setup_os.sh`, find the `apt-get install` block and replace it:

```bash
# Before:
apt-get install -y git sqlite3 i2c-tools chrony ufw openssh-server \
    curl snmp tftpd-hpa unattended-upgrades

# After:
apt-get install -y git sqlite3 i2c-tools chrony ufw openssh-server \
    curl unattended-upgrades
```

- [ ] **Step 2: Add purge block immediately after the install line**

After the `apt-get install` line and before `timedatectl`, add:

```bash
# Purge unneeded network listeners if present from prior runs (idempotent)
apt-get purge -y --auto-remove snmp tftpd-hpa 2>/dev/null || true
```

- [ ] **Step 3: Add SSH host key regeneration block**

After the `systemctl enable ssh` / `systemctl start ssh` lines, add:

```bash
# Regenerate SSH host keys — Pi OS images ship with shared keys.
# Marker file prevents rotation on re-runs (which would break known_hosts).
HOSTKEY_MARKER="/etc/ssh/.host-keys-regenerated"
if [ ! -f "$HOSTKEY_MARKER" ]; then
    rm -f /etc/ssh/ssh_host_*
    dpkg-reconfigure openssh-server
    touch "$HOSTKEY_MARKER"
    echo "SSH host keys regenerated"
else
    echo "SSH host keys already regenerated — skipping"
fi
```

- [ ] **Step 4: Add sshd hardening drop-in immediately after the host key block**

```bash
# Write sshd hardening config — drop-in avoids editing sshd_config directly.
# Idempotent: overwriting the file with the same content is safe.
cat > /etc/ssh/sshd_config.d/99-ice-gateway-hardening.conf << 'EOF'
# Ice Gateway SSH hardening — written by 01_setup_os.sh — do not edit manually
PasswordAuthentication no
PermitRootLogin no
X11Forwarding no
AllowAgentForwarding no
MaxAuthTries 3
LoginGraceTime 20
EOF
chmod 644 /etc/ssh/sshd_config.d/99-ice-gateway-hardening.conf
sshd -t   # validate combined config — fails fast before restarting
systemctl restart ssh
echo "sshd hardening applied and service restarted"
```

- [ ] **Step 5: Verify the edits look correct**

```bash
grep -n "snmp\|tftpd" scripts/01_setup_os.sh
```

Expected: no output (both packages removed).

```bash
grep -n "host-keys-regenerated\|PasswordAuthentication\|sshd -t" scripts/01_setup_os.sh
```

Expected: three matching lines present.

- [ ] **Step 6: Commit**

```bash
git add scripts/01_setup_os.sh
git commit -m "security: harden 01_setup_os.sh — remove snmp/tftpd-hpa, regenerate SSH host keys, add sshd drop-in"
```

---

### Task 2: Update sudoers deploy rule to root-owned path (I4 — part 1)

**Files:**
- Modify: `scripts/02_create_argus.sh`

Context: The sudoers rule currently grants the deploy user permission to run `/home/argus/ice_gateway/deploy.sh` as `argus`. Since `argus` owns that file, argus can rewrite it then invoke it via sudo — a privilege escalation path. The fix points the rule to `/usr/local/sbin/ice-gateway-deploy` (root-owned, placed there by Task 6) and changes the run-as principal to `root`.

- [ ] **Step 1: Update the DEPLOY_RULE line in 02_create_argus.sh**

Find:
```bash
DEPLOY_RULE="${DEPLOY_USER} ALL=(argus) NOPASSWD: /home/argus/ice_gateway/deploy.sh"
```

Replace with:
```bash
DEPLOY_RULE="${DEPLOY_USER} ALL=(root) NOPASSWD: /usr/local/sbin/ice-gateway-deploy"
```

- [ ] **Step 2: Update the fallback comment line**

Find:
```bash
DEPLOY_RULE="# No invoking user detected — add manually: <user> ALL=(argus) NOPASSWD: /home/argus/ice_gateway/deploy.sh"
```

Replace with:
```bash
DEPLOY_RULE="# No invoking user detected — add manually: <user> ALL=(root) NOPASSWD: /usr/local/sbin/ice-gateway-deploy"
```

- [ ] **Step 3: Update the echo message**

Find:
```bash
echo "  Personal deploy rule: $DEPLOY_USER can invoke deploy.sh as argus"
```

Replace with:
```bash
echo "  Personal deploy rule: $DEPLOY_USER can invoke ice-gateway-deploy as root"
```

- [ ] **Step 4: Verify**

```bash
grep -n "DEPLOY_RULE\|ice-gateway-deploy\|/home/argus/ice_gateway/deploy" scripts/02_create_argus.sh
```

Expected: all three `DEPLOY_RULE` references point to `/usr/local/sbin/ice-gateway-deploy`; no reference to the old in-repo path.

- [ ] **Step 5: Commit**

```bash
git add scripts/02_create_argus.sh
git commit -m "security: update sudoers deploy rule to root-owned /usr/local/sbin/ice-gateway-deploy"
```

---

### Task 3: Scope firewall rules to correct interfaces (C1 — part 1)

**Files:**
- Modify: `scripts/03_setup_network.sh`

Context: `ufw allow ssh` and `ufw allow 8080/tcp` both open on **all** interfaces including `wlan0`. SSH must stay open on all interfaces in this step (step 04 locks it down after Tailscale is confirmed). Port 8080 should only be reachable on the LAN (`eth0`) and Tailscale (`tailscale0`).

- [ ] **Step 1: Replace the broad firewall rules in 03_setup_network.sh**

Find the firewall block:
```bash
# Firewall
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 8080/tcp comment 'Ice Gateway Dashboard'
ufw --force enable
```

Replace with:
```bash
# Firewall
ufw --force reset
ufw default deny incoming
ufw default allow outgoing

# SSH stays open on all interfaces here — locked to tailscale0+eth0 in 04_setup_tailscale.sh
# after Tailscale is confirmed connected (locking before that risks an SSH lockout).
ufw allow ssh

# Dashboard: LAN (eth0) and Tailscale only — never exposed on wlan0
ufw allow in on eth0 to any port 8080 proto tcp comment 'Ice Gateway Dashboard (LAN)'
ufw allow in on tailscale0 to any port 8080 proto tcp comment 'Ice Gateway Dashboard (Tailscale)'

ufw --force enable
```

- [ ] **Step 2: Verify the broad 8080 rule is gone**

```bash
grep -n "8080" scripts/03_setup_network.sh
```

Expected: two lines matching `eth0` and `tailscale0` — no bare `ufw allow 8080/tcp`.

- [ ] **Step 3: Commit**

```bash
git add scripts/03_setup_network.sh
git commit -m "security: scope dashboard port 8080 to eth0+tailscale0 only in ufw rules"
```

---

### Task 4: Tailscale — GPG apt repo, SSH lockdown, ACL tags (C1 part 2, C2 part 1, I7)

**Files:**
- Modify: `scripts/04_setup_tailscale.sh`

Context: Three changes in one script. (1) Replace `curl | sh` with the official GPG apt repo. (2) After Tailscale connects, narrow SSH to `tailscale0` + `eth0` only. (3) Add `--advertise-tags=tag:ice-gateway` so Tailscale ACLs can target this node type.

- [ ] **Step 1: Replace the curl|sh install block with the GPG apt repo method**

Find:
```bash
# Install Tailscale if not present
if command -v tailscale &>/dev/null; then
    echo "Tailscale already installed — skipping install"
else
    curl -fsSL https://tailscale.com/install.sh | sh
fi
```

Replace with:
```bash
# Install Tailscale via GPG-verified apt repo — no curl-pipe-sh
if command -v tailscale &>/dev/null; then
    echo "Tailscale already installed — skipping install"
else
    curl -fsSL https://pkgs.tailscale.com/stable/debian/bookworm.gpg \
        | gpg --dearmor -o /usr/share/keyrings/tailscale-archive-keyring.gpg
    cat > /etc/apt/sources.list.d/tailscale.list << 'EOF'
deb [signed-by=/usr/share/keyrings/tailscale-archive-keyring.gpg] https://pkgs.tailscale.com/stable/debian bookworm main
EOF
    apt-get update -qq
    apt-get install -y tailscale
    echo "Tailscale installed via apt"
fi
```

- [ ] **Step 2: Add --advertise-tags to the tailscale up call**

Find:
```bash
    tailscale up --authkey="$TAILSCALE_AUTH_KEY" --hostname="ice-gateway-$(hostname)"
```

Replace with:
```bash
    # REQUIREMENT: auth key must be pre-authorized for tag:ice-gateway in
    # Tailscale admin → Keys → Generate auth key → add tag:ice-gateway
    tailscale up \
        --authkey="$TAILSCALE_AUTH_KEY" \
        --hostname="ice-gateway-$(hostname)" \
        --advertise-tags=tag:ice-gateway
```

- [ ] **Step 3: Add SSH lockdown block after the fi that closes the auth section**

After the closing `fi` of the `tailscale status` block (just before `echo "=== Tailscale setup complete ==="`), add:

```bash
# Lock SSH to eth0 + tailscale0 only — safe now that Tailscale is confirmed up.
# Idempotent: delete is || true in case the broad rule was already removed.
ufw delete allow ssh 2>/dev/null || true
ufw allow in on eth0 to any port 22 proto tcp comment 'SSH (LAN)'
ufw allow in on tailscale0 to any port 22 proto tcp comment 'SSH (Tailscale)'
ufw reload
echo "SSH access locked to eth0 + tailscale0"
```

- [ ] **Step 4: Verify the old curl|sh line is gone**

```bash
grep -n "tailscale.com/install.sh\|curl.*install.sh" scripts/04_setup_tailscale.sh
```

Expected: no output.

```bash
grep -n "advertise-tags\|bookworm.gpg\|ufw delete allow ssh" scripts/04_setup_tailscale.sh
```

Expected: three matching lines.

- [ ] **Step 5: Commit**

```bash
git add scripts/04_setup_tailscale.sh
git commit -m "security: Tailscale GPG apt repo, SSH interface lockdown post-connect, ACL tags"
```

---

### Task 5: App setup — pin uv binary, secure env file (C2 part 2, I2)

**Files:**
- Modify: `scripts/06_setup_app.sh`

Context: (1) `curl | sh` for uv is replaced with a pinned binary download from GitHub releases, verified against its published SHA256. (2) `ice-gateway.env` is created but never chmod'd — any local user can read it.

The Pi 4 is ARM64 (`aarch64`). uv releases publish a `uv-aarch64-unknown-linux-musl.tar.gz` and a matching `.sha256` file. We download both and verify.

- [ ] **Step 1: Replace the uv install block with the pinned binary approach**

Find:
```bash
# Install uv for argus if not present
if [ -f "/home/argus/.local/bin/uv" ]; then
    echo "uv already installed for argus — skipping"
else
    sudo -u argus bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
    echo "Installed uv for argus"
fi
```

Replace with:
```bash
# Install uv for argus if not present — pinned binary from GitHub releases with SHA256 verify.
# To update: change UV_VERSION and re-run. The .sha256 file is fetched from the same release.
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
```

- [ ] **Step 2: Add chmod 600 immediately after the env file is created**

Find:
```bash
if [ ! -f "$APP_DIR/config/ice-gateway.env" ]; then
    sudo -u argus cp "$APP_DIR/.env.example" \
        "$APP_DIR/config/ice-gateway.env"
    echo "Created ice-gateway.env — edit $APP_DIR/config/ice-gateway.env to add secrets"
else
    echo "ice-gateway.env already exists — skipping"
fi
```

Replace with:
```bash
if [ ! -f "$APP_DIR/config/ice-gateway.env" ]; then
    sudo -u argus cp "$APP_DIR/.env.example" \
        "$APP_DIR/config/ice-gateway.env"
    chmod 600 "$APP_DIR/config/ice-gateway.env"
    echo "Created ice-gateway.env (mode 600) — edit $APP_DIR/config/ice-gateway.env to add secrets"
else
    echo "ice-gateway.env already exists — skipping"
fi
```

- [ ] **Step 3: Verify the old curl|sh line is gone**

```bash
grep -n "astral.sh/uv/install.sh\|curl.*install.sh" scripts/06_setup_app.sh
```

Expected: no output.

```bash
grep -n "sha256sum\|chmod 600.*ice-gateway.env" scripts/06_setup_app.sh
```

Expected: two matching lines.

- [ ] **Step 4: Commit**

```bash
git add scripts/06_setup_app.sh
git commit -m "security: pin uv to verified binary download, chmod 600 ice-gateway.env"
```

---

### Task 6: Publish root-owned deploy script (I4 — part 2)

**Files:**
- Modify: `scripts/07_deploy_service.sh`

Context: `02_create_argus.sh` (Task 2) points the sudoers rule to `/usr/local/sbin/ice-gateway-deploy`. This task makes `07_deploy_service.sh` actually install it there. The file is owned root:root so `argus` cannot modify the script it can invoke via sudo.

- [ ] **Step 1: Add the deploy script installation block at the end of 07_deploy_service.sh**

After the final `systemctl status` lines and before the closing `echo "=== Services deployed ==="`, add:

```bash
# Install root-owned deploy script — sudoers rule points here (not the in-repo copy).
# argus cannot modify /usr/local/sbin, so this prevents privilege escalation via
# sudo + writable script.
DEPLOY_TARGET="/usr/local/sbin/ice-gateway-deploy"
cp "$APP_DIR/deploy.sh" "$DEPLOY_TARGET"
chown root:root "$DEPLOY_TARGET"
chmod 755 "$DEPLOY_TARGET"
echo "Deploy script installed at $DEPLOY_TARGET (root-owned)"
echo "NOTE: re-run this step after any changes to deploy.sh"
```

- [ ] **Step 2: Verify**

```bash
grep -n "ice-gateway-deploy\|/usr/local/sbin" scripts/07_deploy_service.sh
```

Expected: lines referencing `DEPLOY_TARGET` and `/usr/local/sbin/ice-gateway-deploy`.

- [ ] **Step 3: Commit**

```bash
git add scripts/07_deploy_service.sh
git commit -m "security: install root-owned deploy script to /usr/local/sbin/ice-gateway-deploy"
```

---

### Task 7: Systemd sandboxing (I1)

**Files:**
- Modify: `systemd/ice-gateway.service`

Context: The service file has no isolation directives. A compromised process runs with full argus privileges and can read/write anywhere argus can. The sandboxing directives below constrain what it can do without breaking normal operation.

Current `[Service]` section ends at `SyslogIdentifier=ice-gateway`. The new directives go after that line, before `[Install]`.

- [ ] **Step 1: Add sandboxing directives to ice-gateway.service**

Open `systemd/ice-gateway.service`. After the line `SyslogIdentifier=ice-gateway`, add:

```ini
# Sandboxing — constrains blast radius if the process is compromised
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
RestrictNamespaces=true
LockPersonality=true
MemoryDenyWriteExecute=true
# Allow writes only to the paths the app actually uses
ReadWritePaths=/home/argus/ice_gateway/data /home/argus/ice_gateway/logs /run
```

The full file after editing:

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

# Sandboxing — constrains blast radius if the process is compromised
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
RestrictNamespaces=true
LockPersonality=true
MemoryDenyWriteExecute=true
ReadWritePaths=/home/argus/ice_gateway/data /home/argus/ice_gateway/logs /run

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Verify key directives are present**

```bash
grep -c "NoNewPrivileges\|ProtectSystem\|MemoryDenyWriteExecute\|ReadWritePaths" systemd/ice-gateway.service
```

Expected: `4`

- [ ] **Step 3: Commit**

```bash
git add systemd/ice-gateway.service
git commit -m "security: add systemd sandboxing directives to ice-gateway.service"
```

---

### Task 8: Log size cap (M1)

**Files:**
- Modify: `src/ice_gateway/logging_setup.py`
- Test: `tests/test_logging_setup.py`

Context: Loguru sinks use `rotation="1 day"` but no size cap. On a small SD card, a runaway log can fill the disk before the daily rotation fires. Add `rotation="500 MB"` — Loguru rotates on whichever condition fires first.

There are two `logger.add` sinks (`ice_gateway.log` and `sensors.log`). Both need the size cap.

- [ ] **Step 1: Add rotation="500 MB" to the ice_gateway.log sink**

In `src/ice_gateway/logging_setup.py`, find:

```python
    logger.add(
        LOGS_DIR / "ice_gateway.log",
        level=level,
        rotation="1 day",
        retention=f"{retain_days} days",
```

Replace with:

```python
    logger.add(
        LOGS_DIR / "ice_gateway.log",
        level=level,
        rotation="500 MB",
        retention=f"{retain_days} days",
```

- [ ] **Step 2: Add rotation="500 MB" to the sensors.log sink**

Find:

```python
    logger.add(
        LOGS_DIR / "sensors.log",
        level=level,
        rotation="1 day",
        retention=f"{retain_days} days",
```

Replace with:

```python
    logger.add(
        LOGS_DIR / "sensors.log",
        level=level,
        rotation="500 MB",
        retention=f"{retain_days} days",
```

- [ ] **Step 3: Verify both "1 day" rotation strings are gone**

```bash
uv run python -c "
import ast, pathlib
src = pathlib.Path('src/ice_gateway/logging_setup.py').read_text()
assert '\"1 day\"' not in src, 'Found old rotation string'
assert src.count('\"500 MB\"') == 2, 'Expected 2 size caps'
print('OK: both sinks use 500 MB rotation')
"
```

Expected output: `OK: both sinks use 500 MB rotation`

- [ ] **Step 4: Run existing logging tests to confirm nothing broke**

```bash
uv run pytest tests/test_logging_setup.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest
```

Expected: all tests pass.

- [ ] **Step 6: Run mypy and ruff**

```bash
uv run mypy src/ice_gateway --strict --no-error-summary
uv run ruff check src/ tests/
```

Expected: both exit 0.

- [ ] **Step 7: Commit**

```bash
git add src/ice_gateway/logging_setup.py
git commit -m "security: add 500 MB rotation cap to all log sinks"
```

---

### Task 9: SQLite file permissions (M3)

**Files:**
- Modify: `src/ice_gateway/database.py`
- Test: `tests/test_database.py`

Context: SQLAlchemy creates the SQLite file with the process umask (typically 644 — world-readable). The DB file should be 600 (argus-readable only). Fix: `init_db` accepts an optional `db_path` and calls `chmod(0o600)` after `create_all`.

The test must be skipped on Windows because Windows chmod semantics differ.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_database.py`:

```python
import sys

import pytest
from sqlalchemy import create_engine

from ice_gateway.database import init_db


@pytest.mark.skipif(sys.platform == "win32", reason="chmod semantics differ on Windows")
def test_init_db_sets_db_file_to_mode_600(tmp_path):
    db_file = tmp_path / "test.sqlite"
    engine = create_engine(f"sqlite:///{db_file}")
    init_db(engine, db_path=db_file)
    mode = db_file.stat().st_mode & 0o777
    assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
uv run pytest tests/test_database.py::test_init_db_sets_db_file_to_mode_600 -v
```

Expected: `FAILED` — `init_db()` takes 1 positional argument but 2 were given (or TypeError).

- [ ] **Step 3: Update init_db to accept db_path and chmod after create_all**

In `src/ice_gateway/database.py`, find:

```python
def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
```

Replace with:

```python
def init_db(engine: Engine, db_path: Path = DB_PATH) -> None:
    Base.metadata.create_all(engine)
    if db_path.exists():
        db_path.chmod(0o600)
```

`Path` is already imported at the top of `database.py`. `DB_PATH` is the module-level default. When `db_path` is an in-memory SQLite (`sqlite:///:memory:`), `db_path.exists()` returns False — the chmod is skipped cleanly.

- [ ] **Step 4: Run test to confirm it passes**

```bash
uv run pytest tests/test_database.py::test_init_db_sets_db_file_to_mode_600 -v
```

Expected: `PASSED`

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest
```

Expected: all tests pass.

- [ ] **Step 6: Run mypy and ruff**

```bash
uv run mypy src/ice_gateway --strict --no-error-summary
uv run ruff check src/ tests/
```

Expected: both exit 0.

- [ ] **Step 7: Commit**

```bash
git add src/ice_gateway/database.py tests/test_database.py
git commit -m "security: chmod SQLite DB file to 0o600 after init_db"
```

---

### Task 10: Secrets scanning — gitleaks pre-commit hook (M5)

**Files:**
- Create: `.pre-commit-config.yaml`
- Modify: `pyproject.toml`

Context: No automated secret-scanning runs on commit today. Adding gitleaks via pre-commit catches accidentally committed credentials before they reach the remote. `pre-commit` is added as a dev dependency so `uv sync` pulls it in for all contributors.

- [ ] **Step 1: Create .pre-commit-config.yaml at the repo root**

```yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.27.2
    hooks:
      - id: gitleaks
```

- [ ] **Step 2: Add pre-commit to dev dependencies in pyproject.toml**

In `pyproject.toml`, find the `[dependency-groups]` `dev` list:

```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "httpx>=0.28",
    "ruff>=0.8",
    "mypy>=1.13",
    "types-psutil>=6.0",
]
```

Replace with:

```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "httpx>=0.28",
    "ruff>=0.8",
    "mypy>=1.13",
    "types-psutil>=6.0",
    "pre-commit>=3.7",
]
```

- [ ] **Step 3: Install updated dev dependencies**

```bash
uv sync
```

Expected: `pre-commit` added to `.venv`.

- [ ] **Step 4: Verify .pre-commit-config.yaml is valid**

```bash
uv run pre-commit validate-config .pre-commit-config.yaml
```

Expected: `Configuration parsed and validated` or no output (exit 0).

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
uv run pytest
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add .pre-commit-config.yaml pyproject.toml uv.lock
git commit -m "security: add gitleaks pre-commit hook for secret scanning"
```

Note for developers: wire up the hook locally with `uv run pre-commit install`. This is a one-time step per clone.

---

### Task 11: Move scotsman_ksbun_tool.py to tools/ (M6)

**Files:**
- Move: `scotsman_ksbun_tool.py` → `tools/scotsman_ksbun_tool.py`

Context: The diagnostic tool sits at the repo root alongside `pyproject.toml`, `setup.sh`, etc., making it easy to mistake for application code. Moving it to `tools/` makes its purpose clear. `git mv` preserves the file's blame and log history.

- [ ] **Step 1: Create the tools/ directory and move the file**

```bash
mkdir -p tools
git mv scotsman_ksbun_tool.py tools/scotsman_ksbun_tool.py
```

- [ ] **Step 2: Verify the move**

```bash
git status
```

Expected:
```
Changes to be committed:
  renamed:    scotsman_ksbun_tool.py -> tools/scotsman_ksbun_tool.py
```

- [ ] **Step 3: Confirm no application code imports it**

```bash
uv run grep -r "scotsman_ksbun_tool" src/ tests/
```

Expected: no output (the tool is not imported by the application).

- [ ] **Step 4: Run full test suite to confirm no regressions**

```bash
uv run pytest
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add tools/scotsman_ksbun_tool.py
git commit -m "chore: move scotsman_ksbun_tool.py to tools/ directory"
```

---

## Final Verification

After all tasks are committed, run:

```bash
uv run pytest --cov=src/ice_gateway --cov-report=term-missing
uv run mypy src/ice_gateway --strict --no-error-summary
uv run ruff check src/ tests/
```

All three must exit 0 before the branch is ready to merge.
