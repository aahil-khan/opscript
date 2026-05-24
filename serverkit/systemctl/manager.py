from __future__ import annotations

import subprocess

from serverkit.core.collection import FluentCollection
from serverkit.systemctl.service import Service, _run_systemctl


class ServiceCollection(FluentCollection[Service]):
    def active(self) -> ServiceCollection:
        self.data = [s for s in self.data if s.active_state == "active"]
        return self

    def named(self, text: str) -> ServiceCollection:
        needle = text.lower()
        self.data = [s for s in self.data if needle in s.name.lower()]
        return self

    def summarize(self) -> str:
        return "\n".join(f"{s.name}: {s.active_state}" for s in self.data[:20])


class SystemctlManager:
    def list_units(self) -> ServiceCollection:
        out = _run_systemctl("list-units", "--type=service", "--no-pager", "--no-legend")
        services: list[Service] = []
        for line in out.strip().splitlines():
            parts = line.split(None, 4)
            if len(parts) < 4:
                continue
            services.append(
                Service(
                    name=parts[0],
                    load_state=parts[1],
                    active_state=parts[2],
                    description=parts[4] if len(parts) > 4 else "",
                )
            )
        return ServiceCollection(services)

    def status(self, name: str) -> str:
        return _run_systemctl("status", name)

    def start(self, name: str) -> None:
        subprocess.run(["systemctl", "start", name], check=True)

    def stop(self, name: str) -> None:
        subprocess.run(["systemctl", "stop", name], check=True)

    def restart(self, name: str) -> None:
        subprocess.run(["systemctl", "restart", name], check=True)
