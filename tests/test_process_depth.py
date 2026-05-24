from serverkit.processes.history import ProcessHistory
from serverkit.processes.manager import ProcessCollection
from serverkit.processes.process import Process


def test_group_by_user():
    procs = ProcessCollection(
        [
            Process(1, "a", 10, 1, username="alice"),
            Process(2, "b", 20, 2, username="bob"),
            Process(3, "c", 30, 3, username="alice"),
        ]
    )
    groups = procs.group_by_user()
    assert len(groups["alice"].all()) == 2


def test_history_diff():
    before = [Process(1, "a", 10, 1)]
    after = [Process(1, "a", 50, 1), Process(2, "b", 5, 1)]
    diff = ProcessHistory.diff(before, after)
    assert len(diff.appeared) == 1
    assert len(diff.changed) == 1
