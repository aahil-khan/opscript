"""System memory and swap snapshot."""

from __future__ import annotations

import psutil


class MemorySnapshot:
    """Point-in-time memory statistics."""

    def __init__(self) -> None:
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        self.total_mb = vm.total / 1024 / 1024
        self.used_mb = vm.used / 1024 / 1024
        self.available_mb = vm.available / 1024 / 1024
        self.percent = vm.percent
        self.swap_total_mb = swap.total / 1024 / 1024
        self.swap_used_mb = swap.used / 1024 / 1024
        self.swap_percent = swap.percent

    def summarize(self) -> str:
        return (
            f"RAM: {self.used_mb:.0f}/{self.total_mb:.0f} MB ({self.percent:.1f}%) | "
            f"Swap: {self.swap_used_mb:.0f}/{self.swap_total_mb:.0f} MB "
            f"({self.swap_percent:.1f}%)"
        )

    def to_dict(self) -> dict:
        return {
            "total_mb": self.total_mb,
            "used_mb": self.used_mb,
            "available_mb": self.available_mb,
            "percent": self.percent,
            "swap_total_mb": self.swap_total_mb,
            "swap_used_mb": self.swap_used_mb,
            "swap_percent": self.swap_percent,
        }

    def __repr__(self) -> str:
        return f"MemorySnapshot(used={self.percent:.1f}%)"

    def __str__(self) -> str:
        return self.summarize()
