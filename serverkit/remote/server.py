"""RemoteServer facade — same entry points as local Server over SSH."""

from __future__ import annotations

import shlex

from serverkit.config import Config
from serverkit.cron.manager import CronCollection
from serverkit.disk.manager import DiskCollection
from serverkit.docker.manager import ContainerCollection
from serverkit.env.vars import EnvSnapshot
from serverkit.logs.logfile import LogFile
from serverkit.memory.snapshot import MemorySnapshot
from serverkit.processes.manager import ProcessCollection
from serverkit.remote.connection import SSHConnection
from serverkit.remote.facade_managers import (
    RemoteDockerManager,
    RemoteNetworkManager,
    RemoteUsersManager,
)
from serverkit.remote.host_parsers import (
    cron_jobs_from_remote_text,
    disk_partitions_from_df,
    env_dict_from_printenv,
    ports_from_ss,
)
from serverkit.remote.parsers import (
    PSUTIL_JSON_SCRIPT,
    PSUTIL_PROBE,
    memory_from_free_m,
    memory_from_psutil_json,
    processes_from_ps_aux,
    processes_from_psutil_json,
)
from serverkit.remote.systemctl import RemoteSystemctlManager
from serverkit.ports.manager import PortCollection
from serverkit.services.manager import ServicesManager
from serverkit.workflows.manager import WorkflowManager


class RemoteServer:
    """SSH-backed facade matching local Server methods used by workflows."""

    def __init__(self, connection: SSHConnection, config: Config | None = None) -> None:
        self._conn = connection
        self._config = config or Config.load()
        self._systemctl = RemoteSystemctlManager(connection)
        self._services_manager = ServicesManager(self._systemctl)
        self._workflow_manager = WorkflowManager()
        self._cached_psutil_payload: str | None = None
        self._network = RemoteNetworkManager(connection)
        self._users = RemoteUsersManager(connection)
        self._docker = RemoteDockerManager(connection)

    @property
    def host(self) -> str:
        return self._conn.host

    @property
    def user(self) -> str:
        return self._conn.user

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> RemoteServer:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def processes(self) -> ProcessCollection:
        if self._has_remote_psutil():
            payload = self._fetch_psutil_json()
            return ProcessCollection(processes_from_psutil_json(payload))
        out = self._conn.run("ps aux", check=False)
        return ProcessCollection(processes_from_ps_aux(out))

    def logs(self, path: str) -> LogFile:
        quoted = path.replace("'", "'\"'\"'")
        out = self._conn.run(f"tail -n 5000 '{quoted}' 2>/dev/null || cat '{quoted}'")
        lines = [line for line in out.splitlines() if line]
        return LogFile.from_lines(lines, path=path)

    def memory(self) -> MemorySnapshot:
        if self._has_remote_psutil():
            payload = self._fetch_psutil_json()
            return MemorySnapshot(memory_from_psutil_json(payload))
        out = self._conn.run("free -m")
        return MemorySnapshot(memory_from_free_m(out))

    def disk(self) -> DiskCollection:
        out = self._conn.run("df -P 2>/dev/null || true", check=False)
        return DiskCollection(disk_partitions_from_df(out))

    def network(self) -> RemoteNetworkManager:
        return self._network

    def ports(self) -> PortCollection:
        out = self._conn.run("ss -tulpn 2>/dev/null | head -n 800 || true", check=False)
        return PortCollection(ports_from_ss(out))

    def systemctl(self) -> RemoteSystemctlManager:
        return self._systemctl

    def services(self):
        return self._services_manager.list()

    def service(self, name: str):
        return self._services_manager.get(name)

    def cron(self) -> CronCollection:
        inner = (
            'for p in /etc/crontab; do test -r "$p" && echo "# FILE$p" && cat "$p"; done; '
            'for p in /etc/cron.d/*; do test -r "$p" && echo "# FILE$p" && cat "$p"; done'
        )
        blob = self._conn.run("bash -lc " + shlex.quote(inner), check=False)
        return CronCollection(cron_jobs_from_remote_text(blob))

    def users(self) -> RemoteUsersManager:
        return self._users

    def env(self) -> EnvSnapshot:
        out = self._conn.run("printenv 2>/dev/null || env 2>/dev/null || true", check=False)
        return EnvSnapshot(env_dict_from_printenv(out))

    def docker(self) -> RemoteDockerManager:
        return self._docker

    def containers(self) -> ContainerCollection:
        return self.docker().containers()

    def ask(self, query: str) -> str:
        from serverkit.ai.analyzer import Analyzer

        return Analyzer(self).ask(query)

    def run(self, name: str, *, dry_run: bool = False, executor: str | None = None):
        return self._workflow_manager.run(
            name, dry_run=dry_run, executor=executor, server=self
        )

    def _has_remote_psutil(self) -> bool:
        try:
            out = self._conn.run(PSUTIL_PROBE, check=False)
            return "ok" in out
        except Exception:
            return False

    def _fetch_psutil_json(self) -> str:
        if self._cached_psutil_payload is not None:
            return self._cached_psutil_payload
        self._cached_psutil_payload = self._conn.run(PSUTIL_JSON_SCRIPT, check=True)
        return self._cached_psutil_payload
