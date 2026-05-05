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
- **Dashboard** — `http://<tailscale-ip>:8080`
- **Service user** — `argus` (dedicated account, owns all app files)

## Setup (fresh Raspberry Pi OS 64-bit)

```bash
git clone https://github.com/conradstorz/Scotsman_Monitor
cd Scotsman_Monitor
sudo bash setup.sh
```

`setup.sh` calls the numbered scripts in order and stops on any failure:

| Script | Run as | Purpose |
|---|---|---|
| `scripts/01_setup_os.sh` | root | OS updates, base packages (snmp, tftpd-hpa, etc.) |
| `scripts/02_create_argus.sh` | root | Create `argus` service user, groups, sudoers rules |
| `scripts/03_setup_network.sh` | root | Static IP + DHCP server on eth0, UFW firewall |
| `scripts/04_setup_tailscale.sh` | root | Install Tailscale (prompts for auth key once) |
| `scripts/05_setup_onewire.sh` | root | Enable DS18B20 1-wire hardware (dtoverlay + modprobe) |
| `scripts/06_setup_app.sh` | root → argus | Clone repo as argus, install uv, sync deps, register sensors |
| `scripts/07_deploy_service.sh` | root | Install and start the ice-gateway systemd service |

> **Tailscale auth key** — before running setup, generate a one-time key at
> https://login.tailscale.com/admin/settings/keys with these settings:
>
> | Setting | Value | Reason |
> |---|---|---|
> | Reusable | No | Key is consumed on first use and cannot enroll a second device |
> | Expiry | 90 days | Short enough to limit exposure if the key is intercepted |
> | Ephemeral | No | Pi must persist in the tailnet across reboots and power cycles |
>
> Script 04 prompts for the key interactively (it starts with `tskey-auth-`).
> The key is never written to disk by the setup scripts.
>
> **Re-running setup does not consume or invalidate the key.** Script 04 checks
> `tailscale status` first — if the Pi is already enrolled in a tailnet it skips
> the auth step entirely. Your existing tailnet node and its stable Tailscale IP
> are preserved across re-installs.

## Moving to a different Tailscale network

If the Pi needs to be re-assigned to a different tailnet (e.g. moved to a new
site or transferred to a new owner):

```bash
# 1. Disconnect from the current tailnet (removes the Pi from that network)
tailscale logout

# 2. Re-run the Tailscale script — it will detect the disconnected state
#    and prompt for a new auth key from the new tailnet
sudo bash scripts/04_setup_tailscale.sh
```

`tailscale logout` removes the Pi's node from the old tailnet immediately.
The old auth key has already been consumed and cannot be reused — only the
node identity is removed. Generate a new auth key from the target tailnet's
admin console before running step 2.

## Service account

The application runs as `argus` — a dedicated system account that owns all app files.

| Property | Value |
|---|---|
| Username | `argus` |
| Password | `scotsman` (change for production) |
| Home | `/home/argus/` |
| App | `/home/argus/ice_gateway/` |

## Post-deploy configuration

1. Cable the KSBU-N to `eth0` and reboot the Pi.
2. Discover the KSBU-N's assigned IP: `arp -n`
3. Edit `/home/argus/ice_gateway/config/config.local.toml`:
   - Set `ksbu_device_ip` to the discovered address
   - Set `site_name` and `machine_name`
   - Update sensor `name` and `location` entries
4. Edit `/home/argus/ice_gateway/config/ice-gateway.env` — add any secrets
5. `sudo systemctl restart ice-gateway`

## Day-to-day deployment

Pull the latest code and restart the service:

```bash
./deploy.sh
```

`deploy.sh` is self-correcting — it re-execs as `argus` automatically even if called as `conrad` or `root`, so ownership is never accidentally changed.

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

Logs rotate daily, are retained for 1 year, and are gzip-compressed.

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
host = "0.0.0.0"
port = 8080

[[temperature_sensors]]
id       = "28-00000abc1234"
name     = "bin_upper_air"
location = "Ice bin upper air"
enabled  = true
alert_min_f = 25.0
alert_max_f = 45.0
```

## Development

Requires Python ≥ 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
uv run ruff check src tests
uv run mypy src
```

## Scripts reference

| Script | Purpose |
|---|---|
| `setup.sh` | Orchestrator — bare-Pi provisioning in one command |
| `deploy.sh` | Day-to-day update — git pull + uv sync + service restart (self-correcting) |
| `scripts/00_README.sh` | Print setup guide in the terminal |
| `scripts/01_setup_os.sh` | OS updates and base package install |
| `scripts/02_create_argus.sh` | Create `argus` service user with groups and sudoers |
| `scripts/03_setup_network.sh` | Static IP, DHCP server, UFW firewall |
| `scripts/04_setup_tailscale.sh` | Tailscale VPN install and auth (idempotent) |
| `scripts/05_setup_onewire.sh` | 1-Wire kernel module and boot overlay (hardware only) |
| `scripts/06_setup_app.sh` | Clone repo as argus, install uv, sync deps, register sensors |
| `scripts/07_deploy_service.sh` | Install systemd service, enable, restart |
| `scripts/07_status_report.sh` | Service status, logs, sensors, system health |
