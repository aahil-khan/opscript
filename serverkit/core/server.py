"""Server class — thin facade delegating to domain managers."""

from __future__ import annotations

from serverkit.config import Config
from serverkit.cron.manager import CronManager
from serverkit.disk.manager import DiskManager
from serverkit.docker.manager import DockerManager
from serverkit.env.manager import EnvManager
from serverkit.logs.manager import LogManager
from serverkit.memory.manager import MemoryManager
from serverkit.network.manager import NetworkManager
from serverkit.ports.manager import PortManager
from serverkit.processes.manager import ProcessManager
from serverkit.services.manager import ServicesManager
from serverkit.systemctl.manager import SystemctlManager
from serverkit.users.manager import UsersManager
from serverkit.workflows.manager import WorkflowManager


class Server:
    """Entry point for all SDK usage."""

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or Config.load()
        self._process_manager = ProcessManager(self._config)
        self._log_manager = LogManager()
        self._workflow_manager = WorkflowManager()
        self._memory_manager = MemoryManager()
        self._disk_manager = DiskManager()
        self._network_manager = NetworkManager()
        self._port_manager = PortManager()
        self._systemctl_manager = SystemctlManager()
        self._services_manager = ServicesManager(self._systemctl_manager)
        self._cron_manager = CronManager()
        self._users_manager = UsersManager()
        self._env_manager = EnvManager()
        self._docker_manager = DockerManager()

    def processes(self):
        return self._process_manager.all()

    def logs(self, path: str):
        return self._log_manager.open(path)

    def workflow(self, name: str):
        return self._workflow_manager.create(name)

    def run(self, name: str, *, dry_run: bool = False, executor: str | None = None):
        return self._workflow_manager.run(
            name, dry_run=dry_run, executor=executor, server=self
        )

    def memory(self):
        return self._memory_manager.snapshot()

    def disk(self):
        return self._disk_manager.all()

    def network(self):
        return self._network_manager

    def ports(self):
        return self._port_manager.all()

    def systemctl(self):
        return self._systemctl_manager

    def services(self):
        return self._services_manager.list()

    def service(self, name: str):
        return self._services_manager.get(name)

    def cron(self):
        return self._cron_manager.all()

    def users(self):
        return self._users_manager

    def env(self):
        return self._env_manager.snapshot()

    def docker(self):
        return self._docker_manager
