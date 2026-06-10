"""Parse shell input strings into SDK calls (Dev 2)."""

from __future__ import annotations

import json
import os
import re
import shlex
from datetime import datetime
from typing import TYPE_CHECKING

from serverkit.exceptions import (
    LogFileNotFound,
    OptionalDependencyError,
    RemoteConnectionError,
    ServerKitError,
    WorkflowNotFound,
)
from serverkit.workflows.builder import WorkflowBuilder
from serverkit.workflows.manager import WorkflowManager

if TYPE_CHECKING:
    from serverkit.shell.state import ReplState

HELP_TEXT = """\
--------------------------------------------------------------------------------
  ServerKit shell — command reference
  Further detail: docs/DEV2_CONTRACTS.md
--------------------------------------------------------------------------------

  Shell
  -----
  help                          Show this help
  clr | clear                   Clear the terminal (Windows: cls, Unix: clear)
  exit                          Leave the shell

  Processes (classic forms; active target = local or remote after connect)
  ---------------------------------------------------------------------------
  processes.all()
  processes.memory_above(N)
  processes.cpu_above(N)
  processes.named("name")
  processes.sort_by_memory().all()
  processes.sort_by_cpu().all()

  Logs
  ----
  logs("path").errors()              Summarize ERROR lines
  logs("path").warnings()
  logs("path").contains("text")      Substring filter (LogFile.contains)
  logs("path").match("regex")        Regex filter (LogFile.match)
  logs("path").summarize()
  logs("path").tail(N)
  logs("path").since("2024-06-01T12:00:00")   # parsed line timestamps
  logs("path").until("2024-06-02T00:00:00")
  logs("path").json_lines()             # JSON array (terminal)
  logs("path").error_rate()             # or .error_rate(10) — window minutes

  Memory
  ------
  memory                        RAM / swap summary
  memory.json                   Same snapshot as JSON (MemorySnapshot.to_dict)

  Workflows (saved + catalog)
  ---------------------------
  workflow create NAME          Interactive builder (local save)
  workflow list                 Saved under ~/.serverkit/workflows/
  workflow run NAME             Run on active target
  catalog                       Bundled template names
  import NAME                   Import catalog template by name
  run NAME [--dry-run]          Run saved workflow

  Host & services (local or after connect)
  ----------------------------------------
  disk                          disk() — partitions; chain e.g. .usage_above(80).summarize()
  network.interfaces()          network.connections() — chain e.g. .listening().display()
  ports                         ports() — chain e.g. .listening().summarize()
  systemctl.list_units()        Chain e.g. .active().summarize()
  services                      services() — chain e.g. .named("nginx").summarize()
  service UNIT ACTION           ACTION: status | start | stop | restart | is_active
  cron                          cron() — chain e.g. .suspicious_only().display()
  users.logged_in()             users.failed_logins() — chain .summarize() / .display()
  env                           env() — .keys_matching("PATH") matches variable *names*
  env.contains("OneDrive")      Substring in *values* (paths, etc.)
  docker()                      docker().containers().running().summarize()
  docker.logs("NAME"[, N])      Local: docker-py; remote: docker over SSH
  docker.stats("NAME")
  containers()                  Alias of docker().containers()

  Processes (fluent root — same as SDK processes())
  ---------------------------------------------------
  processes()                   e.g. processes().for_user("u").display()
  processes().group_by_name().summarize()     # grouped apps (terminal)
  processes().memory_above(N).summarize()     # … any ProcessCollection chain

  Systemctl (raw unit names; same subprocess as SystemctlManager)
  -----------------------------------------------------------------
  systemctl.status("UNIT")
  systemctl.start("UNIT")       systemctl.stop("UNIT")    systemctl.restart("UNIT")

  Workflow one-liner (local only; must end with .save())
  --------------------------------------------------------
  workflow("NAME").processes().memory_above(500).summarize().save()

  Remote SSH
  ----------
  connect HOST [--user U] [--key PATH] [--port N] [--password P]
           [--timeout SEC] [--no-agent] [--no-look-for-keys]   # needs: pip install serverkit[remote]
  disconnect

  AI (optional: pip install serverkit[ai]; Ollama + ollama.model in config)
  -------------------------------------------------------------------------
  ask <question>                Natural language → SDK (processes, logs, disk,
                                ports, cron, env, memory, network, users, docker,
                                services, systemctl), diagnose, or workflows

  Tab completion lists common SDK strings.
"""


def extract_number(text: str) -> float:
    match = re.search(r"\(\s*(\d+\.?\d*)\s*\)", text)
    return float(match.group(1)) if match else 0.0


def extract_string_arg(text: str, func_name: str) -> str | None:
    """Parse first string literal inside func_name(...)."""
    idx = text.find(f"{func_name}(")
    if idx < 0:
        return None
    start = idx + len(func_name) + 1
    rest = text[start:]
    m = re.match(r'\s*(["\'])(.*?)\1', rest, re.DOTALL)
    if m:
        return m.group(2)
    return None


def format_processes(procs: list) -> str:
    if not procs:
        return "No processes found."
    lines = [
        f"{p.name:<24} {p.memory_mb:>10.1f} MB  CPU: {p.cpu_percent:>6.1f}%  PID: {p.pid}"
        for p in procs
    ]
    return "\n".join(lines)


def _terminal_log_summary(state: "ReplState", path: str) -> str:
    lf = state.active.logs(path)
    return lf.summarize()


def _parse_datetime_arg(s: str) -> datetime:
    """Parse REPL datetime strings for LogFile.since / until."""
    t = s.strip()
    if t.endswith("Z") and "T" in t:
        t = t[:-1]
    try:
        return datetime.fromisoformat(t)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(t, fmt)
        except ValueError:
            continue
    raise ValueError(
        f"Could not parse datetime {s!r}; try ISO format e.g. 2024-06-01T12:00:00"
    )


def _apply_log_chain(state: "ReplState", path: str, chain: str) -> str:
    """chain examples: .errors(), .warnings(), .tail(20), .summarize()."""
    lf = state.active.logs(path)
    tail = chain
    while tail:
        tail = tail.strip()
        if not tail:
            break
        if tail.startswith(".errors()"):
            lf = lf.errors()
            tail = tail[len(".errors()") :]
        elif tail.startswith(".warnings()"):
            lf = lf.warnings()
            tail = tail[len(".warnings()") :]
        elif tail.startswith(".contains(") or tail.startswith(".log_contains("):
            m = re.match(r"^\.(?:contains|log_contains)\(\s*(['\"])(.*?)\1\s*\)", tail, re.DOTALL)
            if not m:
                return "Malformed .contains(\"…\") or .log_contains(\"…\")"
            lf = lf.contains(m.group(2))
            tail = tail[m.end() :]
        elif tail.startswith(".match("):
            m = re.match(r"^\.match\(\s*(['\"])(.*?)\1\s*\)", tail, re.DOTALL)
            if not m:
                return "Malformed .match(\"…\")"
            lf = lf.match(m.group(2))
            tail = tail[m.end() :]
        elif tail.startswith(".since("):
            m = re.match(r"^\.since\(\s*(['\"])(.*?)\1\s*\)", tail, re.DOTALL)
            if not m:
                return "Malformed .since(\"ISO-DATETIME\")"
            try:
                dt = _parse_datetime_arg(m.group(2))
            except ValueError as exc:
                return str(exc)
            lf = lf.since(dt)
            tail = tail[m.end() :]
        elif tail.startswith(".until("):
            m = re.match(r"^\.until\(\s*(['\"])(.*?)\1\s*\)", tail, re.DOTALL)
            if not m:
                return "Malformed .until(\"ISO-DATETIME\")"
            try:
                dt = _parse_datetime_arg(m.group(2))
            except ValueError as exc:
                return str(exc)
            lf = lf.until(dt)
            tail = tail[m.end() :]
        elif tail.startswith(".json_lines()"):
            tail = tail[len(".json_lines()") :]
            if tail.strip().startswith("."):
                return "Cannot chain after .json_lines()"
            data = lf.json_lines()
            return json.dumps(data, indent=2, default=str)[:100_000]
        elif tail.startswith(".error_rate"):
            m = re.match(r"^\.error_rate\(\s*([^)]*)\s*\)", tail)
            if not m:
                return "Malformed .error_rate( [minutes] )"
            inner = m.group(1).strip()
            try:
                win = float(inner) if inner else 5.0
            except ValueError:
                return "error_rate: minutes must be a number"
            rep = lf.error_rate(win)
            tail = tail[m.end() :]
            if tail.strip():
                return "Cannot chain after .error_rate()"
            return (
                f"errors={rep.count} | window_min={rep.window_minutes} | "
                f"errors_per_minute={rep.rate_per_minute:.4f}"
            )
        elif tail.startswith(".summarize()"):
            return lf.summarize()
        elif tail.startswith(".summarise()"):
            return lf.summarise()
        elif tail.startswith(".tail("):
            close = tail.find(")")
            if close < 0:
                return "Malformed .tail( — missing closing )"
            chunk = tail[: close + 1]
            n = int(extract_number(chunk))
            lf = lf.tail(n)
            tail = tail[close + 1 :]
        elif tail.startswith(".display()"):
            return lf.display()
        elif tail.startswith(".all()"):
            lines = lf.all()
            return "\n".join(lines) if lines else "(no lines)"
        else:
            break
    return lf.summarize()


def apply_step_command(builder: WorkflowBuilder, step: str) -> str | None:
    """Map a builder step line to WorkflowBuilder methods. Returns error message or None."""
    parts = shlex.split(step.strip())
    if not parts:
        return "Empty step; try: processes, memory_above 500, summarize, save"
    cmd = parts[0].lower()
    try:
        if cmd == "processes":
            builder.processes()
        elif cmd == "logs" and len(parts) >= 2:
            builder.logs(parts[1])
        elif cmd == "memory_above" and len(parts) >= 2:
            builder.memory_above(float(parts[1]))
        elif cmd == "cpu_above" and len(parts) >= 2:
            builder.cpu_above(float(parts[1]))
        elif cmd == "named" and len(parts) >= 2:
            builder.named(parts[1])
        elif cmd == "sort_by_memory":
            builder.sort_by_memory()
        elif cmd == "sort_by_cpu":
            builder.sort_by_cpu()
        elif cmd == "errors":
            builder.errors()
        elif cmd == "warnings":
            builder.warnings()
        elif cmd == "log_contains" and len(parts) >= 2:
            builder.log_contains(parts[1])
        elif cmd == "tail" and len(parts) >= 2:
            builder.tail(int(parts[1]))
        elif cmd == "summarize":
            builder.summarize()
        elif cmd == "export" and len(parts) >= 2:
            builder.export(parts[1])
        else:
            return (
                f"Unknown step {cmd!r}. Try: processes, logs PATH, memory_above N, "
                "cpu_above N, named NAME, sort_by_memory, errors, warnings, tail N, summarize, export PATH"
            )
    except Exception as exc:  # builder validation
        return f"Step failed: {exc}"
    return None


def run_workflow_builder(name: str, state: "ReplState") -> str:
    print(f"Workflow builder: {name}")
    print("Enter steps (see help). Type save when done, cancel to abort.")
    print(
        "Examples: processes | memory_above 500 | sort_by_memory | summarize\n"
        "          logs /var/log/syslog | errors | tail 20 | summarize\n"
        "          export /tmp/report.txt"
    )
    builder = state.server.workflow(name)
    while True:
        try:
            raw = input("step> ").strip()
        except EOFError:
            return "Cancelled (EOF)."
        if not raw:
            continue
        if raw == "save":
            builder.save()
            return f"Workflow saved: {name}"
        if raw == "cancel":
            return "Cancelled."
        err = apply_step_command(builder, raw)
        if err:
            print(err)


def _parse_connect_args(
    rest: list[str],
) -> tuple[str, str | None, str | None, int, str | None, int | None, bool, bool]:
    if not rest:
        raise ValueError("connect: host required")
    host = rest[0]
    user = None
    key_path = None
    password = None
    port = 22
    timeout: int | None = None
    allow_agent = True
    look_for_keys = True
    i = 1
    while i < len(rest):
        if rest[i] == "--user" and i + 1 < len(rest):
            user = rest[i + 1]
            i += 2
        elif rest[i] == "--key" and i + 1 < len(rest):
            key_path = rest[i + 1]
            i += 2
        elif rest[i] == "--password" and i + 1 < len(rest):
            password = rest[i + 1]
            i += 2
        elif rest[i] == "--port" and i + 1 < len(rest):
            port = int(rest[i + 1])
            i += 2
        elif rest[i] == "--timeout" and i + 1 < len(rest):
            timeout = int(rest[i + 1])
            i += 2
        elif rest[i] == "--no-agent":
            allow_agent = False
            i += 1
        elif rest[i] == "--no-look-for-keys":
            look_for_keys = False
            i += 1
        else:
            raise ValueError(f"connect: unknown argument {rest[i]!r}")
    return host, user, key_path, port, password, timeout, allow_agent, look_for_keys


def parse_input(text: str, state: "ReplState") -> str | None:
    """Translate one line of shell input into a string to print, or None."""
    text = text.strip()
    if not text:
        return None

    # --- Meta / contracts (DEV2_CONTRACTS) ---
    if text == "help":
        return HELP_TEXT

    if text.lower() in ("clr", "clear"):
        os.system("cls" if os.name == "nt" else "clear")
        return None

    if text.startswith("ask "):
        query = text[4:].strip()
        if not query:
            return "Usage: ask <natural language question>"
        try:
            from serverkit.ai.analyzer import Analyzer

            return Analyzer(state.active).ask(query)
        except OptionalDependencyError as exc:
            return f"{exc}\nInstall with: pip install serverkit[ai]"
        except RuntimeError as exc:
            return str(exc)

    if text == "catalog":
        names = WorkflowManager().list_catalog()
        return "\n".join(names) if names else "(no catalog templates)"

    if text.startswith("import ") and not text.startswith("import_workflow"):
        name = text[len("import ") :].strip()
        if not name:
            return "Usage: import CATALOG_NAME"
        state.server.import_workflow(name)
        return f"Imported catalog workflow {name!r} to ~/.serverkit/workflows/"

    if text.startswith("run "):
        rest = shlex.split(text[len("run ") :])
        if not rest:
            return "Usage: run WORKFLOW_NAME [--dry-run]"
        dry = False
        name_parts: list[str] = []
        for tok in rest:
            if tok == "--dry-run":
                dry = True
            else:
                name_parts.append(tok)
        if not name_parts:
            return "Usage: run WORKFLOW_NAME [--dry-run]"
        wf_name = name_parts[0]
        result = state.active.run(wf_name, dry_run=dry)
        return _format_workflow_result(result)

    if text.startswith("connect "):
        try:
            from serverkit import Server

            rest = shlex.split(text[len("connect ") :])
            host, user, key_path, port, password, timeout, allow_agent, look_for_keys = (
                _parse_connect_args(rest)
            )
            state.close_remote()
            state.remote = Server.connect(
                host,
                user=user,
                key_path=key_path,
                port=port,
                password=password,
                config=state.server._config,
                timeout=timeout,
                allow_agent=allow_agent,
                look_for_keys=look_for_keys,
            )
            return f"Connected to {host!r} as {state.remote.user!r} (remote is active)."
        except OptionalDependencyError as exc:
            return f"{exc}\nInstall with: pip install serverkit[remote]"
        except RemoteConnectionError as exc:
            return f"Connection failed: {exc}"
        except ValueError as exc:
            return str(exc)

    if text == "disconnect":
        if state.remote is None:
            return "Not connected."
        host = getattr(state.remote, "host", "remote")
        state.close_remote()
        return f"Disconnected from {host!r}. Using local server."

    if text == "memory":
        snap = state.active.memory()
        return snap.summarize() + "\n\n" + snap.display()

    if text == "memory.json":
        snap = state.active.memory()
        return json.dumps(snap.to_dict(), indent=2)

    # --- PDF: processes ---
    if text == "processes.all()":
        procs = state.active.processes().all()
        return format_processes(procs)

    if text.startswith("processes.memory_above("):
        n = extract_number(text)
        procs = state.active.processes().memory_above(n).all()
        return format_processes(procs)

    if text.startswith("processes.cpu_above("):
        n = extract_number(text)
        procs = state.active.processes().cpu_above(n).all()
        return format_processes(procs)

    if text.startswith("processes.named("):
        name = extract_string_arg(text, "processes.named")
        if name is None:
            return "Usage: processes.named(\"name\")"
        procs = state.active.processes().named(name).all()
        return format_processes(procs)

    if text.startswith("processes.sort_by_memory()"):
        col = state.active.processes().sort_by_memory()
        if ".all()" in text:
            return format_processes(col.all())
        return col.summarize() + "\n\n" + col.display()

    if text.startswith("processes.sort_by_cpu()"):
        col = state.active.processes().sort_by_cpu()
        if ".all()" in text:
            return format_processes(col.all())
        return col.summarize() + "\n\n" + col.display()

    # --- PDF: logs ---
    if "logs(" in text:
        path = extract_string_arg(text, "logs")
        if path is None:
            return "Could not parse log path. Use logs(\"/path/to.log\")."
        idx = text.find(")")
        if idx < 0:
            return "Malformed logs(...)"
        chain = text[idx + 1 :].strip()
        try:
            if not chain:
                return _terminal_log_summary(state, path)
            return _apply_log_chain(state, path, chain)
        except LogFileNotFound as exc:
            return str(exc)

    # --- PDF: workflow ---
    if text.startswith("workflow create "):
        name = text[len("workflow create ") :].strip()
        if not name:
            return "Usage: workflow create NAME"
        return run_workflow_builder(name, state)

    if text == "workflow list":
        workflows = WorkflowManager().list()
        return "\n".join(workflows) if workflows else "No workflows saved."

    if text.startswith("workflow run "):
        name = text[len("workflow run ") :].strip()
        if not name:
            return "Usage: workflow run NAME"
        result = state.active.run(name)
        return _format_workflow_result(result)

    from serverkit.shell.chains import try_extended_sdk_commands

    ext = try_extended_sdk_commands(text, state)
    if ext is not None:
        return ext

    return f"Unknown command: {text}\nType help for a list of commands."


def _format_workflow_result(result: dict) -> str:
    if not result:
        return "(workflow finished — empty context)"
    # Prefer human-readable summary if present
    summary = result.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    lines = [f"{k}: {v!r}" for k, v in result.items() if not k.startswith("_")]
    return "\n".join(lines) if lines else repr(result)


def format_user_error(exc: BaseException) -> str:
    if isinstance(exc, ServerKitError):
        return str(exc)
    return f"Error: {exc}"
