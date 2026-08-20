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


def any_process_named(expected: str, proc_root: Path = Path("/proc")) -> bool:
    try:
        entries = proc_root.iterdir()
    except (FileNotFoundError, PermissionError, OSError):
        return False

    for entry in entries:
        if not entry.name.isdigit():
            continue
        if process_name(int(entry.name), proc_root) == expected:
            return True
    return False
