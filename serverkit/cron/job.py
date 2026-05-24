from __future__ import annotations

import re

SUSPICIOUS = re.compile(r"curl\s+.+\|\s*bash|wget\s+.+\|\s*sh", re.I)


class CronJob:
    def __init__(self, schedule: str, command: str, source: str):
        self.schedule = schedule
        self.command = command
        self.source = source

    @property
    def suspicious(self) -> bool:
        return bool(SUSPICIOUS.search(self.command))

    def __repr__(self) -> str:
        flag = " SUSPICIOUS" if self.suspicious else ""
        return f"CronJob({self.schedule!r}, {self.command[:40]!r}{flag})"
