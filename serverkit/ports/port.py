from __future__ import annotations


class Port:
    def __init__(
        self,
        port: int,
        local_addr: str,
        status: str,
        pid: int | None,
        process_name: str | None,
    ):
        self.port = port
        self.local_addr = local_addr
        self.status = status
        self.pid = pid
        self.process_name = process_name

    def __repr__(self) -> str:
        owner = self.process_name or "unknown"
        return f"Port({self.port}, {self.status}, {owner})"
