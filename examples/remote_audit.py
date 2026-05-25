#!/usr/bin/env python3
"""Example: run a memory audit on a remote host over SSH.

Requires: pip install serverkit[remote]
SSH access to the host (key or password). Remote host should have python3;
psutil on the remote host enables accurate process/memory stats.
"""

from serverkit import Server


def main() -> None:
    host = "vm1.example"  # change to your host
    with Server.connect(host, user="deploy") as remote:
        print(remote.processes().memory_above(100).sort_by_memory().summarize())
        print(remote.memory().summarize())
        # After importing catalog locally, run uses remote context:
        # remote.import_workflow is not on RemoteServer — import locally first:
        # Server().import_workflow("memory_audit")
        # remote.run("memory_audit")


if __name__ == "__main__":
    main()
