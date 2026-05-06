# Scotsman Monitor — Ice Gateway

Raspberry Pi monitoring gateway for a Scotsman Prodigy ice machine. The Pi sits between the KSBU-N communication module and your network, polls machine status over the private Ethernet link, reads DS18B20 temperature probes, and serves a local web dashboard accessible over Tailscale.

## Architecture

```
[Scotsman KSBU-N] ──eth0──► [Raspberry Pi] ──wlan0──► [Site Router] ──► Internet
                             192.168.50.1                                 Tailscale
                             DHCP server                                  Dashboard
```

- **eth0** — Pi is DHCP server (192.168.50.1/24); KSBU-N connects here
- **wlan0** — DHCP from site router; internet access and Tailscale VPN
- **Dashboard** — `http://<tailscale-ip>:8080` (also reachable on LAN via `http://<pi-ip>:8080`)
- **Service user** — `argus` (dedicated account, owns all app files)

---

## Before you begin

Do both of these on your laptop **before** running setup on the Pi.

### 1 — Put your SSH public key on the Pi

Setup script 01 disables password SSH. If your key is not on the Pi before it runs, you will be locked out.

**On Linux / macOS:**
```bash
ssh-copy-id <your-username>@<pi-ip>
ssh <your-username>@<pi-ip>   # verify key login works
```

**On Windows (PowerShell) — no ssh-copy-id available:**
```powershell
# Generate a key if you don't have one
ssh-keygen -t ed25519

# Copy it to the Pi (replace pi with your username if different)
cat ~/.ssh/id_ed25519.pub | ssh <your-username>@<pi-ip> "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"

# Verify key login works (should not prompt for Pi password)
ssh <your-username>@<pi-ip>
```

> **Note:** On Raspberry Pi OS Bookworm (current release), the default username is whatever you set in Raspberry Pi Imager — it is no longer always `pi`.

### 2 — Generate a Tailscale auth key with `tag:ice-gateway`

Script 04 advertises `tag:ice-gateway` to your tailnet and will fail if the auth key is not pre-authorized for that tag.

1. Go to [login.tailscale.com/admin/settings/keys](https://login.tailscale.com/admin/settings/keys)
2. Click **Generate auth key** with these settings:

| Setting | Value | Reason |
|---|---|---|
| Reusable | No | One-time key — cannot enroll a second device |
| Expiry | 90 days | Limits exposure if the key is intercepted |
| Ephemeral | No | Pi must persist in the tailnet across reboots |
| **Tags** | **`tag:ice-gateway`** | Required — setup script advertises this tag |

3. Copy the key (starts with `tskey-auth-...`). Script 04 will prompt for it.

The key is never written to disk by the setup scripts. Re-running setup does not consume the key — script 04 checks `tailscale status` first and skips the auth step if the Pi is already enrolled.

---

## Setup (fresh Raspberry Pi OS 64-bit)

After completing both prerequisites above, SSH into the Pi and run:

```bash
curl -fsSL https://raw.githubusercontent.com/conradstorz/Scotsman_Monitor/master/bootstrap.sh | sudo bash
```

> **Windows users:** Run it from inside an SSH session, not piped directly from PowerShell.
> Piping through `ssh … | sudo bash` fails because sudo requires a terminal:
> ```powershell
> # SSH in first
> ssh <your-username>@<pi-ip>
> # Then run the bootstrap from the Pi's shell
> curl -fsSL https://raw.githubusercontent.com/conradstorz/Scotsman_Monitor/master/bootstrap.sh | sudo bash
> ```
> Alternatively use `ssh -t` to force a terminal: `ssh -t <your-username>@<pi-ip> "curl -fsSL … | sudo bash"`

The bootstrap installs git if missing, clones the repo into `~/Scotsman_Monitor`, and runs `setup.sh` automatically.

> **Troubleshooting — `Permission denied (publickey)` during bootstrap:**
> If the repo already exists on the Pi and was previously cloned over SSH, `git pull` will fail because the Pi has no GitHub SSH key. Switch the remote to HTTPS, then re-run bootstrap:
> ```bash
> git -C ~/Scotsman_Monitor remote set-url origin https://github.com/conradstorz/Scotsman_Monitor.git
> curl -fsSL https://raw.githubusercontent.com/conradstorz/Scotsman_Monitor/master/bootstrap.sh | sudo bash
> ```

`setup.sh` calls the numbered scripts in order and stops on any failure:

| Script | Purpose |
|---|---|
| `scripts/01_setup_os.sh` | OS updates, base packages, SSH host key regeneration, sshd hardening |
| `scripts/02_create_argus.sh` | Create `argus` service user, groups, sudoers rules |
| `scripts/03_setup_network.sh` | Static IP + DHCP server on eth0, UFW firewall |
| `scripts/04_setup_tailscale.sh` | Install Tailscale via GPG apt repo, enroll node, lock SSH to LAN+Tailscale |
| `scripts/05_setup_onewire.sh` | Enable DS18B20 1-wire hardware (dtoverlay + modprobe) |
| `scripts/06_setup_app.sh` | Clone repo as argus, install uv (pinned, verified), sync deps, register sensors |
| `scripts/07_deploy_service.sh` | Install systemd service, install root-owned deploy script |

### What to watch for during setup

**Step 1** regenerates SSH host keys on first run. After setup completes, your laptop's `known_hosts` will have a stale entry for the Pi's IP. Clear it before reconnecting:
```bash
ssh-keygen -R <pi-ip>
```
Then reconnect — via Tailscale hostname (`ssh <your-username>@ice-gateway-<hostname>`) or LAN IP.

**Step 4** prompts for your Tailscale auth key. Have it ready. You can also pre-supply it to skip the prompt:
```bash
sudo TAILSCALE_AUTH_KEY=tskey-auth-... bash setup.sh
```

After step 4 completes, SSH is locked to `eth0` (LAN) and `tailscale0` only. Connections over `wlan0` are dropped. If your setup connection is over wlan0, reconnect over LAN (`eth0`) or Tailscale.

---

## Post-deploy configuration

After setup completes:

1. **Reboot** to activate the 1-Wire dtoverlay and hardware watchdog:
   ```bash
   sudo reboot
   ```

2. **Clear the stale SSH host key** on your laptop (host keys were regenerated in step 1):
   ```bash
   ssh-keygen -R <pi-ip>
   ```

3. **Cable the KSBU-N to `eth0`**, then discover its assigned IP:
   ```bash
   arp -n
   ```

4. **Edit the main config:**
   ```bash
   sudo nano /home/argus/ice_gateway/config/config.local.toml
   ```
   - Set `site_name` and `machine_name`
   - Set `ksbu_device_ip` to the address discovered via `arp`
   - Update sensor `name` and `location` for each `[[temperature_sensors]]` entry

5. **Add secrets** (SMTP password, webhook URLs, etc.):
   ```bash
   sudo nano /home/argus/ice_gateway/config/ice-gateway.env
   ```
   This file is mode 600 — only readable by root and argus.

6. **Start the service:**
   ```bash
   sudo systemctl start ice-gateway
   ```

7. **Verify everything is running:**
   ```bash
   systemctl status ice-gateway
   tailscale status
   ls /sys/bus/w1/devices/        # should show 28-xxxx entries for DS18B20 sensors
   curl http://localhost:8080/api/health
   ```

---

## Moving to a different Tailscale network

```bash
# 1. Remove the Pi from the current tailnet
tailscale logout

# 2. Re-run Tailscale setup — prompts for a new auth key from the new tailnet
sudo bash scripts/04_setup_tailscale.sh
```

Generate the new auth key (with `tag:ice-gateway`) from the target tailnet's admin console before running step 2. The old key has already been consumed and cannot be reused.

---

## Day-to-day deployment

Pull the latest code and restart the service:

```bash
sudo /usr/local/sbin/ice-gateway-deploy
```

The deploy script is installed at `/usr/local/sbin/ice-gateway-deploy` (root-owned) and wired into sudoers so you can invoke it as root. It re-execs as `argus` internally, so git pull and uv sync run under the correct user. Ownership of app files is never accidentally changed.

You can also call it from within the repo as `sudo ./deploy.sh` — both resolve to the same behaviour.

> **Note:** After any change to `deploy.sh` in the repo (e.g. after a `git pull`), re-run `sudo bash scripts/07_deploy_service.sh` to refresh the root-owned copy at `/usr/local/sbin/ice-gateway-deploy`.

---

## Security posture

The following hardening is applied by the setup scripts:

| Area | What is hardened |
|---|---|
| **Firewall** | Dashboard port 8080 open on `eth0` (LAN) and `tailscale0` only — never on `wlan0` |
| **SSH** | Locked to `eth0` + `tailscale0` after Tailscale connects; password auth disabled; root login disabled |
| **SSH host keys** | Regenerated on first setup run — Pi OS images ship with shared keys |
| **Tailscale** | Installed via GPG-verified apt repo (no curl-pipe-sh); ACL tag `tag:ice-gateway` |
| **uv install** | Pinned binary downloaded from GitHub releases, SHA256 verified before install |
| **systemd** | `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome=read-only`, `PrivateTmp`, `MemoryDenyWriteExecute`, `ReadWritePaths` limited to `data/`, `logs/`, `/run` |
| **Deploy script** | Installed root-owned at `/usr/local/sbin/ice-gateway-deploy`; sudoers points there (not the argus-writable in-repo copy) |
| **Secrets file** | `ice-gateway.env` created with mode 600 |
| **SQLite DB** | Created with mode 600 |
| **Attack surface** | `snmp` and `tftpd-hpa` not installed; purged if present from prior runs |
| **Log rotation** | Rotates at 500 MB (prevents SD card exhaustion); retained for configured period |
| **Secret scanning** | gitleaks pre-commit hook wired up for developers |

> `PrivateDevices=true` in the service file restricts `/dev` to a safe minimal set. Phase 2 (UPS via I2C, KSBU-N via serial) will need `DeviceAllow=` lines added for the specific devices — the service file has a comment flagging this.

---

## Service account

| Property | Value |
|---|---|
| Username | `argus` |
| Password | locked (`passwd --lock` — no login; access via sudoers only) |
| Home | `/home/argus/` |
| App | `/home/argus/ice_gateway/` |
| Groups | `gpio`, `i2c`, `dialout` |

---

## Configuration reference (`config/config.example.toml`)

```toml
site_name = "My Ice Location"
machine_name = "Scotsman Prodigy"
timezone = "America/Kentucky/Louisville"
poll_interval_seconds = 30

[network]
ksbu_gateway_ip = "192.168.50.1"   # Pi's own IP on the private link
ksbu_device_ip  = "192.168.50.100" # KSBU-N (discover via arp after cabling)

[logging]
level = "INFO"
retain_days = 365

[dashboard]
host = "0.0.0.0"   # Firewall restricts access to LAN + Tailscale
port = 8080

[[temperature_sensors]]
id       = "28-00000abc1234"
name     = "bin_upper_air"
location = "Ice bin upper air"
enabled  = true
```

---

## Monitoring and diagnostics

```bash
# Full status report (service, logs, sensors, system health)
sudo bash scripts/07_status_report.sh

# Increase journal lines shown
sudo bash scripts/07_status_report.sh 100

# Quick checks
systemctl status ice-gateway
sudo journalctl -u ice-gateway -f
tailscale status
ls /sys/bus/w1/devices/
curl http://localhost:8080/api/health
```

Application logs are written to `/home/argus/ice_gateway/logs/`:

| File | Contents |
|---|---|
| `ice_gateway.log` | All application log records |
| `sensors.log` | Sensor-module records only |

Logs rotate at 500 MB or the configured retention period, whichever fires first. Rotated files are gzip-compressed.

---

## Development

Requires Python ≥ 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                            # install deps (including dev tools)
uv run pre-commit install                          # wire up gitleaks secret scanner (once per clone)
uv run pytest                                      # run tests
uv run pytest --cov=src/ice_gateway --cov-report=term-missing  # with coverage
uv run ruff check src tests                        # lint
uv run mypy src/ice_gateway --strict               # type check
```

All tests use in-memory SQLite and fake hardware providers — no Pi, sensors, or KSBU-N needed.

---

## Scripts reference

| Script | Purpose |
|---|---|
| `bootstrap.sh` | Curl-able entry point — installs git if missing, clones repo, runs `setup.sh` |
| `setup.sh` | Orchestrator — bare-Pi provisioning in one command |
| `deploy.sh` | Source for the root-owned deploy script; installed to `/usr/local/sbin/ice-gateway-deploy` by step 07 |
| `scripts/00_README.sh` | Print setup guide in the terminal |
| `scripts/01_setup_os.sh` | OS updates, base packages, SSH hardening, host key regeneration |
| `scripts/02_create_argus.sh` | Create `argus` service user with groups and sudoers |
| `scripts/03_setup_network.sh` | Static IP, DHCP server on eth0, UFW firewall (8080 scoped to LAN+Tailscale) |
| `scripts/04_setup_tailscale.sh` | Install Tailscale via GPG apt repo, enroll with ACL tags, lock SSH interfaces |
| `scripts/05_setup_onewire.sh` | 1-Wire kernel module and boot overlay (hardware only) |
| `scripts/06_setup_app.sh` | Clone repo as argus, install pinned uv binary, sync deps, register sensors |
| `scripts/07_deploy_service.sh` | Install systemd service, install root-owned deploy script |
| `scripts/07_status_report.sh` | Service status, logs, sensors, system health |
| `tools/scotsman_ksbun_tool.py` | Developer/diagnostic tool for the KSBU-N interface |
