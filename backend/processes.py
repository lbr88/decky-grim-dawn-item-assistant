from __future__ import annotations

from pathlib import Path


def process_name(pid: int, proc_root: Path = Path("/proc")) -> str | None:
    try:
        return (proc_root / str(pid) / "comm").read_text(
            encoding="utf-8", errors="replace"
        ).strip()
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return None


def pid_matches(pid: int, expected: str, proc_root: Path = Path("/proc")) -> bool:
    return pid > 0 and process_name(pid, proc_root) == expected


def process_command_name(pid: int, proc_root: Path = Path("/proc")) -> str | None:
    try:
        with (proc_root / str(pid) / "cmdline").open("rb") as command_line:
            raw = command_line.read(4097)
        if b"\0" not in raw:
            return None
        first_argument = raw.split(b"\0", 1)[0]
        command = first_argument.decode("utf-8", errors="replace")
        return command.replace("\\", "/").rsplit("/", 1)[-1]
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return None


def any_process_named(expected: str, proc_root: Path = Path("/proc")) -> bool:
    try:
        entries = proc_root.iterdir()
    except (FileNotFoundError, PermissionError, OSError):
        return False

    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if (
            process_name(pid, proc_root) == expected
            or process_command_name(pid, proc_root) == expected
        ):
            return True
    return False
