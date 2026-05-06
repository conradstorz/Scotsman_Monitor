# Security Hardening — Design Spec

**Date:** 2026-05-05
**Scope:** Fix all Critical (C1–C2), Important (I1–I7), and Minor (M1, M3, M5, M6) issues from the security review, baked into idempotent setup scripts.

---

## Context

A security review of the Phase 1 implementation found two Critical, seven Important, and four Minor issues. All changes are made in-place within existing scripts and source files (no new scripts). Every change must be idempotent — safe to re-run on an already-configured Pi.

---

## Section 1: Firewall Hardening (C1)

### `scripts/03_setup_network.sh`

Replace the broad `ufw allow 8080/tcp` with interface-scoped rules. SSH stays open everywhere during step 03 — it is locked down in step 04 after Tailscale is confirmed connected.

```bash
# Dashboard accessible on LAN (eth0) and Tailscale only
ufw allow in on eth0 to any port 8080 proto tcp
ufw allow in on tailscale0 to any port 8080 proto tcp

# SSH stays open on all interfaces here — locked in 04_setup_tailscale.sh
ufw allow ssh
```

Remove the existing `ufw allow 8080/tcp` and `ufw allow ssh` broad rules.

### `scripts/04_setup_tailscale.sh`

After the `tailscale status` health check confirms the node is connected, append:

```bash
# Lock SSH to eth0 + tailscale0 only — safe because Tailscale is confirmed up
ufw delete allow ssh
ufw allow in on eth0 to any port 22 proto tcp
ufw allow in on tailscale0 to any port 22 proto tcp
ufw reload
echo "SSH locked to eth0 + tailscale0"
```

Sequencing is critical: locking SSH before verifying Tailscale connectivity would risk a lockout if Tailscale fails to connect.

---

## Section 2: Supply Chain Trust (C2)

### `scripts/04_setup_tailscale.sh` — GPG apt repo

Replace the `curl | sh` Tailscale installer with the official apt repo method:

```bash
curl -fsSL https://pkgs.tailscale.com/stable/debian/bookworm.gpg \
    | gpg --dearmor -o /usr/share/keyrings/tailscale-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/tailscale-archive-keyring.gpg] \
    https://pkgs.tailscale.com/stable/debian bookworm main" \
    > /etc/apt/sources.list.d/tailscale.list
apt-get update -qq
apt-get install -y tailscale
```

Wrap in an idempotency check: skip if `tailscale` is already installed.

### `scripts/06_setup_app.sh` — Pinned uv with SHA256

Replace the `curl | sh` uv installer with a pinned-version verified install:

```bash
UV_VERSION="0.7.3"
UV_SHA256="<sha256 from astral.sh release page for this version>"
UV_INSTALLER=$(mktemp)
curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" -o "$UV_INSTALLER"
echo "${UV_SHA256}  ${UV_INSTALLER}" | sha256sum -c -
sudo -u argus bash "$UV_INSTALLER"
rm -f "$UV_INSTALLER"
```

A comment in the script must document where to find the updated SHA256 when bumping the pinned version.

Wrap in an idempotency check: skip if `/home/argus/.local/bin/uv` already exists (existing behavior).

---

## Section 3: Systemd Sandboxing (I1)

### `systemd/ice-gateway.service`

Add isolation directives to the `[Service]` section:

```ini
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
```

`ProtectSystem=strict` makes `/usr`, `/boot`, and `/etc` read-only for the process. `ReadWritePaths` carves out the directories the app actually writes to. `MemoryDenyWriteExecute` is safe for CPython.

---

## Section 4: File Permissions & Secrets (I2, M3)

### `scripts/06_setup_app.sh` — env file mode (I2)

Immediately after creating `ice-gateway.env`:

```bash
sudo -u argus cp "$APP_DIR/.env.example" "$APP_DIR/config/ice-gateway.env"
chmod 600 "$APP_DIR/config/ice-gateway.env"
```

### `src/ice_gateway/database.py` — SQLite file mode (M3)

After `Base.metadata.create_all(engine)`:

```python
db_path = Path(config.database.path)
if db_path.exists():
    db_path.chmod(0o600)
```

This is idempotent — `chmod` on an existing file just updates the mode.

---

## Section 5: SSH Hardening (I3, I5)

Both changes go in `scripts/01_setup_os.sh`.

### Harden sshd config (I3)

Write a drop-in config file (idempotent, never edits `sshd_config` directly):

```bash
cat > /etc/ssh/sshd_config.d/99-ice-gateway-hardening.conf << 'EOF'
# Ice Gateway SSH hardening — written by 01_setup_os.sh
PasswordAuthentication no
PermitRootLogin no
X11Forwarding no
AllowAgentForwarding no
MaxAuthTries 3
LoginGraceTime 20
EOF
chmod 644 /etc/ssh/sshd_config.d/99-ice-gateway-hardening.conf
sshd -t   # validate combined config before restarting
systemctl restart ssh
```

### Regenerate SSH host keys (I5)

Gate behind a marker file so re-runs don't rotate keys:

```bash
MARKER="/etc/ssh/.host-keys-regenerated"
if [ ! -f "$MARKER" ]; then
    rm -f /etc/ssh/ssh_host_*
    dpkg-reconfigure openssh-server
    touch "$MARKER"
    echo "SSH host keys regenerated"
else
    echo "SSH host keys already regenerated — skipping"
fi
```

`dpkg-reconfigure openssh-server` generates fresh keys for all key types — the canonical Debian/Raspberry Pi OS method.

---

## Section 6: Privileged Deploy Path (I4)

### `scripts/07_deploy_service.sh`

Copy `deploy.sh` to a root-owned location at the end of the script:

```bash
DEPLOY_TARGET="/usr/local/sbin/ice-gateway-deploy"
cp "$APP_DIR/deploy.sh" "$DEPLOY_TARGET"
chown root:root "$DEPLOY_TARGET"
chmod 755 "$DEPLOY_TARGET"
echo "Installed deploy script at $DEPLOY_TARGET (root-owned)"
```

### `scripts/02_create_argus.sh`

Update the sudoers deploy rule to point to the root-owned location:

```bash
# Before (argus-writable, privilege escalation path):
DEPLOY_RULE="${DEPLOY_USER} ALL=(argus) NOPASSWD: /home/argus/ice_gateway/deploy.sh"

# After (root-owned, not writable by argus):
DEPLOY_RULE="${DEPLOY_USER} ALL=(root) NOPASSWD: /usr/local/sbin/ice-gateway-deploy"
```

The principal also changes from `(argus)` to `(root)` — the deploy script needs root to restart systemd services.

**Operator note:** When the app is updated via git pull, `07_deploy_service.sh` must be re-run to refresh `/usr/local/sbin/ice-gateway-deploy`.

---

## Section 7: Attack Surface Reduction (I6)

### `scripts/01_setup_os.sh`

Remove `snmp` and `tftpd-hpa` from the install list and actively purge them on re-runs:

```bash
# Remove from apt-get install line:
# snmp tftpd-hpa

# Add purge block (idempotent — || true absorbs "not installed" exit code):
apt-get purge -y --auto-remove snmp tftpd-hpa 2>/dev/null || true
```

Neither package is needed for any planned phase.

---

## Section 8: Tailscale ACL Tags (I7)

### `scripts/04_setup_tailscale.sh`

Add `--advertise-tags` to the `tailscale up` call:

```bash
tailscale up \
    --authkey="$TAILSCALE_AUTH_KEY" \
    --hostname="$TAILSCALE_HOSTNAME" \
    --advertise-tags=tag:ice-gateway
```

Add a comment documenting the requirement: the auth key must be a pre-authorized key tagged with `tag:ice-gateway` in the Tailscale admin console (Keys → Generate auth key → add tag).

---

## Section 9: Log Size Cap (M1)

### `src/ice_gateway/logging_setup.py`

Add `"500 MB"` rotation alongside the existing daily rotation. Loguru rotates on whichever condition fires first:

```python
logger.add(
    LOGS_DIR / "ice_gateway.log",
    level=level,
    rotation="500 MB",
    retention=f"{retain_days} days",
    compression="gz",
    ...
)
```

---

## Section 10: Secrets Scanning (M5)

### `.pre-commit-config.yaml` (new file at repo root)

```yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.27.2
    hooks:
      - id: gitleaks
```

### `pyproject.toml`

Add `pre-commit` to dev dependencies:

```toml
[tool.uv.dev-dependencies]
pre-commit = ">=3.7"
```

Developers run `uv run pre-commit install` once after cloning. No CI step added (out of scope for Phase 1).

---

## Section 11: Tool File Organization (M6)

Move `scotsman_ksbun_tool.py` from the repo root to `tools/`:

```bash
git mv scotsman_ksbun_tool.py tools/scotsman_ksbun_tool.py
```

No code changes. Git history is preserved via the move.

---

## Files Changed

| File | Change |
|---|---|
| `scripts/01_setup_os.sh` | Remove snmp/tftpd-hpa; purge block; sshd hardening drop-in; host key regeneration |
| `scripts/02_create_argus.sh` | Update sudoers deploy rule to `/usr/local/sbin/ice-gateway-deploy` as root |
| `scripts/03_setup_network.sh` | Scope 8080 to `eth0`+`tailscale0`; keep SSH broad during setup |
| `scripts/04_setup_tailscale.sh` | GPG apt repo install; SSH lock-down post-connect; `--advertise-tags` |
| `scripts/06_setup_app.sh` | Pinned uv with SHA256 verify; `chmod 600` on env file |
| `scripts/07_deploy_service.sh` | Copy deploy.sh to `/usr/local/sbin/ice-gateway-deploy` (root-owned) |
| `systemd/ice-gateway.service` | Add full sandboxing directives |
| `src/ice_gateway/database.py` | `chmod 0o600` on SQLite file after creation |
| `src/ice_gateway/logging_setup.py` | Add `"500 MB"` rotation cap |
| `.pre-commit-config.yaml` | New file — gitleaks hook |
| `pyproject.toml` | Add `pre-commit` to dev dependencies |
| `tools/scotsman_ksbun_tool.py` | Moved from repo root (git mv) |

---

## Success Criteria

- UFW rules for 8080 and SSH are interface-scoped after step 04 completes
- Tailscale installed via GPG apt repo, not `curl | sh`
- uv installed at a pinned version with SHA256 verification
- `ice-gateway.env` created with mode 600
- SQLite DB file created with mode 600
- `systemd/ice-gateway.service` has full sandboxing directives
- SSH hardening drop-in written; `sshd -t` passes; sshd restarted
- SSH host keys regenerated on first run only (marker file)
- `snmp` and `tftpd-hpa` purged on re-runs
- `/usr/local/sbin/ice-gateway-deploy` exists, owned root:root, mode 755
- Sudoers rule points to `/usr/local/sbin/ice-gateway-deploy` as root
- `tailscale up` includes `--advertise-tags=tag:ice-gateway`
- Log sink has `rotation="500 MB"` cap
- `.pre-commit-config.yaml` present with gitleaks hook
- `tools/scotsman_ksbun_tool.py` exists; file no longer at repo root
- All existing tests continue to pass
- `mypy --strict` passes on `src/`
- `ruff check` exits 0
