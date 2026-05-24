"""Process listing and collection filtering."""

from __future__ import annotations

import psutil

from serverkit.core.collection import FluentCollection
from serverkit.processes.factory import ProcessFactory
from serverkit.processes.process import Process


class ProcessCollection(FluentCollection[Process]):
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

    def for_user(self, username: str) -> ProcessCollection:
        needle = username.lower()
        self.data = [
            p for p in self.data if p.username and p.username.lower() == needle
        ]
        return self

    def sort_by_memory(self) -> ProcessCollection:
        self.data = sorted(self.data, key=lambda p: p.memory_mb, reverse=True)
        return self

    def sort_by_cpu(self) -> ProcessCollection:
        self.data = sorted(self.data, key=lambda p: p.cpu_percent, reverse=True)
        return self

    def summarize(self) -> str:
        lines = [f"{p.name}: {p.memory_mb:.1f} MB" for p in self.data[:10]]
        return "\n".join(lines)

    def group_by_user(self) -> dict[str, ProcessCollection]:
        groups: dict[str, list[Process]] = {}
        for proc in self.data:
            user = proc.username or "unknown"
            groups.setdefault(user, []).append(proc)
        return {user: ProcessCollection(procs) for user, procs in groups.items()}

    def kill_all(self) -> int:
        count = 0
        for proc in self.data:
            try:
                proc.kill()
                count += 1
            except Exception:
                pass
        return count

    def terminate_all(self) -> int:
        count = 0
        for proc in self.data:
            try:
                proc.terminate()
                count += 1
            except Exception:
                pass
        return count

    def tree(self) -> dict[int, dict]:
        """Build parent -> children tree from current collection."""
        by_pid = {p.pid: p for p in self.data}
        roots = [p for p in self.data if p.ppid not in by_pid]

        def node(proc: Process) -> dict:
            kids = [c for c in self.data if c.ppid == proc.pid]
            return {"process": proc, "children": [node(k) for k in kids]}

        return {r.pid: node(r) for r in roots}


class ProcessManager:
    def all(self) -> ProcessCollection:
        processes: list[Process] = []
        for proc in psutil.process_iter():
            process = ProcessFactory.create(proc)
            if process is not None:
                processes.append(process)
        return ProcessCollection(processes)

    def snapshot(self) -> ProcessCollection:
        return self.all()
