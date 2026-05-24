from __future__ import annotations

import subprocess
from pathlib import Path

from serverkit.core.collection import FluentCollection
from serverkit.users.session import FailedLogin, UserSession


class SessionCollection(FluentCollection[UserSession]):
    def summarize(self) -> str:
        return "\n".join(repr(s) for s in self.data)


class UsersManager:
    def logged_in(self) -> SessionCollection:
        out = subprocess.run(["who"], capture_output=True, text=True, check=False).stdout
        sessions: list[UserSession] = []
        for line in out.strip().splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            sessions.append(
                UserSession(user=parts[0], tty=parts[1], host=parts[2], login_at=parts[3])
            )
        return SessionCollection(sessions)

    def failed_logins(self, log_path: str = "/var/log/secure") -> list[FailedLogin]:
        path = Path(log_path)
        if not path.exists():
            path = Path("/var/log/auth.log")
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-500:]
        return [FailedLogin(line) for line in lines if "Failed" in line or "failure" in line]
