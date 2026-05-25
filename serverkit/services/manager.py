"""High-level services API over systemctl."""

from __future__ import annotations

from serverkit.core.collection import FluentCollection
from serverkit.services.handle import ServiceHandle, normalize_unit_name
from serverkit.systemctl.manager import SystemctlManager
from serverkit.systemctl.service import Service


class ServiceCollection(FluentCollection[Service]):
    """Fluent collection of systemd service units."""

    def active(self) -> ServiceCollection:
        self.data = [s for s in self.data if s.active_state == "active"]
        return self

    def named(self, text: str) -> ServiceCollection:
        needle = text.lower()
        self.data = [s for s in self.data if needle in s.name.lower()]
        return self

    def summarize(self) -> str:
        return "\n".join(f"{s.name}: {s.active_state}" for s in self.data[:20])

    def get(self, name: str) -> ServiceHandle:
        return ServiceHandle(name, self._manager)

    def __init__(
        self,
        data: list[Service] | None = None,
        manager: SystemctlManager | None = None,
    ) -> None:
        super().__init__(data)
        self._manager = manager or SystemctlManager()


class ServicesManager:
    def __init__(self, systemctl: SystemctlManager | None = None) -> None:
        self._systemctl = systemctl or SystemctlManager()

    def list(self) -> ServiceCollection:
        units = self._systemctl.list_units()
        return ServiceCollection(units.data, manager=self._systemctl)

    def get(self, name: str) -> ServiceHandle:
        return ServiceHandle(name, self._systemctl)
