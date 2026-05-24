"""Milestone 1: Process + ProcessCollection (no psutil — in-memory only)."""

from serverkit.processes.manager import ProcessCollection
from serverkit.processes.process import Process


def _sample_processes() -> list[Process]:
    return [
        Process(1, "python", 1200.0, 12.0),
        Process(2, "postgres", 800.0, 4.0),
        Process(3, "nginx", 120.0, 0.5),
        Process(4, "python-worker", 600.0, 25.0),
    ]


def test_memory_above_filters_and_chains():
    result = (
        ProcessCollection(_sample_processes())
        .memory_above(500)
        .sort_by_memory()
        .all()
    )
    assert [p.name for p in result] == ["python", "postgres", "python-worker"]


def test_named_is_case_insensitive():
    result = ProcessCollection(_sample_processes()).named("PYthon").all()
    assert len(result) == 2
    assert all("python" in p.name.lower() for p in result)


def test_summarize_limits_to_ten_lines():
    text = ProcessCollection(_sample_processes()).summarize()
    assert "python: 1200.0 MB" in text
    assert text.count("\n") == 3  # four processes → four lines
