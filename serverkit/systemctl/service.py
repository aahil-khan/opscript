from __future__ import annotations

import subprocess

from serverkit.exceptions import ExternalCommandNotFound, ServiceNotFound


class Service:
    def __init__(self, name: str, load_state: str, active_state: str, description: str):
        self.name = name
        self.load_state = load_state
        self.active_state = active_state
        self.description = description

    def __repr__(self) -> str:
        return f"Service({self.name!r}, {self.active_state})"


def _run_systemctl(*args: str) -> str:
    try:
        result = subprocess.run(
            ["systemctl", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ExternalCommandNotFound(
            "systemctl was not found. systemd commands only run on Linux hosts "
            "where systemctl is installed (not on Windows)."
        ) from exc
    if result.returncode != 0:
        raise ServiceNotFound(result.stderr.strip() or "systemctl failed")
    return result.stdout
