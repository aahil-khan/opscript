"""SSH connection via paramiko."""

from __future__ import annotations

from typing import Any

from serverkit.config import Config
from serverkit.exceptions import OptionalDependencyError, RemoteConnectionError


def _paramiko():
    try:
        import paramiko
    except ImportError as exc:
        raise OptionalDependencyError(
            "Install remote support: pip install serverkit[remote]"
        ) from exc
    return paramiko


class SSHConnection:
    """Paramiko-backed SSH session for remote command execution."""

    def __init__(self, client: Any, *, host: str, user: str) -> None:
        self._client = client
        self.host = host
        self.user = user

    @classmethod
    def connect(
        cls,
        host: str,
        user: str | None = None,
        *,
        port: int = 22,
        key_path: str | None = None,
        password: str | None = None,
        config: Config | None = None,
        timeout: int | None = None,
        allow_agent: bool = True,
        look_for_keys: bool = True,
    ) -> SSHConnection:
        paramiko = _paramiko()
        cfg = config or Config.load()
        user = user or cfg.get("remote", "default_user") or _default_ssh_user()
        key_path = key_path or cfg.get("remote", "key_path")
        port = int(cfg.get("remote", "port", default=port) or port)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kwargs: dict[str, Any] = {
            "hostname": host,
            "port": port,
            "username": user,
            "timeout": int(timeout or cfg.get("remote", "timeout", default=30) or 30),
            "allow_agent": allow_agent,
            "look_for_keys": look_for_keys,
        }
        if password:
            connect_kwargs["password"] = password
        if key_path:
            connect_kwargs["key_filename"] = key_path
        try:
            client.connect(**connect_kwargs)
        except Exception as exc:
            raise RemoteConnectionError(
                f"SSH connect failed for {user}@{host}:{port}: {exc}"
            ) from exc
        return cls(client, host=host, user=user)

    def run(self, command: str, *, check: bool = True) -> str:
        """Execute a remote shell command and return decoded stdout."""
        _stdin, stdout, stderr = self._client.exec_command(command, timeout=120)
        exit_status = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if check and exit_status != 0:
            raise RemoteConnectionError(
                f"Remote command failed ({exit_status}): {command}\n{err or out}"
            )
        return out

    def read_file(self, path: str, *, max_bytes: int = 5_000_000) -> str:
        """Read a remote file via cat (size-capped)."""
        return self.run(
            f"head -c {max_bytes} { _shell_quote(path) }",
            check=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> SSHConnection:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _default_ssh_user() -> str:
    import getpass

    return getpass.getuser()


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"
