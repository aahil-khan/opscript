from __future__ import annotations

import subprocess
from pathlib import Path

from serverkit.core.collection import FluentCollection
from serverkit.core.display import display_table, export_table, resolve_use_rich
from serverkit.exceptions import ExternalCommandNotFound
from serverkit.users.session import FailedLogin, UserSession


class SessionCollection(FluentCollection[UserSession]):
    def summarize(self) -> str:
        return "\n".join(repr(s) for s in self.data)

    def display(self, *, use_rich: bool | None = None) -> str:
        rows = [[s.user, s.tty, s.host, s.login_at] for s in self.data]
        return display_table(
            "Logged-in users",
            ["User", "TTY", "Host", "Login"],
            rows,
            use_rich=resolve_use_rich(use_rich),
        )

    def export(self, path: str, fmt: str = "csv") -> None:
        export_table(
            path,
            ["user", "tty", "host", "login_at"],
            [[s.user, s.tty, s.host, s.login_at] for s in self.data],
            fmt=fmt,
        )


class FailedLoginCollection(FluentCollection[FailedLogin]):
    def display(self, *, use_rich: bool | None = None, limit: int = 20) -> str:
        rows = [[f.line[:100]] for f in self.data[:limit]]
        return display_table(
            "Failed logins",
            ["Line"],
            rows,
            use_rich=resolve_use_rich(use_rich),
        )


class UsersManager:
    def logged_in(self) -> SessionCollection:
        try:
            proc = subprocess.run(
                ["who"], capture_output=True, text=True, check=False
            )
        except FileNotFoundError as exc:
            raise ExternalCommandNotFound(
                "The `who` command was not found. users.logged_in() expects a Unix-like "
                "login table (not available on typical Windows shells)."
            ) from exc
        out = proc.stdout
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
        path = Path(log_path)
        if not path.exists():
            path = Path("/var/log/auth.log")
        if not path.exists():
            return FailedLoginCollection()
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-500:]
        items = [FailedLogin(line) for line in lines if "Failed" in line or "failure" in line]
        return FailedLoginCollection(items)
