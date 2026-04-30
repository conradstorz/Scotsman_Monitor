"""
scotsman_ksbun_tool.py

Raspberry Pi gateway abstraction tool for a Scotsman Prodigy Smart-Board KSBU-N.

Primary design:
- Pi eth0 private network to KSBU-N
- Pi provides DHCP
- Pi talks to KSBU-N using SNMPv1 + NAFEM Bulk File Transfer
- Pi hosts command files over TFTP
- HTTP is used for sanity checking / fallback discovery

Docs basis:
- KSBU-N supports Ethernet, DHCP, browser access, USB, and NAFEM protocol.
- Compliance form identifies SNMPv1 agent, TFTP client, DHCP client, UDP, IPv4.
- Bulk File Transfer document defines writable functions and indexes.

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
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tomllib
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from loguru import logger


LOG_DIR = Path("logs")
DATA_DIR = Path("data")
CONFIG_PATH = Path("config/ksbun_gateway.toml")

DEFAULT_COMMUNITY = "public"
DEFAULT_TFTP_ROOT = Path("/srv/tftp")

# Known writable Bulk File Transfer indexes from Scotsman Smart Board doc.
BULK_INDEX_BIN_LEVEL = 4
BULK_INDEX_KEYPAD = 6
BULK_INDEX_CLEAN_INTERVAL = 7
BULK_INDEX_FLUSH_LEVEL = 8
BULK_INDEX_MACHINE_POWER = 9


DEFAULT_CONFIG_TEXT = """[network]
default_community = "public"
tftp_root = "/srv/tftp"

[snmp.bulk_transfer]
file_name_base_oid = ""
transfer_trigger_base_oid = ""
status_base_oid = ""

[snmp.discovery]
walk_root_oid = ".1"
"""


@dataclass
class BulkTransferOids:
    file_name_base_oid: str
    transfer_trigger_base_oid: str
    status_base_oid: str

    @property
    def is_complete(self) -> bool:
        return all(
            [
                self.file_name_base_oid,
                self.transfer_trigger_base_oid,
                self.status_base_oid,
            ]
        )


@dataclass
class GatewayConfig:
    default_community: str
    tftp_root: Path
    walk_root_oid: str
    bulk_transfer_oids: BulkTransferOids


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


def ensure_dirs() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)
    CONFIG_PATH.parent.mkdir(exist_ok=True)


def configure_logging() -> None:
    ensure_dirs()

    logger.remove()
    logger.add(
        LOG_DIR / "scotsman_ksbun_tool.log",
        rotation="00:00",
        retention="30 days",
        level="DEBUG",
    )
    logger.add(lambda message: print(message, end=""), level="INFO")


def load_config(path: Path = CONFIG_PATH) -> GatewayConfig:
    ensure_dirs()

    if not path.exists():
        path.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
        logger.warning(f"Created default config file: {path}")

    with path.open("rb") as file:
        raw = tomllib.load(file)

    return GatewayConfig(
        default_community=raw.get("network", {}).get(
            "default_community",
            DEFAULT_COMMUNITY,
        ),
        tftp_root=Path(
            raw.get("network", {}).get(
                "tftp_root",
                str(DEFAULT_TFTP_ROOT),
            )
        ),
        walk_root_oid=raw.get("snmp", {})
        .get("discovery", {})
        .get("walk_root_oid", ".1"),
        bulk_transfer_oids=BulkTransferOids(
            file_name_base_oid=raw.get("snmp", {})
            .get("bulk_transfer", {})
            .get("file_name_base_oid", ""),
            transfer_trigger_base_oid=raw.get("snmp", {})
            .get("bulk_transfer", {})
            .get("transfer_trigger_base_oid", ""),
            status_base_oid=raw.get("snmp", {})
            .get("bulk_transfer", {})
            .get("status_base_oid", ""),
        ),
    )


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
        config: GatewayConfig,
        community: str | None = None,
    ) -> None:
        self.host = host
        self.config = config
        self.community = community or config.default_community
        self.tftp_root = config.tftp_root

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
            "preview": response.text[:500],
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

    def snmp_walk(self, oid: str | None = None) -> str:
        root_oid = oid or self.config.walk_root_oid

        result = run_command(
            [
                "snmpwalk",
                "-v",
                "1",
                "-c",
                self.community,
                self.host,
                root_oid,
            ],
            timeout=90,
        )

        output_path = DATA_DIR / "ksbun_snmpwalk.txt"
        output_path.write_text(
            result.stdout + "\n\nSTDERR:\n" + result.stderr,
            encoding="utf-8",
        )

        if result.returncode != 0:
            logger.warning(f"snmpwalk failed: {result.stderr.strip()}")

        return str(output_path)

    def create_command_file(self, command_file: CommandFile) -> Path:
        self.tftp_root.mkdir(parents=True, exist_ok=True)

        path = self.tftp_root / command_file.filename
        path.write_text(command_file.contents, encoding="ascii")

        logger.info(f"Created command file: {path}")
        return path

    def verify_bulk_transfer_oids(self) -> dict[str, Any]:
        oids = self.config.bulk_transfer_oids

        if not oids.is_complete:
            return {
                "ok": False,
                "reason": "Bulk transfer OIDs are missing from config.",
                "config_file": str(CONFIG_PATH),
                "needed": [
                    "snmp.bulk_transfer.file_name_base_oid",
                    "snmp.bulk_transfer.transfer_trigger_base_oid",
                    "snmp.bulk_transfer.status_base_oid",
                ],
            }

        checks = {}

        for name, base_oid in {
            "file_name_base_oid": oids.file_name_base_oid,
            "transfer_trigger_base_oid": oids.transfer_trigger_base_oid,
            "status_base_oid": oids.status_base_oid,
        }.items():
            test_oid = f"{base_oid}.{BULK_INDEX_MACHINE_POWER}"

            try:
                checks[name] = {
                    "oid": test_oid,
                    "ok": True,
                    "value": self.snmp_get(test_oid),
                }
            except RuntimeError as exc:
                checks[name] = {
                    "oid": test_oid,
                    "ok": False,
                    "error": str(exc),
                }

        return {
            "ok": all(item["ok"] for item in checks.values()),
            "checks": checks,
        }

    def bulk_transfer(self, command_file: CommandFile) -> ToolResult:
        """
        Stage a command file and trigger a NAFEM Bulk File Transfer.

        The command file and index mapping are known.
        The exact OID writes are intentionally isolated here because the OID names
        must be filled in from the NAFEM Bulk File Transfer MIB.
        """
        path = self.create_command_file(command_file)
        oids = self.config.bulk_transfer_oids

        if not oids.is_complete:
            result = ToolResult(
                timestamp=now(),
                host=self.host,
                action=command_file.action,
                success=False,
                details={
                    "message": "Command file created, but Bulk File Transfer OIDs are not configured.",
                    "file": str(path),
                    "bulk_index": command_file.index,
                    "config_file": str(CONFIG_PATH),
                    "needed": [
                        "snmp.bulk_transfer.file_name_base_oid",
                        "snmp.bulk_transfer.transfer_trigger_base_oid",
                        "snmp.bulk_transfer.status_base_oid",
                    ],
                },
            )
            save_result(result)
            return result

        filename_oid = f"{oids.file_name_base_oid}.{command_file.index}"
        trigger_oid = f"{oids.transfer_trigger_base_oid}.{command_file.index}"
        status_oid = f"{oids.status_base_oid}.{command_file.index}"

        try:
            set_file_result = self.snmp_set_string(filename_oid, command_file.filename)
            trigger_result = self.snmp_set_integer(trigger_oid, 1)
            status_result = self.snmp_get(status_oid)

            result = ToolResult(
                timestamp=now(),
                host=self.host,
                action=command_file.action,
                success=True,
                details={
                    "file": str(path),
                    "bulk_index": command_file.index,
                    "filename_oid": filename_oid,
                    "trigger_oid": trigger_oid,
                    "status_oid": status_oid,
                    "set_file_result": set_file_result,
                    "trigger_result": trigger_result,
                    "status_result": status_result,
                },
            )

        except RuntimeError as exc:
            result = ToolResult(
                timestamp=now(),
                host=self.host,
                action=command_file.action,
                success=False,
                details={
                    "file": str(path),
                    "bulk_index": command_file.index,
                    "filename_oid": filename_oid,
                    "trigger_oid": trigger_oid,
                    "status_oid": status_oid,
                    "error": str(exc),
                },
            )

        save_result(result)
        return result

    def probe(self) -> ToolResult:
        details: dict[str, Any] = {
            "ping": self.ping(),
            "http": self.http_probe(),
            "community": self.community,
            "tftp_root": str(self.tftp_root),
            "bulk_transfer_configured": self.config.bulk_transfer_oids.is_complete,
        }

        try:
            details["snmp_sysdescr"] = self.snmp_get("1.3.6.1.2.1.1.1.0")
        except RuntimeError as exc:
            details["snmp_error"] = str(exc)

        details["bulk_transfer_oid_check"] = self.verify_bulk_transfer_oids()

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

    def write_bin_schedule(self, schedule: dict[str, list[list[int]]]) -> ToolResult:
        """
        Schedule format:
        {
            "Monday": [[60, 32], [660, 32], [900, 32], [1140, 0]],
            "Tuesday": [[60, 32], [660, 32], [900, 32], [1140, 0]]
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

            for index, pair in enumerate(entries, start=1):
                minute, level = pair

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
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--community", default=None)

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

    config = load_config(Path(args.config))

    client = ScotsmanKSBUN(
        host=args.host,
        config=config,
        community=args.community,
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