from __future__ import annotations

import os
from pathlib import Path


class Partition:
    def __init__(self, device: str, mountpoint: str, fstype: str, total_mb: float, used_mb: float, percent: float):
        self.device = device
        self.mountpoint = mountpoint
        self.fstype = fstype
        self.total_mb = total_mb
        self.used_mb = used_mb
        self.percent = percent

    def __repr__(self) -> str:
        return f"Partition({self.mountpoint!r}, {self.percent:.1f}% full)"


class FileEntry:
    def __init__(self, path: str, size_mb: float):
        self.path = path
        self.size_mb = size_mb

    def __repr__(self) -> str:
        return f"FileEntry({self.path!r}, {self.size_mb:.2f} MB)"


def scan_largest_files(root: str, limit: int = 20) -> list[FileEntry]:
    entries: list[FileEntry] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                size_mb = os.path.getsize(path) / 1024 / 1024
            except OSError:
                continue
            entries.append(FileEntry(path, size_mb))
    entries.sort(key=lambda e: e.size_mb, reverse=True)
    return entries[:limit]


def directory_size_mb(path: str) -> float:
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for name in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                continue
    return total / 1024 / 1024
