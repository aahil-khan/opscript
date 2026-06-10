"""Workflow definition, persistence, and execution."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from serverkit.workflows.factory import StepFactory
from serverkit.workflows.step import WorkflowStep
from serverkit.workflows.validator import validate_workflow

if TYPE_CHECKING:
    from serverkit.core.server import Server

WORKFLOW_DIR = os.path.expanduser("~/.serverkit/workflows/")
SCHEMA_VERSION = 2


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

    def run(
        self,
        server: Server | None = None,
        *,
        dry_run: bool = False,
        executor: str | None = None,
    ) -> dict:
        from serverkit import Server
        from serverkit.config import Config
        from serverkit.workflows.executors import get_executor

        validate_workflow(self)
        srv = server or Server()
        cfg = getattr(srv, "_config", None) or Config.load()
        exec_name = executor or cfg.get("workflow", "executor", default="sequential")
        return get_executor(exec_name).execute(self, srv, dry_run=dry_run)

    def save(self, *, versioned: bool = True) -> None:
        validate_workflow(self)
        os.makedirs(WORKFLOW_DIR, exist_ok=True)
        latest = os.path.join(WORKFLOW_DIR, f"{self.name}.json")
        payload = self.to_dict()
        with open(latest, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        if versioned:
            versions_dir = os.path.join(WORKFLOW_DIR, self.name, "versions")
            os.makedirs(versions_dir, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            version_path = os.path.join(versions_dir, f"v_{stamp}.json")
            with open(version_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
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

    def __repr__(self) -> str:
        return f"Workflow({self.name!r}, {len(self.steps)} steps)"
