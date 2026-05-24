"""Process domain object."""

from __future__ import annotations

import os
import signal

import os
import signal


class Process:
    """A single OS process with chainable actions."""

    def __init__(
        self,
        pid: int,
        name: str,
        memory_mb: float,
        cpu_percent: float,
    ) -> None:
        self.pid = pid
        self.name = name
        self.memory_mb = memory_mb
        self.cpu_percent = cpu_percent

    def kill(self) -> None:
        """Send SIGKILL to the process."""
        os.kill(self.pid, signal.SIGKILL)

    def terminate(self) -> None:
        """Send SIGTERM to the process (polite shutdown request)."""
        os.kill(self.pid, signal.SIGTERM)

    def details(self) -> dict:
        """Return process attributes as a plain dict."""
        return {
            "pid": self.pid,
            "name": self.name,
            "memory_mb": self.memory_mb,
            "cpu_percent": self.cpu_percent,
        }

    def __repr__(self) -> str:
        return (
            f"Process({self.name!r}, pid={self.pid}, "
            f"mem={self.memory_mb:.1f}MB)"
        )
