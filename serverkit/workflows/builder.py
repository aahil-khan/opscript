"""Fluent builder for constructing workflows from chained calls."""

from __future__ import annotations

from serverkit.workflows.steps import ProcessFilterStep, SortStep, SummaryStep
from serverkit.workflows.workflow import Workflow


class WorkflowBuilder:
    """Chains resource filters into workflow steps."""

    def __init__(self, name: str) -> None:
        self._workflow = Workflow(name)
        self._current_resource: str | None = None

    def processes(self) -> WorkflowBuilder:
        self._current_resource = "processes"
        return self

    def memory_above(self, mb: float) -> WorkflowBuilder:
        self._workflow.add_step(ProcessFilterStep(memory_above=mb))
        return self

    def sort_by_memory(self) -> WorkflowBuilder:
        self._workflow.add_step(SortStep(field="memory"))
        return self

    def summarize(self) -> WorkflowBuilder:
        self._workflow.add_step(SummaryStep())
        return self

    def save(self) -> Workflow:
        self._workflow.save()
        return self._workflow

    def build(self) -> Workflow:
        return self._workflow
