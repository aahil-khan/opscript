"""SSH-backed managers mirroring local ServerKit entry points (best-effort)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from serverkit.cron.manager import CronCollection
from serverkit.disk.manager import DiskCollection
from serverkit.docker.manager import ContainerCollection
from serverkit.env.vars import EnvSnapshot
from serverkit.network.manager import ConnectionCollection, InterfaceCollection
from serverkit.ports.manager import PortCollection
from serverkit.remote.host_parsers import (
    connections_from_ss,
    containers_from_docker_ps,
    cron_jobs_from_remote_text,
    disk_partitions_from_df,
    env_dict_from_printenv,
    network_interfaces_from_proc_net_dev,
    ports_from_ss,
)
from serverkit.users.manager import FailedLoginCollection, SessionCollection
from serverkit.users.session import FailedLogin, UserSession

if TYPE_CHECKING:
    from serverkit.remote.connection import SSHConnection


class RemoteNetworkManager:
    def __init__(self, conn: SSHConnection) -> None:
        self._conn = conn

    def interfaces(self) -> InterfaceCollection:
        out = self._conn.run("cat /proc/net/dev 2>/dev/null || true", check=False)
        return InterfaceCollection(network_interfaces_from_proc_net_dev(out))

    def connections(self, kind: str = "inet") -> ConnectionCollection:
        _ = kind
        out = self._conn.run("ss -tan 2>/dev/null | head -n 800 || true", check=False)
        return ConnectionCollection(connections_from_ss(out))


class RemoteDockerManager:
    """Docker via remote ``docker`` CLI (no local docker-py)."""

    _name_safe = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")

    def __init__(self, conn: SSHConnection) -> None:
        self._conn = conn

    def containers(self) -> ContainerCollection:
        out = self._conn.run(
            'docker ps -a --no-trunc --format "{{.ID}}\\t{{.Names}}\\t{{.Image}}\\t{{.Status}}" 2>/dev/null || true',
            check=False,
        )
        return ContainerCollection(containers_from_docker_ps(out))

    def logs(self, name: str, tail: int = 100) -> str:
        if not self._name_safe.match(name):
            raise ValueError("Invalid container name for remote docker.logs")
        return self._conn.run(
            f"docker logs --tail {int(tail)} {name} 2>&1",
            check=False,
        )

    def stats(self, name: str) -> dict:
        if not self._name_safe.match(name):
            raise ValueError("Invalid container name for remote docker.stats")
        raw = self._conn.run(
            f"docker inspect -f '{{{{json .State}}}}' {name} 2>/dev/null || echo null",
            check=False,
        ).strip()
        return {"name": name, "state_json": raw[:4000]}


class RemoteUsersManager:
    def __init__(self, conn: SSHConnection) -> None:
        self._conn = conn

    def logged_in(self) -> SessionCollection:
        out = self._conn.run("who 2>/dev/null || true", check=False)
        sessions: list[UserSession] = []
        for line in out.strip().splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            sessions.append(
                UserSession(user=parts[0], tty=parts[1], host=parts[2], login_at=parts[3])
            )
        return SessionCollection(sessions)

    def failed_logins(self, log_path: str = "/var/log/secure") -> FailedLoginCollection:
        quoted = log_path.replace("'", "'\"'\"'")
        out = self._conn.run(
            f"test -r '{quoted}' && tail -n 500 '{quoted}' || true",
            check=False,
        )
        lines = out.splitlines()
        items = [FailedLogin(line) for line in lines if "Failed" in line or "failure" in line.lower()]
        return FailedLoginCollection(items)
