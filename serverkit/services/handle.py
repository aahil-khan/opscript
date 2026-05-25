"""Handle for a single systemd service unit."""

from __future__ import annotations

from typing import TYPE_CHECKING

from serverkit.exceptions import ServiceNotFound

if TYPE_CHECKING:
    from serverkit.systemctl.manager import SystemctlManager


def normalize_unit_name(name: str) -> str:
    if name.endswith(".service"):
        return name
    return f"{name}.service"


class ServiceHandle:
    """Friendly API for one service: status, start, stop, restart."""

    def __init__(self, name: str, manager: SystemctlManager) -> None:
        self.name = normalize_unit_name(name)
        self._manager = manager

    def status(self) -> str:
        return self._manager.status(self.name)

    def start(self) -> ServiceHandle:
        self._manager.start(self.name)
        return self

    def stop(self) -> ServiceHandle:
        self._manager.stop(self.name)
        return self

    def restart(self) -> ServiceHandle:
        self._manager.restart(self.name)
        return self

    def is_active(self) -> bool:
        try:
            out = self._manager.status(self.name)
        except ServiceNotFound:
            return False
        return "active (running)" in out or "Active: active" in out

    def __repr__(self) -> str:
        return f"ServiceHandle({self.name!r})"
