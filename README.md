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

## Setup (fresh Raspberry Pi OS 64-bit)

Run scripts in order:

```bash
sudo bash scripts/01_setup_os.sh        # Update OS, install base packages
sudo bash scripts/02_setup_network.sh   # Static IP + DHCP server on eth0, UFW firewall
sudo bash scripts/03_setup_tailscale.sh # Install Tailscale (requires auth key — see below)
sudo bash scripts/04_setup_onewire.sh   # Enable DS18B20 1-wire sensors
     bash scripts/05_setup_python.sh    # Install uv and Python dependencies
sudo bash scripts/06_deploy_app.sh      # Deploy app, install systemd service
```

> **Tailscale auth key** — before running script 03, generate a one-time key at
> https://login.tailscale.com/admin/settings/keys (Reusable: No, Ephemeral: No).
> The script will prompt for it; it is never stored by the setup scripts.

## Post-deploy configuration

1. Cable the KSBU-N to `eth0` and reboot the Pi.
2. Discover the KSBU-N's assigned IP: `arp -n | grep eth0`
3. Edit `/opt/ice_gateway/config/config.local.toml`:
   - Set `ksbu_device_ip` to the discovered address
   - Add DS18B20 sensor ROM IDs and your site name
   - Discover ROM IDs with: `ls /sys/bus/w1/devices/`
4. Edit `/etc/ice-gateway/ice-gateway.env` — add any secrets
5. `sudo systemctl restart ice-gateway`

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

Application logs are written to `/opt/ice_gateway/logs/`:

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
ksbu_device_ip  = "192.168.50.100" # KSBU-N (discover via arp)

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
uv sync --all-extras
uv run pytest
uv run ruff check src tests
uv run mypy src
```

## Scripts reference

| Script | Purpose |
|---|---|
| `00_README.sh` | Print this setup guide in the terminal |
| `01_setup_os.sh` | OS updates and base package install |
| `02_setup_network.sh` | Static IP, DHCP server, UFW firewall |
| `03_setup_tailscale.sh` | Tailscale VPN install and auth |
| `04_setup_onewire.sh` | 1-Wire kernel module and overlay |
| `05_setup_python.sh` | Install uv and sync dependencies |
| `06_deploy_app.sh` | Copy app to `/opt`, install systemd service |
| `07_status_report.sh` | Service status, logs, sensors, system health |
