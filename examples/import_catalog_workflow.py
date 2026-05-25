#!/usr/bin/env python3
"""Example: import a bundled workflow template and run it."""

from serverkit import Server
from serverkit.workflows.manager import WorkflowManager


def main() -> None:
    mgr = WorkflowManager()
    print("Catalog:", ", ".join(mgr.list_catalog()))

    server = Server()
    server.import_workflow("nginx_health_check")
    result = server.run("nginx_health_check", dry_run=True)
    print(result.get("summary", result))


if __name__ == "__main__":
    main()
