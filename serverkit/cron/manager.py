from __future__ import annotations

from pathlib import Path

from serverkit.core.collection import FluentCollection
from serverkit.cron.job import CronJob


class CronCollection(FluentCollection[CronJob]):
    def suspicious_only(self) -> CronCollection:
        self.data = [j for j in self.data if j.suspicious]
        return self

    def summarize(self) -> str:
        return "\n".join(repr(j) for j in self.data[:20])


class CronManager:
    def all(self) -> CronCollection:
        jobs: list[CronJob] = []
        paths = [Path("/etc/crontab"), *Path("/etc/cron.d").glob("*")]
        for path in paths:
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(None, 5)
                if len(parts) < 6:
                    continue
                schedule = " ".join(parts[:5])
                jobs.append(CronJob(schedule, parts[5], str(path)))
        return CronCollection(jobs)
