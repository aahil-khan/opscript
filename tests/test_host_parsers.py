"""Remote host output parsers."""

from __future__ import annotations

from serverkit.remote.host_parsers import disk_partitions_from_df, env_dict_from_printenv


def test_disk_partitions_from_df():
    sample = """Filesystem     1024-blocks      Used Available Capacity Mounted on
/dev/root      100000      50000     45000      53% /
"""
    parts = disk_partitions_from_df(sample)
    assert len(parts) == 1
    assert parts[0].mountpoint == "/"
    assert parts[0].percent == 53.0


def test_env_dict_from_printenv():
    d = env_dict_from_printenv("A=1\nB=two\n")
    assert d == {"A": "1", "B": "two"}
