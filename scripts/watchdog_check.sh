#!/bin/bash
# Runs once per boot as a systemd oneshot service.
# Detects whether the previous boot was caused by the hardware watchdog and
# emits a CRIT journal entry if so.
#
# Check results are visible via:
#   journalctl -t ice-gateway
#   sudo bash scripts/07_status_report.sh

set -euo pipefail

WATCHDOG_DETECTED=0
DETECTION_METHOD="none"

# Method 1: Raspberry Pi hardware reset source register.
# vcgencmd get_rsts reads PM_RSTS; bit 20 (0x100000 = 1048576) = watchdog reset.
if command -v vcgencmd &>/dev/null; then
    RSTS_HEX=$(vcgencmd get_rsts 2>/dev/null | grep -oP '(?<=rsts=)0x[0-9a-fA-F]+' || true)
    if [ -n "$RSTS_HEX" ]; then
        RSTS_DEC=$(printf '%d' "$RSTS_HEX" 2>/dev/null || echo 0)
        if [ $(( RSTS_DEC & 1048576 )) -ne 0 ]; then
            WATCHDOG_DETECTED=1
            DETECTION_METHOD="vcgencmd (rsts=$RSTS_HEX)"
        fi
    fi
fi

# Method 2: Kernel messages from the previous boot session.
# Fallback for non-Pi hardware or when vcgencmd is unavailable.
if [ "$WATCHDOG_DETECTED" -eq 0 ]; then
    if journalctl -b -1 -k --no-pager 2>/dev/null \
            | grep -qiE "watchdog.*(reset|reboot|triggered)|soft lockup"; then
        WATCHDOG_DETECTED=1
        DETECTION_METHOD="kernel log (previous boot)"
    fi
fi

if [ "$WATCHDOG_DETECTED" -eq 1 ]; then
    logger -t ice-gateway -p daemon.crit \
        "WATCHDOG RESET DETECTED (via $DETECTION_METHOD) — system was rebooted by the hardware watchdog. Investigate for hangs, OOM, or kernel panics: journalctl -b -1"
else
    logger -t ice-gateway -p daemon.info \
        "Boot watchdog check: previous shutdown was normal (no watchdog reset detected)"
fi
