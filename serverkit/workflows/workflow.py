"""Workflow definition, persistence, and execution."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from serverkit.workflows.factory import StepFactory
from serverkit.workflows.step import WorkflowStep

if TYPE_CHECKING:
    from serverkit.core.server import Server

WORKFLOW_DIR = os.path.expanduser("~/.serverkit/workflows/")


class Workflow:
    """Named pipeline of steps, saved as JSON under ~/.serverkit/workflows/."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.steps: list[WorkflowStep] = []
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.last_run: str | None = None

    def add_step(self, step: WorkflowStep) -> Workflow:
        self.steps.append(step)
        return self

    def run(self, server: Server | None = None) -> dict:
        from serverkit import Server

        srv = server or Server()
        context: dict = {"_server": srv}
        for step in self.steps:
            print(f" Running: {step.__class__.__name__}")
            context = step.execute(context)
        self.last_run = datetime.now(timezone.utc).isoformat()
        return context

    def save(self) -> None:
        os.makedirs(WORKFLOW_DIR, exist_ok=True)
        path = os.path.join(WORKFLOW_DIR, f"{self.name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        print(f"Workflow saved: {path}")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "created_at": self.created_at,
            "last_run": self.last_run,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Workflow:
        wf = cls(data["name"])
        wf.created_at = data.get("created_at", wf.created_at)
        wf.last_run = data.get("last_run")
        wf.steps = [StepFactory.create(step) for step in data["steps"]]
        return wf

    def export(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
