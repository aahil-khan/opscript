"""Extended REPL commands: fluent SDK chains beyond the original PDF subset."""

from __future__ import annotations

import json
import re
import shlex
from typing import Any, TYPE_CHECKING

from serverkit.exceptions import (
    ExternalCommandNotFound,
    OptionalDependencyError,
    ServiceNotFound,
)

if TYPE_CHECKING:
    from serverkit.shell.state import ReplState


class ShellSdkError(RuntimeError):
    """User-facing REPL error for unsupported SDK on current target."""


def _summarize_and_display(obj: Any) -> str:
    s = getattr(obj, "summarize", None)
    d = getattr(obj, "display", None)
    parts = []
    if callable(s):
        parts.append(s())
    if callable(d):
        parts.append(d())
    return "\n\n".join(p for p in parts if p)


def parse_call_args_inner(inner: str) -> list[Any]:
    """Parse comma-separated args: numbers, quoted strings, bare identifiers."""
    inner = inner.strip()
    if not inner:
        return []

    def one(tok: str) -> Any:
        t = tok.strip()
        if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
            return t[1:-1]
        try:
            if "." in t:
                return float(t)
            return int(t)
        except ValueError:
            return t

    out: list[Any] = []
    buf: list[str] = []
    depth = 0
    in_q = False
    q = ""
    for ch in inner:
        if in_q:
            buf.append(ch)
            if ch == q:
                in_q = False
            continue
        if ch in "\"'":
            in_q = True
            q = ch
            buf.append(ch)
            continue
        if ch == "(":
            depth += 1
            buf.append(ch)
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
            continue
        if ch == "," and depth == 0:
            out.append(one("".join(buf)))
            buf = []
            continue
        buf.append(ch)
    if buf:
        out.append(one("".join(buf)))
    return out


def _format_process_like_rows(procs: list) -> str:
    if not procs:
        return "No processes found."
    lines = [
        f"{p.name:<24} {p.memory_mb:>10.1f} MB  CPU: {p.cpu_percent:>6.1f}%  PID: {p.pid}"
        for p in procs
    ]
    return "\n".join(lines)


def _format_all_result(obj: Any, data: Any) -> str:
    if isinstance(data, dict):
        if not data:
            return "(empty)"
        lines = [f"{k}={v}" for k, v in sorted(data.items())[:80]]
        return "\n".join(lines)
    if not data:
        return "(empty)"
    sample = data[0]
    if hasattr(sample, "memory_mb") and hasattr(sample, "cpu_percent") and hasattr(sample, "name"):
        return _format_process_like_rows(data)
    if hasattr(sample, "mountpoint") and hasattr(sample, "used_mb"):
        return "\n".join(
            f"{p.mountpoint}: {p.used_mb:.0f}/{p.total_mb:.0f} MB ({p.percent:.1f}%)"
            for p in data[:50]
        )
    return "\n".join(str(x) for x in data)


def _format_process_collection_groups(groups: dict[str, Any]) -> str:
    parts: list[str] = []
    for name, col in sorted(groups.items()):
        n = len(col) if hasattr(col, "__len__") else 0
        summ = col.summarize() if callable(getattr(col, "summarize", None)) else repr(col)
        parts.append(f"=== {name} ({n} processes) ===\n{summ}")
    return "\n\n".join(parts)


def _grouped_processes_followup(obj: Any, tail: str) -> str | None:
    """If ``obj`` is dict[str, ProcessCollection]-like, handle .summarize() / .display() / end."""
    if not isinstance(obj, dict) or not obj:
        return None
    sample = next(iter(obj.values()))
    if not callable(getattr(sample, "summarize", None)):
        return None
    rest = tail.strip()
    if not rest:
        return _format_process_collection_groups(obj)
    if rest.startswith(".summarize()") or rest.startswith(".display()"):
        mlen = len(".summarize()") if rest.startswith(".summarize()") else len(".display()")
        after = rest[mlen:].strip()
        if after:
            return "Cannot chain further after grouped processes (.summarize() / .display() is final)."
        return _format_process_collection_groups(obj)
    return (
        "After group_by_name() / group_by_user(), use .summarize() or .display() "
        "to print groups, or end the chain."
    )


def fluent_chain(obj: Any, tail: str) -> str:
    """Apply .method(args)... ending in .summarize() | .display() | .all() | or default summarize+display."""
    tail = (tail or "").strip()
    if not tail:
        return _summarize_and_display(obj)

    while tail:
        tail = tail.strip()
        if tail.startswith(".summarize()"):
            return obj.summarize()
        if tail.startswith(".summarise()"):
            return obj.summarise()
        if tail.startswith(".display()"):
            return obj.display()
        if tail.startswith(".all()"):
            rest = tail[len(".all()") :].strip()
            if rest:
                return "Cannot chain further after .all()"
            data = obj.all()
            return _format_all_result(obj, data)
        m = re.match(r"\.(\w+)\(\s*([^)]*)\s*\)", tail)
        if m:
            name, inner = m.group(1), m.group(2)
            args = parse_call_args_inner(inner)
            obj = getattr(obj, name)(*args)
            tail = tail[m.end() :]
            g = _grouped_processes_followup(obj, tail)
            if g is not None:
                return g
            continue
        m2 = re.match(r"\.(\w+)\(\)", tail)
        if m2:
            name = m2.group(1)
            obj = getattr(obj, name)()
            tail = tail[m2.end() :]
            g = _grouped_processes_followup(obj, tail)
            if g is not None:
                return g
            continue
        break

    g2 = _grouped_processes_followup(obj, tail)
    if g2 is not None:
        return g2

    return _summarize_and_display(obj)


def _require_local_server(state: ReplState, feature: str) -> None:
    if state.remote is not None:
        raise ShellSdkError(f"{feature} is only supported on the local Server (disconnect first).")


def try_workflow_one_liner(text: str, state: ReplState) -> str | None:
    """workflow(\"name\").processes().memory_above(500).summarize().save()"""
    m = re.match(r'^workflow\s*\(\s*["\']([^"\']+)["\']\s*\)(.*)$', text.strip())
    if not m:
        return None
    name, tail = m.group(1), m.group(2).strip()
    _require_local_server(state, "workflow builder one-liner")
    if not re.search(r"\.save\s*\(\s*\)\s*$", tail):
        raise ShellSdkError("workflow one-liner must end with .save()")
    builder = state.server.workflow(name)
    for mm in re.finditer(r"\.(\w+)\(\s*([^)]*)\s*\)", tail):
        method, inner = mm.group(1), mm.group(2).strip()
        args = parse_call_args_inner(inner)
        if method == "processes":
            builder.processes()
        elif method == "logs" and args:
            builder.logs(str(args[0]))
        elif method == "memory_above" and args:
            builder.memory_above(float(args[0]))
        elif method == "cpu_above" and args:
            builder.cpu_above(float(args[0]))
        elif method == "named" and args:
            builder.named(str(args[0]))
        elif method == "sort_by_memory":
            builder.sort_by_memory()
        elif method == "sort_by_cpu":
            builder.sort_by_cpu()
        elif method == "errors":
            builder.errors()
        elif method == "warnings":
            builder.warnings()
        elif method == "log_contains" and args:
            builder.log_contains(str(args[0]))
        elif method == "tail" and args:
            builder.tail(int(args[0]))
        elif method == "summarize":
            builder.summarize()
        elif method == "export" and args:
            builder.export(str(args[0]))
        elif method == "when_empty" and args:
            builder.when_empty(str(args[0]))
        elif method == "when_missing" and args:
            builder.when_missing(str(args[0]))
        elif method == "then_run" and args:
            builder.then_run(str(args[0]))
        elif method == "save":
            builder.save()
            return f"Workflow saved as ~/.serverkit/workflows/{name}.json"
        else:
            raise ShellSdkError(f"Unknown workflow builder step: {method}()")
    raise ShellSdkError("workflow one-liner must end with .save()")


def try_service_command(text: str, state: ReplState) -> str | None:
    """service UNIT status|start|stop|restart|is_active"""
    parts = shlex.split(text.strip())
    if len(parts) < 3 or parts[0].lower() != "service":
        return None
    _, unit, action = parts[0], parts[1], parts[2].lower()
    handle = state.active.service(unit)
    if action == "status":
        return handle.status()
    if action == "is_active":
        return str(handle.is_active())
    if action == "start":
        handle.start()
        return f"Started {handle.name}"
    if action == "stop":
        handle.stop()
        return f"Stopped {handle.name}"
    if action == "restart":
        handle.restart()
        return f"Restarted {handle.name}"
    raise ShellSdkError(f"Unknown service action {action!r}; use status, start, stop, restart, is_active")


def _match_disk_ports_cron_env(prefix: str, text: str) -> re.Match[str] | None:
    """prefix is disk|ports|cron|env — rest is '' or starts with '.' or optional () then rest."""
    return re.match(rf"^{prefix}(\s*\(\s*\))?(.*)$", text.strip())


def try_extended_sdk_commands(text: str, state: ReplState) -> str | None:
    """Return a result string if this line is an extended SDK command, else None."""
    t = text.strip()
    active = state.active

    try:
        wf = try_workflow_one_liner(t, state)
        if wf is not None:
            return wf
    except ShellSdkError as exc:
        return str(exc)

    try:
        sc = try_service_command(t, state)
        if sc is not None:
            return sc
    except (ServiceNotFound, ShellSdkError) as exc:
        return str(exc)

    try:
        # --- docker.logs / docker.stats (full-line SDK parity) ---
        m_dl = re.match(
            r"^docker\.logs\(\s*(.*?)\s*\)\s*$",
            t,
            re.DOTALL,
        )
        if m_dl:
            if not hasattr(active, "docker"):
                raise ShellSdkError("docker() is not available on the current target.")
            args = parse_call_args_inner(m_dl.group(1))
            if not args:
                return 'Usage: docker.logs("container_name"[, tail_lines])'
            name = str(args[0])
            tail_n = int(args[1]) if len(args) > 1 else 100
            return active.docker().logs(name, tail=tail_n)

        m_ds = re.match(r"^docker\.stats\(\s*(.*?)\s*\)\s*$", t, re.DOTALL)
        if m_ds:
            if not hasattr(active, "docker"):
                raise ShellSdkError("docker() is not available on the current target.")
            args = parse_call_args_inner(m_ds.group(1))
            if len(args) != 1:
                return 'Usage: docker.stats("container_name")'
            data = active.docker().stats(str(args[0]))
            return json.dumps(data, indent=2, default=str)

        droot = re.match(r"^docker(\s*\(\s*\))?(.*)$", t)
        if droot and (droot.group(2) == "" or droot.group(2).startswith(".")):
            if not hasattr(active, "docker"):
                raise ShellSdkError("docker() is not available on the current target.")
            mgr = active.docker()
            rest = droot.group(2).strip()
            if not rest:
                return (
                    "docker(): add a chain, e.g. docker().containers().summarize() "
                    "or use docker.logs(\"name\") / docker.stats(\"name\") for one-shot calls."
                )
            return fluent_chain(mgr, rest)

        # --- systemctl.status|start|stop|restart("unit") ---
        m_sc = re.match(
            r"^systemctl\.(status|start|stop|restart)\(\s*(.*?)\s*\)\s*$",
            t,
            re.DOTALL,
        )
        if m_sc:
            if not hasattr(active, "systemctl"):
                raise ShellSdkError("systemctl is not available on the current target.")
            args = parse_call_args_inner(m_sc.group(2))
            if len(args) != 1:
                return 'Usage: systemctl.status("unit") | systemctl.start("unit") | …'
            unit = str(args[0])
            ctl = active.systemctl()
            act = m_sc.group(1)
            if act == "status":
                return ctl.status(unit)
            if act == "start":
                ctl.start(unit)
                return f"systemctl start {unit!r} OK"
            if act == "stop":
                ctl.stop(unit)
                return f"systemctl stop {unit!r} OK"
            ctl.restart(unit)
            return f"systemctl restart {unit!r} OK"

        # --- processes() fluent root (SDK ProcessCollection chains) ---
        pfm = re.match(r"^processes(\s*\(\s*\))?(.*)$", t)
        if pfm and (pfm.group(2) == "" or pfm.group(2).startswith(".")):
            root = active.processes()
            rest = pfm.group(2).strip()
            if not rest:
                return _summarize_and_display(root)
            return fluent_chain(root, rest)

        # --- disk ---
        dm = _match_disk_ports_cron_env("disk", t)
        if dm and (dm.group(2) == "" or dm.group(2).startswith(".")):
            if not hasattr(active, "disk"):
                raise ShellSdkError("disk() is not available on the current target.")
            root = active.disk()
            rest = dm.group(2).strip()
            if not rest:
                return _summarize_and_display(root)
            return fluent_chain(root, rest)

        # --- ports ---
        pm = _match_disk_ports_cron_env("ports", t)
        if pm and (pm.group(2) == "" or pm.group(2).startswith(".")):
            if not hasattr(active, "ports"):
                raise ShellSdkError("ports() is not available on the current target.")
            root = active.ports()
            rest = pm.group(2).strip()
            if not rest:
                return _summarize_and_display(root)
            return fluent_chain(root, rest)

        # --- network ---
        nm = re.match(r"^network\.(interfaces|connections)\(\)(.*)$", t)
        if nm:
            if not hasattr(active, "network"):
                raise ShellSdkError("network() is not available on the current target.")
            mgr = active.network()
            obj = getattr(mgr, nm.group(1))()
            return fluent_chain(obj, nm.group(2))

        # --- systemctl list_units ---
        if re.match(r"^systemctl\.list_units\(\)", t):
            if not hasattr(active, "systemctl"):
                raise ShellSdkError("systemctl is not available on the current target.")
            root = active.systemctl().list_units()
            rest = t[len("systemctl.list_units()") :]
            return fluent_chain(root, rest)

        # --- services() ---
        sm = re.match(r"^services(\s*\(\s*\))?(.*)$", t)
        if sm and (sm.group(2) == "" or sm.group(2).startswith(".")):
            if not hasattr(active, "services"):
                raise ShellSdkError("services() is not available on the current target.")
            root = active.services()
            rest = sm.group(2).strip()
            if not rest:
                return _summarize_and_display(root)
            return fluent_chain(root, rest)

        # --- cron ---
        cm = _match_disk_ports_cron_env("cron", t)
        if cm and (cm.group(2) == "" or cm.group(2).startswith(".")):
            if not hasattr(active, "cron"):
                raise ShellSdkError("cron() is not available on the current target.")
            root = active.cron()
            rest = cm.group(2).strip()
            if not rest:
                return _summarize_and_display(root)
            return fluent_chain(root, rest)

        # --- users ---
        if t.startswith("users."):
            if not hasattr(active, "users"):
                raise ShellSdkError("users() is not available on the current target.")
            mgr = active.users()
            um = re.match(r"^users\.logged_in\(\)(.*)$", t)
            if um:
                return fluent_chain(mgr.logged_in(), um.group(1))
            um2 = re.match(r"^users\.failed_logins\(\s*([^)]*)\s*\)(.*)$", t)
            if um2:
                inner = um2.group(1).strip()
                path: str | None = None
                if inner:
                    args = parse_call_args_inner(inner)
                    path = str(args[0]) if args else None
                obj = mgr.failed_logins(path) if path else mgr.failed_logins()
                return fluent_chain(obj, um2.group(2))
            return "Usage: users.logged_in().summarize() | users.failed_logins().display()"

        # --- env ---
        em = _match_disk_ports_cron_env("env", t)
        if em and (em.group(2) == "" or em.group(2).startswith(".")):
            if not hasattr(active, "env"):
                raise ShellSdkError("env() is not available on the current target.")
            root = active.env()
            rest = em.group(2).strip()
            if not rest:
                return _summarize_and_display(root)
            return fluent_chain(root, rest)

        # --- containers() alias (Server.containers / RemoteServer.containers) ---
        ctm = re.match(r"^containers(\s*\(\s*\))?(.*)$", t)
        if ctm and (ctm.group(2) == "" or ctm.group(2).startswith(".")):
            if not hasattr(active, "containers"):
                raise ShellSdkError("containers() is not available on the current target.")
            root = active.containers()
            rest = ctm.group(2).strip()
            if not rest:
                return _summarize_and_display(root)
            return fluent_chain(root, rest)

    except OptionalDependencyError as exc:
        return str(exc)
    except ExternalCommandNotFound as exc:
        return str(exc)
    except ShellSdkError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error: {exc}"

    return None
