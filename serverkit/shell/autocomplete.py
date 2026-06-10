"""SDK-aware tab completion (Dev 2) — deterministic static dictionary, no AI."""

from __future__ import annotations

from prompt_toolkit.completion import Completer, Completion

# Completions from a static map (PDF). Keys: line prefix → candidate suffixes.
_SDK_COMPLETIONS: dict[str, list[str]] = {
    "": [
        "ask ",
        "processes",
        "logs",
        "disk",
        "ports",
        "network.",
        "systemctl.list_units()",
        "services",
        "service ",
        "cron",
        "users.",
        "env",
        "docker.containers()",
        "containers",
        "workflow",
        "run",
        "import",
        "catalog",
        "connect",
        "disconnect",
        "memory",
        "memory.json",
        "clr",
        "clear",
        "help",
        "exit",
    ],
    "processes": [
        "processes()",
        "processes().for_user(",
        "processes.all()",
        "processes.named(",
        "processes.memory_above(",
        "processes.cpu_above(",
        "processes.sort_by_memory().all()",
        "processes.sort_by_cpu().all()",
    ],
    "logs": [
        'logs("/var/log/syslog").errors()',
        'logs("app.log").contains("timeout")',
        'logs("app.log").match("ERROR.*")',
        'logs("app.log").warnings()',
        'logs("app.log").summarize()',
        'logs("app.log").tail(20)',
    ],
    "workflow": [
        "workflow create ",
        "workflow list",
        "workflow run ",
    ],
    "run": [
        "run ",
    ],
    "import": [
        "import ",
    ],
    "memory": [
        "memory",
        "memory.json",
    ],
    "connect": [
        "connect ",
    ],
    "disk": [
        "disk",
        "disk.usage_above(",
        "disk.mount_contains(",
        "disk.sort_by_used().summarize()",
    ],
    "ports": [
        "ports",
        "ports.listening().summarize()",
        "ports.port(",
    ],
    "network": [
        "network.interfaces().summarize()",
        "network.connections().listening().display()",
    ],
    "systemctl": [
        "systemctl.list_units().active().summarize()",
        'systemctl.status("nginx.service")',
        'systemctl.restart("nginx.service")',
    ],
    "services": [
        "services",
        "services().active().summarize()",
        "services().named(",
    ],
    "service": [
        "service nginx status",
        "service nginx restart",
    ],
    "cron": [
        "cron",
        "cron.suspicious_only().display()",
    ],
    "users": [
        "users.logged_in().summarize()",
        "users.failed_logins().display()",
    ],
    "env": [
        "env",
        "env.keys_matching(",
    ],
    "docker": [
        "docker.containers().running().summarize()",
        'docker.logs("mycontainer", 100)',
        'docker.stats("mycontainer")',
    ],
    "containers": [
        "containers",
        "containers().running().summarize()",
    ],
}


def _longest_matching_prefix(text: str) -> str:
    best = ""
    for prefix in _SDK_COMPLETIONS:
        if not prefix:
            continue
        if text.startswith(prefix) and len(prefix) > len(best):
            best = prefix
    return best


class SDKCompleter(Completer):
    """Complete common ServerKit shell tokens (offline, no introspection)."""

    def get_completions(self, document, complete_event):  # noqa: ARG002
        text = document.text_before_cursor
        prefix = _longest_matching_prefix(text)
        candidates = _SDK_COMPLETIONS.get(prefix, _SDK_COMPLETIONS[""])
        for candidate in candidates:
            if candidate.startswith(text):
                yield Completion(candidate, start_position=-len(text))
