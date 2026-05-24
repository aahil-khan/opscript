"""Process listing and collection filtering."""

from __future__ import annotations

from serverkit.processes.process import Process


class ProcessCollection:
    """Fluent, eager filter chain over Process objects."""

    def __init__(self, data: list[Process] | None = None) -> None:
        self.data: list[Process] = list(data) if data else []

    def named(self, name: str) -> ProcessCollection:
        needle = name.lower()
        self.data = [p for p in self.data if needle in p.name.lower()]
        return self

    def memory_above(self, mb: float) -> ProcessCollection:
        self.data = [p for p in self.data if p.memory_mb > mb]
        return self

    def cpu_above(self, percent: float) -> ProcessCollection:
        self.data = [p for p in self.data if p.cpu_percent > percent]
        return self

    def sort_by_memory(self) -> ProcessCollection:
        self.data = sorted(self.data, key=lambda p: p.memory_mb, reverse=True)
        return self

    def sort_by_cpu(self) -> ProcessCollection:
        self.data = sorted(self.data, key=lambda p: p.cpu_percent, reverse=True)
        return self

    def all(self) -> list[Process]:
        return self.data

    def summarize(self) -> str:
        lines = [f"{p.name}: {p.memory_mb:.1f} MB" for p in self.data[:10]]
        return "\n".join(lines)

    def __iter__(self):
        return iter(self.data)


class ProcessManager:
    """Loads processes from the OS via psutil."""

    def all(self) -> ProcessCollection:
        raise NotImplementedError
