"""
scotsman_ksbun_tool.py

Raspberry Pi gateway abstraction tool for a Scotsman Prodigy Smart-Board KSBU-N.

Primary design:
- Pi eth0 private network to KSBU-N
- Pi provides DHCP
- Pi talks to KSBU-N using SNMPv1 + NAFEM Bulk File Transfer
- Pi hosts command files over TFTP
- HTTP is only used for sanity checking / fallback discovery

System packages on Raspberry Pi:
    sudo apt update
    sudo apt install -y snmp tftpd-hpa curl
    curl -LsSf https://astral.sh/uv/install.sh | sh


Python deps:
    uv init
    uv add loguru requests

Examples:
    uv run scotsman_ksbun_tool.py --host 10.77.0.20 probe
    uv run scotsman_ksbun_tool.py --host 10.77.0.20 snmp-walk
    uv run scotsman_ksbun_tool.py --host 10.77.0.20 start
    uv run scotsman_ksbun_tool.py --host 10.77.0.20 stop
    uv run scotsman_ksbun_tool.py --host 10.77.0.20 lock-keypad
    uv run scotsman_ksbun_tool.py --host 10.77.0.20 unlock-keypad
    uv run scotsman_ksbun_tool.py --host 10.77.0.20 set-flush-level Auto
    uv run scotsman_ksbun_tool.py --host 10.77.0.20 set-clean-interval 6

Important:
- The SNMP OIDs for the exact NAFEM Bulk File Transfer MIB must be filled in once
  we have the actual NAFEM MIB text or discover it from snmpwalk.
- This script already creates the correct command files and abstracts the indexes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from loguru import logger


LOG_DIR = Path("logs")
DATA_DIR = Path("data")
TFTP_ROOT = Path("/srv/tftp")

DEFAULT_COMMUNITY = "public"

# Known writable Bulk File Transfer indexes from Scotsman Smart Board doc.
BULK_INDEX_BIN_LEVEL = 4
BULK_INDEX_KEYPAD = 6
BULK_INDEX_CLEAN_INTERVAL = 7
BULK_INDEX_FLUSH_LEVEL = 8
BULK_INDEX_MACHINE_POWER = 9


# TODO: Replace these placeholders after NAFEM MIB discovery.
# The KSBU-N supports SNMPv1 and NAFEM Bulk File Transfer, but these exact OIDs
# need the NAFEM MIB or a successful snmpwalk mapping.
NAFEM_BULK_FILE_NAME_OID = "TODO"
NAFEM_BULK_FILE_TRANSFER_TRIGGER_OID = "TODO"
NAFEM_BULK_FILE_STATUS_OID = "TODO"


@dataclass
class CommandFile:
    action: str
    index: int
    filename: str
    contents: str


@dataclass
class ToolResult:
    timestamp: str
    host: str
    action: str
    success: bool
    details: dict[str, Any]


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def configure_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)

    logger.remove()
    logger.add(
        LOG_DIR / "scotsman_ksbun_tool.log",
        rotation="00:00",
        retention="30 days",
        level="DEBUG",
    )
    logger.add(lambda message: print(message, end=""), level="INFO")


def save_result(result: ToolResult) -> None:
    DATA_DIR.mkdir(exist_ok=True)

    with (DATA_DIR / "ksbun_results.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(asdict(result)) + "\n")


def run_command(command: list[str], timeout: int = 20) -> subprocess.CompletedProcess[str]:
    logger.debug(f"Running command: {' '.join(command)}")

    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class ScotsmanKSBUN:
    def __init__(
        self,
        host: str,
        community: str = DEFAULT_COMMUNITY,
        tftp_root: Path = TFTP_ROOT,
    ) -> None:
        self.host = host
        self.community = community
        self.tftp_root = tftp_root

    def ping(self) -> bool:
        result = run_command(["ping", "-c", "1", "-W", "2", self.host], timeout=5)
        return result.returncode == 0

    def http_probe(self) -> dict[str, Any]:
        url = f"http://{self.host}/"

        try:
            response = requests.get(url, timeout=5)
        except requests.RequestException as exc:
            return {"reachable": False, "error": str(exc)}

        html_path = DATA_DIR / "ksbun_http_index.html"
        html_path.write_text(response.text, encoding="utf-8", errors="replace")

        return {
            "reachable": True,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "saved_to": str(html_path),
            "preview": response.text[:300],
        }

    def snmp_get(self, oid: str) -> str:
        result = run_command(
            [
                "snmpget",
                "-v",
                "1",
                "-c",
                self.community,
                self.host,
                oid,
            ]
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())

        return result.stdout.strip()

    def snmp_set_string(self, oid: str, value: str) -> str:
        result = run_command(
            [
                "snmpset",
                "-v",
                "1",
                "-c",
                self.community,
                self.host,
                oid,
                "s",
                value,
            ]
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())

        return result.stdout.strip()

    def snmp_set_integer(self, oid: str, value: int) -> str:
        result = run_command(
            [
                "snmpset",
                "-v",
                "1",
                "-c",
                self.community,
                self.host,
                oid,
                "i",
                str(value),
            ]
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())

        return result.stdout.strip()

    def snmp_walk(self, oid: str = ".1") -> str:
        result = run_command(
            [
                "snmpwalk",
                "-v",
                "1",
                "-c",
                self.community,
                self.host,
                oid,
            ],
            timeout=60,
        )

        output_path = DATA_DIR / "ksbun_snmpwalk.txt"
        output_path.write_text(result.stdout + "\n\nSTDERR:\n" + result.stderr, encoding="utf-8")

        if result.returncode != 0:
            logger.warning(f"snmpwalk failed: {result.stderr.strip()}")

        return str(output_path)

    def create_command_file(self, command_file: CommandFile) -> Path:
        self.tftp_root.mkdir(parents=True, exist_ok=True)

        path = self.tftp_root / command_file.filename
        path.write_text(command_file.contents, encoding="ascii")

        logger.info(f"Created command file: {path}")
        return path

    def bulk_transfer(self, command_file: CommandFile) -> ToolResult:
        """
        Stage a command file and trigger a NAFEM Bulk File Transfer.

        The command file and index mapping are known.
        The exact OID writes are intentionally isolated here because the OID names
        must be filled in from the NAFEM Bulk File Transfer MIB.
        """
        path = self.create_command_file(command_file)

        if "TODO" in {
            NAFEM_BULK_FILE_NAME_OID,
            NAFEM_BULK_FILE_TRANSFER_TRIGGER_OID,
            NAFEM_BULK_FILE_STATUS_OID,
        }:
            success = False
            details = {
                "message": "Command file created, but Bulk File Transfer OIDs are not configured yet.",
                "file": str(path),
                "bulk_index": command_file.index,
                "next_step": "Run snmp-walk and map the NAFEM Bulk File Transfer MIB OIDs.",
            }
            logger.warning(details["message"])
        else:
            filename_oid = f"{NAFEM_BULK_FILE_NAME_OID}.{command_file.index}"
            trigger_oid = f"{NAFEM_BULK_FILE_TRANSFER_TRIGGER_OID}.{command_file.index}"
            status_oid = f"{NAFEM_BULK_FILE_STATUS_OID}.{command_file.index}"

            set_file_result = self.snmp_set_string(filename_oid, command_file.filename)
            trigger_result = self.snmp_set_integer(trigger_oid, 1)
            status_result = self.snmp_get(status_oid)

            success = True
            details = {
                "file": str(path),
                "bulk_index": command_file.index,
                "set_file_result": set_file_result,
                "trigger_result": trigger_result,
                "status_result": status_result,
            }

        result = ToolResult(
            timestamp=now(),
            host=self.host,
            action=command_file.action,
            success=success,
            details=details,
        )
        save_result(result)
        return result

    def probe(self) -> ToolResult:
        details = {
            "ping": self.ping(),
            "http": self.http_probe(),
        }

        try:
            details["snmp_sysdescr"] = self.snmp_get("1.3.6.1.2.1.1.1.0")
        except RuntimeError as exc:
            details["snmp_error"] = str(exc)

        result = ToolResult(
            timestamp=now(),
            host=self.host,
            action="probe",
            success=bool(details["ping"]),
            details=details,
        )
        save_result(result)
        return result

    def start_machine(self) -> ToolResult:
        return self.bulk_transfer(
            CommandFile(
                action="start_machine",
                index=BULK_INDEX_MACHINE_POWER,
                filename="StartMachineIndex9.txt",
                contents="StartMachine\r\n",
            )
        )

    def stop_machine(self) -> ToolResult:
        return self.bulk_transfer(
            CommandFile(
                action="stop_machine",
                index=BULK_INDEX_MACHINE_POWER,
                filename="StopMachineIndex9.txt",
                contents="StopMachine\r\n",
            )
        )

    def lock_keypad(self) -> ToolResult:
        return self.bulk_transfer(
            CommandFile(
                action="lock_keypad",
                index=BULK_INDEX_KEYPAD,
                filename="KeysLockIndex6.txt",
                contents="KeysLock\r\n",
            )
        )

    def unlock_keypad(self) -> ToolResult:
        return self.bulk_transfer(
            CommandFile(
                action="unlock_keypad",
                index=BULK_INDEX_KEYPAD,
                filename="KeysUnlockIndex6.txt",
                contents="KeysUnlock\r\n",
            )
        )

    def set_clean_interval(self, months: int) -> ToolResult:
        if months not in {1, 3, 6}:
            raise ValueError("Clean interval must be 1, 3, or 6 months")

        return self.bulk_transfer(
            CommandFile(
                action=f"set_clean_interval_{months}_months",
                index=BULK_INDEX_CLEAN_INTERVAL,
                filename=f"TimeToClean{months}MonthIndex7.txt",
                contents=f"TimeToClean={months}\r\n",
            )
        )

    def set_flush_level(self, level: str) -> ToolResult:
        normalized = level.strip()

        if normalized.lower() == "auto":
            filename_value = "Auto"
            contents_value = "Auto"
        elif normalized in {"1", "2", "3", "4", "5"}:
            filename_value = normalized
            contents_value = normalized
        else:
            raise ValueError("Flush level must be 1, 2, 3, 4, 5, or Auto")

        return self.bulk_transfer(
            CommandFile(
                action=f"set_flush_level_{filename_value}",
                index=BULK_INDEX_FLUSH_LEVEL,
                filename=f"FlushLevelSetting{filename_value}Index8.txt",
                contents=f"FlushLevelSetting={contents_value}\r\n",
            )
        )

    def set_bin_level_control(self, enabled: bool) -> ToolResult:
        state = "On" if enabled else "Off"

        return self.bulk_transfer(
            CommandFile(
                action=f"set_bin_level_control_{state.lower()}",
                index=BULK_INDEX_BIN_LEVEL,
                filename=f"BinLevelControl{state}Index4.txt",
                contents=f"BinLevelControl={state}\r\n",
            )
        )

    def write_bin_schedule(self, schedule: dict[str, list[tuple[int, int]]]) -> ToolResult:
        """
        Write bin level schedule.

        schedule format:
            {
                "Monday": [(60, 32), (660, 32), (900, 32), (1140, 0)],
                ...
            }

        Times are minutes past midnight.
        Levels are 0 or 9 through 32.
        """
        days = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        lines = []

        for day in days:
            entries = schedule.get(day)
            if entries is None or len(entries) != 4:
                raise ValueError(f"{day} must contain exactly four time/level entries")

            previous_time = -1
            for index, (minute, level) in enumerate(entries, start=1):
                if not 0 <= minute <= 1439:
                    raise ValueError(f"{day} time {index} must be 0-1439 minutes")

                if minute < previous_time:
                    raise ValueError(f"{day} times must be in ascending order")

                if level != 0 and not 9 <= level <= 32:
                    raise ValueError(f"{day} level {index} must be 0 or 9-32")

                previous_time = minute

                lines.append(f"{day}Time{index}={minute}")
                lines.append(f"{day}Level{index}={level}")

        contents = "\r\n".join(lines) + "\r\n"

        return self.bulk_transfer(
            CommandFile(
                action="write_bin_schedule",
                index=BULK_INDEX_BIN_LEVEL,
                filename="BinLevelSchedulingIndex4.txt",
                contents=contents,
            )
        )


def print_result(result: ToolResult) -> None:
    print(json.dumps(asdict(result), indent=2))


def main() -> None:
    configure_logging()

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--community", default=DEFAULT_COMMUNITY)
    parser.add_argument("--tftp-root", default=str(TFTP_ROOT))

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("probe")
    sub.add_parser("snmp-walk")
    sub.add_parser("start")
    sub.add_parser("stop")
    sub.add_parser("lock-keypad")
    sub.add_parser("unlock-keypad")
    sub.add_parser("bin-level-on")
    sub.add_parser("bin-level-off")

    clean_parser = sub.add_parser("set-clean-interval")
    clean_parser.add_argument("months", type=int, choices=[1, 3, 6])

    flush_parser = sub.add_parser("set-flush-level")
    flush_parser.add_argument("level")

    schedule_parser = sub.add_parser("write-bin-schedule")
    schedule_parser.add_argument("json_file")

    args = parser.parse_args()

    client = ScotsmanKSBUN(
        host=args.host,
        community=args.community,
        tftp_root=Path(args.tftp_root),
    )

    if args.command == "probe":
        print_result(client.probe())

    elif args.command == "snmp-walk":
        path = client.snmp_walk()
        result = ToolResult(
            timestamp=now(),
            host=args.host,
            action="snmp_walk",
            success=True,
            details={"saved_to": path},
        )
        save_result(result)
        print_result(result)

    elif args.command == "start":
        print_result(client.start_machine())

    elif args.command == "stop":
        print_result(client.stop_machine())

    elif args.command == "lock-keypad":
        print_result(client.lock_keypad())

    elif args.command == "unlock-keypad":
        print_result(client.unlock_keypad())

    elif args.command == "set-clean-interval":
        print_result(client.set_clean_interval(args.months))

    elif args.command == "set-flush-level":
        print_result(client.set_flush_level(args.level))

    elif args.command == "bin-level-on":
        print_result(client.set_bin_level_control(True))

    elif args.command == "bin-level-off":
        print_result(client.set_bin_level_control(False))

    elif args.command == "write-bin-schedule":
        schedule = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
        print_result(client.write_bin_schedule(schedule))


if __name__ == "__main__":
    main()