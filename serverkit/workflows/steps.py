"""Concrete workflow steps (Composite pattern — each is one pipeline node)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from serverkit.workflows.step import WorkflowStep

if TYPE_CHECKING:
    from serverkit.core.server import Server
    from serverkit.logs.logfile import LogFile
    from serverkit.processes.manager import ProcessCollection


def _server(context: dict) -> Server:
    from serverkit import Server

    return context.get("_server") or Server()


def _processes(context: dict) -> ProcessCollection:
    procs = context.get("processes")
    if procs is None:
        procs = _server(context).processes()
        context["processes"] = procs
    return procs


class ProcessFilterStep(WorkflowStep):
    def __init__(
        self,
        memory_above: float | None = None,
        cpu_above: float | None = None,
        named: str | None = None,
    ) -> None:
        self.memory_above = memory_above
        self.cpu_above = cpu_above
        self.named = named

    def execute(self, context: dict) -> dict:
        procs = _processes(context)
        if self.memory_above is not None:
            procs.memory_above(self.memory_above)
        if self.cpu_above is not None:
            procs.cpu_above(self.cpu_above)
        if self.named is not None:
            procs.named(self.named)
        context["processes"] = procs
        return context

    def to_dict(self) -> dict:
        return {
            "type": "process_filter",
            "memory_above": self.memory_above,
            "cpu_above": self.cpu_above,
            "named": self.named,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProcessFilterStep:
        return cls(
            memory_above=data.get("memory_above"),
            cpu_above=data.get("cpu_above"),
            named=data.get("named"),
        )


class SortStep(WorkflowStep):
    def __init__(self, field: str = "memory") -> None:
        self.field = field

    def execute(self, context: dict) -> dict:
        procs = _processes(context)
        if self.field == "memory":
            procs.sort_by_memory()
        elif self.field == "cpu":
            procs.sort_by_cpu()
        elif self.field == "name":
            procs.data = sorted(procs.data, key=lambda p: p.name.lower())
        else:
            raise ValueError(f"Unknown sort field: {self.field}")
        context["processes"] = procs
        return context

    def to_dict(self) -> dict:
        return {"type": "sort", "field": self.field}

    @classmethod
    def from_dict(cls, data: dict) -> SortStep:
        return cls(field=data.get("field", "memory"))


class LogFilterStep(WorkflowStep):
    def __init__(
        self,
        path: str | None = None,
        level: str | None = None,
        contains: str | None = None,
    ) -> None:
        self.path = path
        self.level = level
        self.contains = contains

    def execute(self, context: dict) -> dict:
        path = self.path or context.get("log_path")
        if not path:
            raise ValueError("log_filter requires path in step or context['log_path']")

        log: LogFile = _server(context).logs(path)
        if self.level == "error":
            log.errors()
        elif self.level == "warning":
            log.warnings()
        if self.contains:
            log.contains(self.contains)
        context["log_path"] = path
        context["log_file"] = log
        return context

    def to_dict(self) -> dict:
        return {
            "type": "log_filter",
            "path": self.path,
            "level": self.level,
            "contains": self.contains,
        }

    @classmethod
    def from_dict(cls, data: dict) -> LogFilterStep:
        return cls(
            path=data.get("path"),
            level=data.get("level"),
            contains=data.get("contains"),
        )


class TailStep(WorkflowStep):
    def __init__(self, n: int) -> None:
        self.n = n

    def execute(self, context: dict) -> dict:
        log_file: LogFile | None = context.get("log_file")
        if log_file is None:
            path = context.get("log_path")
            if not path:
                raise ValueError("tail requires log_file or log_path in context")
            log_file = _server(context).logs(path)
        log_file.tail(self.n)
        context["log_file"] = log_file
        context["log_lines"] = log_file.all()
        return context

    def to_dict(self) -> dict:
        return {"type": "tail", "n": self.n}

    @classmethod
    def from_dict(cls, data: dict) -> TailStep:
        return cls(n=data["n"])


class SummaryStep(WorkflowStep):
    def execute(self, context: dict) -> dict:
        if "log_file" in context:
            context["summary"] = context["log_file"].summarize()
        elif "processes" in context:
            context["summary"] = context["processes"].summarize()
        else:
            context["summary"] = _processes(context).summarize()
        return context

    def to_dict(self) -> dict:
        return {"type": "summary"}

    @classmethod
    def from_dict(cls, data: dict) -> SummaryStep:
        return cls()


class ExportStep(WorkflowStep):
    def __init__(self, path: str) -> None:
        self.path = path

    def execute(self, context: dict) -> dict:
        payload: Any = context.get("summary")
        if payload is None and "log_lines" in context:
            payload = context["log_lines"]
        if payload is None and "processes" in context:
            payload = [p.details() for p in context["processes"].all()]

        with open(self.path, "w", encoding="utf-8") as f:
            if isinstance(payload, str):
                f.write(payload)
            else:
                json.dump(payload, f, indent=2)
        context["export_path"] = self.path
        return context

    def to_dict(self) -> dict:
        return {"type": "export", "path": self.path}

    @classmethod
    def from_dict(cls, data: dict) -> ExportStep:
        return cls(path=data["path"])


def _register_steps() -> None:
    from serverkit.workflows.factory import StepFactory

    StepFactory.register("process_filter", ProcessFilterStep)
    StepFactory.register("sort", SortStep)
    StepFactory.register("log_filter", LogFilterStep)
    StepFactory.register("tail", TailStep)
    StepFactory.register("summary", SummaryStep)
    StepFactory.register("export", ExportStep)


_register_steps()
