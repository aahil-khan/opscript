"""Create, list, import, and run workflows."""

from __future__ import annotations

import json
import os

from serverkit.workflows import workflow as workflow_module
from serverkit.workflows.builder import WorkflowBuilder
from serverkit.workflows.workflow import Workflow


class WorkflowManager:
    def create(self, name: str) -> WorkflowBuilder:
        return WorkflowBuilder(name)

    def run(self, name: str) -> dict:
        path = os.path.join(workflow_module.WORKFLOW_DIR, f"{name}.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        workflow = Workflow.from_dict(data)
        print(f"Running workflow: {workflow.name}")
        return workflow.run()

    def list(self) -> list[str]:
        workflow_dir = workflow_module.WORKFLOW_DIR
        if not os.path.exists(workflow_dir):
            return []
        return sorted(
            f.replace(".json", "")
            for f in os.listdir(workflow_dir)
            if f.endswith(".json")
        )

    def import_workflow(self, path: str) -> Workflow:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        workflow = Workflow.from_dict(data)
        workflow.save()
        return workflow
