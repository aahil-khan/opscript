from serverkit.memory.snapshot import MemorySnapshot


class MemoryManager:
    def snapshot(self) -> MemorySnapshot:
        return MemorySnapshot()
