"""Milestones 5–8: workflow steps, serialization, builder, manager."""

import json
from pathlib import Path

import pytest

import serverkit.workflows.steps  # noqa: F401 — register step types
from serverkit import Server
from serverkit.processes.manager import ProcessCollection
from serverkit.processes.process import Process
from serverkit.workflows.builder import WorkflowBuilder
from serverkit.workflows.factory import StepFactory
from serverkit.workflows.manager import WorkflowManager
from serverkit.workflows.steps import (
    ProcessFilterStep,
    SortStep,
    SummaryStep,
)
from serverkit.workflows.workflow import WORKFLOW_DIR, Workflow


@pytest.fixture
def workflow_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr("serverkit.workflows.workflow.WORKFLOW_DIR", str(tmp_path))
    return tmp_path


def test_process_filter_step_mutates_collection():
    procs = ProcessCollection(
        [
            Process(1, "python", 1200, 10),
            Process(2, "nginx", 50, 1),
        ]
    )
    context = ProcessFilterStep(memory_above=500).execute({"processes": procs})
    names = [p.name for p in context["processes"].all()]
    assert names == ["python"]


def test_step_round_trip_via_factory():
    original = ProcessFilterStep(memory_above=1000, named="python")
    restored = StepFactory.create(original.to_dict())
    assert restored.memory_above == 1000
    assert restored.named == "python"


def test_workflow_json_round_trip():
    wf = Workflow("memory_audit")
    wf.add_step(ProcessFilterStep(memory_above=1000))
    wf.add_step(SortStep(field="memory"))
    wf.add_step(SummaryStep())

    data = wf.to_dict()
    loaded = Workflow.from_dict(data)

    assert loaded.name == "memory_audit"
    assert len(loaded.steps) == 3
    assert loaded.steps[0].memory_above == 1000


def test_builder_saves_expected_json(workflow_dir: Path):
    (
        WorkflowBuilder("memory_audit")
        .processes()
        .memory_above(1000)
        .sort_by_memory()
        .summarize()
        .save()
    )

    path = workflow_dir / "memory_audit.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["name"] == "memory_audit"
    assert data["steps"] == [
        {"type": "process_filter", "memory_above": 1000, "cpu_above": None, "named": None},
        {"type": "sort", "field": "memory"},
        {"type": "summary"},
    ]


def test_manager_run_executes_saved_workflow(workflow_dir: Path):
    WorkflowBuilder("quick").processes().memory_above(0).summarize().save()
    context = WorkflowManager().run("quick")
    assert "summary" in context
    assert isinstance(context["summary"], str)


def test_server_run_delegates(workflow_dir: Path):
    WorkflowBuilder("via_server").processes().summarize().save()
    context = Server().run("via_server")
    assert "summary" in context
