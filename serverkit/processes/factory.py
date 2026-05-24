"""Factory for building Process objects from psutil records."""

from __future__ import annotations

import psutil

from serverkit.processes.process import Process


class ProcessFactory:
    """Creates Process instances from raw psutil process handles."""

    @staticmethod
    def create(proc: psutil.Process) -> Process | None:
        try:
            with proc.oneshot():
                username = None
                try:
                    username = proc.username()
                except (psutil.AccessDenied, KeyError):
                    pass
                return Process(
                    pid=proc.pid,
                    name=proc.name(),
                    memory_mb=proc.memory_info().rss / 1024 / 1024,
                    cpu_percent=proc.cpu_percent(),
                    ppid=proc.ppid(),
                    username=username,
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
