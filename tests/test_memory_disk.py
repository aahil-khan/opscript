from unittest.mock import MagicMock, patch

from serverkit.disk.manager import DiskManager
from serverkit.memory.snapshot import MemorySnapshot


def test_memory_snapshot_fields():
    vm = MagicMock(total=8 * 1024**3, used=4 * 1024**3, available=4 * 1024**3, percent=50.0)
    swap = MagicMock(total=2 * 1024**3, used=512 * 1024**2, percent=25.0)
    with patch("serverkit.memory.snapshot.psutil.virtual_memory", return_value=vm), patch(
        "serverkit.memory.snapshot.psutil.swap_memory", return_value=swap
    ):
        snap = MemorySnapshot()
    assert snap.percent == 50.0
    assert "RAM" in snap.summarize()


def test_disk_collection_filter():
    from serverkit.disk.partition import Partition

    from serverkit.disk.manager import DiskCollection

    parts = DiskCollection(
        [
            Partition("/dev/sda1", "/", "ext4", 1000, 900, 90),
            Partition("/dev/sdb1", "/home", "ext4", 2000, 200, 10),
        ]
    )
    high = parts.usage_above(50).all()
    assert len(high) == 1
    assert high[0].mountpoint == "/"
