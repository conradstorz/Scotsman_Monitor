#!/bin/bash
# Report on the status of the ice-gateway service and related system components.

LINES="${1:-50}"   # number of recent journal lines; override with: ./07_status_report.sh 100

SEP="──────────────────────────────────────────────────────────────"
section() { echo; echo "$SEP"; echo "  $1"; echo "$SEP"; }

# ── Service status ────────────────────────────────────────────────────────────
section "ice-gateway.service — status"
systemctl status ice-gateway --no-pager --lines=0 2>/dev/null \
    || echo "(service not found)"

# ── Restart counter ───────────────────────────────────────────────────────────
section "Restart / failure counters"
RESTARTS=$(systemctl show ice-gateway --property=NRestarts --value 2>/dev/null)
RESULT=$(systemctl show ice-gateway --property=Result --value 2>/dev/null)
ACTIVE=$(systemctl show ice-gateway --property=ActiveState --value 2>/dev/null)
SUB=$(systemctl show ice-gateway --property=SubState --value 2>/dev/null)
printf "  ActiveState : %s / %s\n" "$ACTIVE" "$SUB"
printf "  Result      : %s\n"      "$RESULT"
printf "  NRestarts   : %s\n"      "$RESTARTS"

# ── Recent journal output ─────────────────────────────────────────────────────
section "ice-gateway — last $LINES journal lines"
journalctl -u ice-gateway -n "$LINES" --no-pager 2>/dev/null \
    || echo "(no journal entries)"

# ── Application log files ─────────────────────────────────────────────────────
APP_DIR="/home/argus/ice_gateway/logs"
if [ -d "$APP_DIR" ]; then
    section "Application log files ($APP_DIR)"
    ls -lh "$APP_DIR" 2>/dev/null

    for logfile in "$APP_DIR"/*.log; do
        [ -f "$logfile" ] || continue
        echo
        echo "  -- tail of $(basename "$logfile") --"
        tail -n 20 "$logfile"
    done
else
    section "Application log files"
    echo "  $APP_DIR not found (app may not be deployed yet)"
fi

# ── Network-online dependency ─────────────────────────────────────────────────
section "network-online.target — status"
systemctl status network-online.target --no-pager --lines=0 2>/dev/null

# ── 1-Wire / system sensors ───────────────────────────────────────────────────
section "1-Wire bus (/sys/bus/w1/devices)"
if [ -d /sys/bus/w1/devices ]; then
    ls /sys/bus/w1/devices/
else
    echo "  1-Wire bus not found (is the kernel module loaded?)"
fi

# ── System health ─────────────────────────────────────────────────────────────
section "System health"
printf "  Uptime      : %s\n" "$(uptime -p 2>/dev/null || uptime)"
printf "  Load avg    : %s\n" "$(cut -d' ' -f1-3 /proc/loadavg)"
printf "  Memory free : %s\n" "$(free -h | awk '/^Mem/{print $4 " free of " $2}')"
if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
    TEMP=$(( $(cat /sys/class/thermal/thermal_zone0/temp) / 1000 ))
    printf "  CPU temp    : %s°C\n" "$TEMP"
fi
DISK=$(df -h /home/argus 2>/dev/null | awk 'NR==2{print $3 " used / " $2 " (" $5 ")"}')
printf "  Disk (/home): %s\n" "$DISK"

echo
echo "$SEP"
echo "  Done — $(date)"
echo "$SEP"
echo
