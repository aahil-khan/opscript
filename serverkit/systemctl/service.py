from __future__ import annotations

import subprocess

from serverkit.exceptions import ServiceNotFound


class Service:
    def __init__(self, name: str, load_state: str, active_state: str, description: str):
        self.name = name
        self.load_state = load_state
        self.active_state = active_state
        self.description = description

    def __repr__(self) -> str:
        return f"Service({self.name!r}, {self.active_state})"


def _run_systemctl(*args: str) -> str:
    result = subprocess.run(
        ["systemctl", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ServiceNotFound(result.stderr.strip() or "systemctl failed")
    return result.stdout
