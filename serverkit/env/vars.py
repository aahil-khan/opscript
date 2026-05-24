from __future__ import annotations

import os


class EnvSnapshot:
    def __init__(self, data: dict[str, str] | None = None) -> None:
        self._data = dict(data or os.environ)

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._data.get(key, default)

    def path_entries(self) -> list[str]:
        return self._data.get("PATH", "").split(os.pathsep)

    def contains(self, substring: str) -> EnvSnapshot:
        filtered = {k: v for k, v in self._data.items() if substring in v}
        return EnvSnapshot(filtered)

    def keys_matching(self, pattern: str) -> EnvSnapshot:
        needle = pattern.lower()
        filtered = {k: v for k, v in self._data.items() if needle in k.lower()}
        return EnvSnapshot(filtered)

    def all(self) -> dict[str, str]:
        return dict(self._data)

    def summarize(self) -> str:
        return f"{len(self._data)} environment variables"

    def __repr__(self) -> str:
        return f"EnvSnapshot({len(self._data)} vars)"
