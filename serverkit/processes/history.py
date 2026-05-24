from __future__ import annotations

from dataclasses import dataclass

from serverkit.processes.process import Process


@dataclass
class ProcessHistoryDiff:
    appeared: list[Process]
    disappeared: list[Process]
    changed: list[tuple[Process, Process]]


class ProcessHistory:
    @staticmethod
    def diff(before: list[Process], after: list[Process]) -> ProcessHistoryDiff:
        before_map = {p.pid: p for p in before}
        after_map = {p.pid: p for p in after}
        appeared = [after_map[pid] for pid in after_map if pid not in before_map]
        disappeared = [before_map[pid] for pid in before_map if pid not in after_map]
        changed = []
        for pid in before_map:
            if pid in after_map:
                b, a = before_map[pid], after_map[pid]
                if b.memory_mb != a.memory_mb or b.cpu_percent != a.cpu_percent:
                    changed.append((b, a))
        return ProcessHistoryDiff(appeared, disappeared, changed)
