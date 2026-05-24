from __future__ import annotations


class NetworkInterface:
    def __init__(self, name: str, bytes_sent_mb: float, bytes_recv_mb: float):
        self.name = name
        self.bytes_sent_mb = bytes_sent_mb
        self.bytes_recv_mb = bytes_recv_mb

    def __repr__(self) -> str:
        return f"NetworkInterface({self.name!r}, sent={self.bytes_sent_mb:.1f} MB)"


class Connection:
    def __init__(
        self,
        fd: int,
        family: str,
        type: str,
        local_addr: str,
        remote_addr: str,
        status: str,
        pid: int | None,
    ):
        self.fd = fd
        self.family = family
        self.type = type
        self.local_addr = local_addr
        self.remote_addr = remote_addr
        self.status = status
        self.pid = pid

    def __repr__(self) -> str:
        return f"Connection({self.local_addr} -> {self.remote_addr}, {self.status})"
