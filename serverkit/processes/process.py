"""Process domain object."""

from __future__ import annotations

import os
import signal
import time
from typing import Iterator

import psutil

from serverkit.exceptions import ProcessNotFound


class Process:
    """A single OS process with chainable actions."""

    def __init__(
        self,
        pid: int,
        name: str,
        memory_mb: float,
        cpu_percent: float,
        ppid: int | None = None,
        username: str | None = None,
    ) -> None:
        self.pid = pid
        self.name = name
        self.memory_mb = memory_mb
        self.cpu_percent = cpu_percent
        self.ppid = ppid
        self.username = username

    def kill(self) -> None:
        try:
            os.kill(self.pid, signal.SIGKILL)
        except ProcessLookupError as exc:
            raise ProcessNotFound(f"PID {self.pid} not found") from exc

    def terminate(self) -> None:
        try:
            os.kill(self.pid, signal.SIGTERM)
        except ProcessLookupError as exc:
            raise ProcessNotFound(f"PID {self.pid} not found") from exc

    def children(self) -> list[Process]:
        from serverkit.processes.factory import ProcessFactory

        try:
            proc = psutil.Process(self.pid)
        except psutil.NoSuchProcess as exc:
            raise ProcessNotFound(f"PID {self.pid} not found") from exc
        result = []
        for child in proc.children(recursive=False):
            p = ProcessFactory.create(child)
            if p:
                result.append(p)
        return result

    def parent(self) -> Process | None:
        from serverkit.processes.factory import ProcessFactory

        if self.ppid is None:
            return None
        try:
            return ProcessFactory.create(psutil.Process(self.ppid))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def details(self) -> dict:
        return {
            "pid": self.pid,
            "name": self.name,
            "memory_mb": self.memory_mb,
            "cpu_percent": self.cpu_percent,
            "ppid": self.ppid,
            "username": self.username,
        }

    def __repr__(self) -> str:
        return (
            f"Process({self.name!r}, pid={self.pid}, "
            f"mem={self.memory_mb:.1f}MB)"
        )

    def __str__(self) -> str:
        return self.__repr__()


def watch_process(
    pid: int, interval: float = 5.0, count: int | None = None
) -> Iterator[Process]:
    """Yield refreshed Process snapshots over time."""
    from serverkit.processes.factory import ProcessFactory

    emitted = 0
    while count is None or emitted < count:
        try:
            proc = ProcessFactory.create(psutil.Process(pid))
        except psutil.NoSuchProcess as exc:
            raise ProcessNotFound(f"PID {pid} not found") from exc
        if proc:
            yield proc
        emitted += 1
        time.sleep(interval)
