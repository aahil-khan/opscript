from __future__ import annotations

import subprocess


class UserSession:
    def __init__(self, user: str, tty: str, host: str, login_at: str):
        self.user = user
        self.tty = tty
        self.host = host
        self.login_at = login_at

    def __repr__(self) -> str:
        return f"UserSession({self.user!r} on {self.tty!r} from {self.host!r})"


class FailedLogin:
    def __init__(self, line: str):
        self.line = line

    def __repr__(self) -> str:
        return f"FailedLogin({self.line[:60]!r})"
