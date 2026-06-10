"""Natural-language → SDK actions via Ollama (Dev 2).

Maps ``ask <query>`` to the same Server / RemoteServer entry points as the REPL
(processes, logs, disk, ports, cron, env, memory, network, users, docker, services, systemctl),
plus **saved workflows** and **catalog** templates (like ``workflow list`` / ``catalog``).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

from serverkit.ai.jsonutil import parse_model_json
from serverkit.ai.ollama_client import DEFAULT_MODEL, OllamaClient
from serverkit.exceptions import ExternalCommandNotFound, OptionalDependencyError
from serverkit.workflows.manager import WorkflowManager
from serverkit.workflows.workflow import Workflow

if TYPE_CHECKING:
    from serverkit.logs.logfile import LogFile
    from serverkit.processes.manager import ProcessCollection


class Analyzer:
    """Intent routing, diagnostics context, and workflow JSON generation."""

    def __init__(
        self,
        server: Any,
        model: str | None = None,
        *,
        ollama: OllamaClient | None = None,
    ) -> None:
        self.server = server
        cfg_model: str | None = None
        cfg_base: str | None = None
        if hasattr(server, "_config") and server._config is not None:
            cfg_model = server._config.get("ollama", "model", default=None)
        resolved_model = model or cfg_model or DEFAULT_MODEL
        self._ollama = ollama or OllamaClient(model=resolved_model, base_url=cfg_base)

    def ask(self, query: str) -> str:
        q = query.lower()
        if "create a workflow" in q or "make a workflow" in q:
            return self._generate_workflow(query)
        if any(w in q for w in ("why", "diagnose", "what is causing")):
            return self._diagnose(query)
        inv = self._try_workflow_inventory_query(q)
        if inv is not None:
            return inv
        return self._execute_intent(query)

    def _try_workflow_inventory_query(self, q: str) -> str | None:
        """Match ``list workflows`` / ``catalog`` style questions (no Ollama)."""
        if self._matches_list_workflows(q):
            return self._format_workflow_names(
                WorkflowManager().list(),
                empty="No workflows saved.",
            )
        if self._matches_list_catalog(q):
            return self._format_workflow_names(
                WorkflowManager().list_catalog(),
                empty="(no catalog templates)",
            )
        return None

    @staticmethod
    def _matches_list_workflows(q: str) -> bool:
        if re.search(r"\b(list\s+workflows|workflow\s+list)\b", q):
            return True
        if re.search(r"\b(show|what|which|enumerate)\s+(my\s+)?(saved\s+)?workflows\b", q):
            return True
        if re.search(r"\b(saved\s+)?workflow\s+names\b", q):
            return True
        return False

    @staticmethod
    def _matches_list_catalog(q: str) -> bool:
        s = q.strip()
        if s == "catalog":
            return True
        if re.match(r"^(please\s+)?(list|show)\s+catalog\b", s):
            return True
        if re.search(r"\bcatalog\s+templates?\b", q):
            return True
        if re.search(r"\b(bundled|built-?in|builtin)\s+workflow\s+templates?\b", q):
            return True
        return False

    @staticmethod
    def _format_workflow_names(names: list[str], *, empty: str, title: str | None = None) -> str:
        if not names:
            return empty
        body = "\n".join(names)
        if title:
            return f"{title}\n{body}"
        return body

    def _intent_prompt(self, query: str) -> str:
        return f"""You are a server operations assistant (Linux or Windows host, local or SSH). Output ONE JSON object only. No markdown, no prose before or after.

Rules:
- Double quotes for keys and string values.
- No MongoDB-style fields, no // comments.
- "filters": array of {{"action": "<name>", "value": <optional>}}. At most 8 filters.
- Optional "terminal": "summarize" | "display" | "both" (default summarize). For logs only: "json_lines" | "error_rate".
- For "error_rate" on logs, optional top-level "window_minutes" (number, default 5).

Resources and fields:
- processes — filters: memory_above, cpu_above, named, sort_by_memory, sort_by_cpu, for_user (value username), group_by_name (no value; must be last filter).
- logs — required "path" (log file). filters: errors, warnings, contains, match (regex string), tail (n), since, until (ISO datetime strings e.g. 2024-06-01T12:00:00).
- disk — filters: usage_above (percent), mount_contains (substring), sort_by_used.
- ports — filters: listening, port (number), owned_by (pid number).
- cron — filters: suspicious_only.
- env — filters: keys_matching (substring on var names), contains (substring in values).
- memory — no filters.
- network — required "scope": "interfaces" OR "connections". interfaces filters: sort_by_traffic. connections filters: listening, established, on_port (port number).
- users — required "scope": "logged_in" OR "failed_logins". For failed_logins optional "path" (auth log path, default /var/log/auth.log or /var/log/secure).
- docker — required "operation": "containers" | "logs" | "stats". containers filters: running. For logs/stats: "container" (name), optional "tail" (number, logs only).
- services — systemd service list: filters active, named (substring).
- systemctl — "operation": "list_units" OR "status". For status set "unit" (string e.g. ssh.service).
- workflows — "operation": "list_saved" OR "list_catalog" (no filters; same as REPL ``workflow list`` / ``catalog``).

Examples:
{{"resource":"processes","filters":[{{"action":"cpu_above","value":10}}]}}
{{"resource":"logs","path":"/var/log/syslog","filters":[{{"action":"errors"}}],"terminal":"display"}}
{{"resource":"disk","filters":[{{"action":"usage_above","value":80}}]}}
{{"resource":"ports","filters":[{{"action":"listening"}}]}}
{{"resource":"env","filters":[{{"action":"keys_matching","value":"PATH"}}],"terminal":"display"}}
{{"resource":"memory"}}
{{"resource":"network","scope":"connections","filters":[{{"action":"listening"}}]}}
{{"resource":"users","scope":"logged_in"}}
{{"resource":"docker","operation":"containers","filters":[{{"action":"running"}}]}}
{{"resource":"systemctl","operation":"status","unit":"nginx.service"}}
{{"resource":"workflows","operation":"list_saved"}}
{{"resource":"workflows","operation":"list_catalog"}}

Query: {query}
Output JSON on one line, under 900 characters, no markdown fences.
JSON:"""

    def _try_deterministic_intent(self, query: str) -> str | None:
        """Answer common questions without LLM (avoids small-model JSON drift)."""
        q = query.lower()
        m = re.search(
            r"cpu\s*(?:above|over|>|greater\s+than)\s*(\d+(?:\.\d+)?)\s*(?:%|percent)?\b",
            q,
        )
        if m:
            return self._run_action(
                {
                    "resource": "processes",
                    "filters": [{"action": "cpu_above", "value": float(m.group(1))}],
                }
            )
        m = re.search(
            r"(?:memory|ram)\s*(?:above|over|>|greater\s+than)\s*(\d+(?:\.\d+)?)\s*(?:mb|m\b|gb|gig)?\b",
            q,
        )
        if m:
            return self._run_action(
                {
                    "resource": "processes",
                    "filters": [{"action": "memory_above", "value": float(m.group(1))}],
                }
            )
        m = re.search(
            r"(?:processes|apps)\s+(?:named|called|for|matching)\s+['\"]?([a-z0-9._-]+)['\"]?",
            q,
        )
        if m:
            return self._run_action(
                {
                    "resource": "processes",
                    "filters": [{"action": "named", "value": m.group(1)}],
                }
            )
        m = re.search(
            r"(?:disk|disks|partition|mount|usage)\s*(?:above|over|>|greater\s+than)\s*(\d+)\s*(?:%|percent)?",
            q,
        ) or re.search(
            r"(?:above|over|>|)\s*(\d+)\s*(?:%|percent)\s*(?:disk|usage|partition)",
            q,
        )
        if m and ("disk" in q or "partition" in q or "mount" in q or "usage" in q):
            return self._run_action(
                {
                    "resource": "disk",
                    "filters": [{"action": "usage_above", "value": float(m.group(1))}],
                }
            )
        if re.search(
            r"\b(listening|open)\s+ports\b|\bports?\s+(that\s+are\s+)?listening\b",
            q,
        ):
            return self._run_action(
                {"resource": "ports", "filters": [{"action": "listening"}]}
            )
        m = re.search(
            r"(?:^|\s)port\s*#?\s*(\d{1,5})\b|\bon\s+port\s+(\d{1,5})\b",
            q,
        )
        if m:
            port_n = int(m.group(1) or m.group(2))
            return self._run_action(
                {"resource": "ports", "filters": [{"action": "port", "value": port_n}]}
            )
        if "suspicious" in q and "cron" in q:
            return self._run_action(
                {"resource": "cron", "filters": [{"action": "suspicious_only"}]}
            )
        if re.search(r"\b(show|get|what)\s+(memory|ram)\b|\bmemory\s+stats\b", q):
            return self._run_action({"resource": "memory"})
        if ("path" in q or "PATH" in query) and ("env" in q or "environment" in q):
            return self._run_action(
                {
                    "resource": "env",
                    "filters": [{"action": "keys_matching", "value": "PATH"}],
                    "terminal": "display",
                }
            )
        if re.search(r"\blogged[- ]in\b|\bwho\s+is\s+logged\b", q) and "user" in q:
            return self._run_action({"resource": "users", "scope": "logged_in"})
        return None

    def _execute_intent(self, query: str) -> str:
        direct = self._try_deterministic_intent(query)
        if direct is not None:
            return direct
        prompt = self._intent_prompt(query)
        raw = self._ollama.ask(
            prompt,
            temperature=0.05,
            num_predict=520,
            stop=["```", "\n\nThe ", "\n\n## "],
        )
        action = parse_model_json(raw)
        if action is None:
            cpu_n = re.search(
                r"cpu\s*(?:above|over|>|greater\s+than)\s*(\d+(?:\.\d+)?)",
                query.lower(),
            )
            mem_n = re.search(
                r"(?:memory|ram)\s*(?:above|over|>|greater\s+than)\s*(\d+(?:\.\d+)?)",
                query.lower(),
            )
            if cpu_n:
                repair = (
                    "Output exactly this JSON and nothing else (no markdown, no prose): "
                    f'{{"resource":"processes","filters":[{{"action":"cpu_above","value":{float(cpu_n.group(1))}}}]}}'
                )
            elif mem_n:
                repair = (
                    "Output exactly this JSON and nothing else: "
                    f'{{"resource":"processes","filters":[{{"action":"memory_above","value":{float(mem_n.group(1))}}}]}}'
                )
            else:
                repair = (
                    "Your previous answer was not valid JSON. Reply with ONE JSON object only, "
                    "under 900 bytes. No // comments.\n"
                    f"User query: {query}\n"
                    f"Broken output (trimmed): {raw[:500]!r}\n"
                    "Valid examples:\n"
                    '{"resource":"disk","filters":[{"action":"usage_above","value":80}]}\n'
                    '{"resource":"ports","filters":[{"action":"listening"}]}\n'
                    '{"resource":"logs","path":"/var/log/syslog","filters":[{"action":"errors"}]}\n'
                    '{"resource":"workflows","operation":"list_saved"}\n'
                )
            raw2 = self._ollama.ask(
                repair,
                temperature=0.0,
                num_predict=360,
                stop=["```", "\n"],
            )
            action = parse_model_json(raw2)
            if action is None:
                fallback = self._try_deterministic_intent(query)
                if fallback is not None:
                    return fallback
                return (
                    "Could not parse model JSON (even after retry). "
                    "Try a larger model in config `ollama.model`, or rephrase.\n\n"
                    f"First response:\n{raw}\n\nRetry:\n{raw2}"
                )
        return self._run_action(action)

    def _run_action(self, action: dict[str, Any]) -> str:
        resource = (action.get("resource") or "").lower()
        try:
            if resource == "processes":
                return self._run_processes(action)
            if resource == "logs":
                return self._run_logs(action)
            if resource == "disk":
                return self._run_disk(action)
            if resource == "ports":
                return self._run_ports(action)
            if resource == "cron":
                return self._run_cron(action)
            if resource == "env":
                return self._run_env(action)
            if resource == "memory":
                return self._terminal_output(self.server.memory(), action.get("terminal"))
            if resource == "network":
                return self._run_network(action)
            if resource == "users":
                return self._run_users(action)
            if resource == "docker":
                return self._run_docker(action)
            if resource == "services":
                return self._run_services(action)
            if resource == "systemctl":
                return self._run_systemctl(action)
            if resource == "workflows":
                return self._run_workflows(action)
        except OptionalDependencyError as exc:
            return f"{exc}\nInstall the documented optional extra (e.g. serverkit[docker])."
        except ExternalCommandNotFound as exc:
            return str(exc)
        except Exception as exc:
            return f"SDK error while running intent ({resource!r}): {exc}"
        return f"Unsupported or empty resource: {resource!r}. Use help for supported REPL/SDK commands."

    @staticmethod
    def _normalized_filters(filters: Any) -> list[dict[str, Any]]:
        if not isinstance(filters, list):
            return []
        out: list[dict[str, Any]] = []
        for item in filters:
            if isinstance(item, dict) and isinstance(item.get("action"), str):
                out.append(item)
        return out

    def _run_processes(self, action: dict[str, Any]) -> str:
        from serverkit.processes.manager import ProcessCollection

        filters = self._normalized_filters(action.get("filters"))
        collection: ProcessCollection = self.server.processes()
        for i, f in enumerate(filters):
            act = f.get("action")
            if act == "group_by_name":
                groups = collection.group_by_name()
                if filters[i + 1 :]:
                    return "group_by_name must be the last process filter in the intent JSON."
                return self._format_grouped_processes(groups)
            collection = self._apply_process_filter(collection, f)
        return self._terminal_output(collection, action.get("terminal"))

    def _run_logs(self, action: dict[str, Any]) -> str:
        from serverkit.logs.logfile import LogFile

        path = action.get("path") or action.get("log_path")
        if not path:
            return "Missing logs path in JSON (expected 'path')."
        log: LogFile = self.server.logs(str(path))
        for f in self._normalized_filters(action.get("filters")):
            log = self._apply_log_filter(log, f)
        term = (action.get("terminal") or "summarize").lower()
        if term == "json_lines":
            rows = log.json_lines()
            return json.dumps(rows[:50], indent=2, default=str)
        if term == "error_rate":
            w = float(action.get("window_minutes", 5))
            r = log.error_rate(w)
            return (
                f"Errors: {r.count} in {r.window_minutes:g} min window "
                f"({r.rate_per_minute:.2f} per minute)."
            )
        return self._terminal_output(log, term)

    def _run_disk(self, action: dict[str, Any]) -> str:
        col = self.server.disk()
        for f in self._normalized_filters(action.get("filters")):
            col = self._apply_disk_filter(col, f)
        return self._terminal_output(col, action.get("terminal"))

    def _run_ports(self, action: dict[str, Any]) -> str:
        col = self.server.ports()
        for f in self._normalized_filters(action.get("filters")):
            col = self._apply_ports_filter(col, f)
        return self._terminal_output(col, action.get("terminal"))

    def _run_cron(self, action: dict[str, Any]) -> str:
        col = self.server.cron()
        for f in self._normalized_filters(action.get("filters")):
            col = self._apply_cron_filter(col, f)
        return self._terminal_output(col, action.get("terminal"))

    def _run_env(self, action: dict[str, Any]) -> str:
        snap = self.server.env()
        for f in self._normalized_filters(action.get("filters")):
            snap = self._apply_env_filter(snap, f)
        return self._terminal_output(snap, action.get("terminal"))

    def _run_network(self, action: dict[str, Any]) -> str:
        scope = (action.get("scope") or "interfaces").lower()
        nm = self.server.network()
        if scope == "interfaces":
            col = nm.interfaces()
            for f in self._normalized_filters(action.get("filters")):
                col = self._apply_interface_filter(col, f)
            return self._terminal_output(col, action.get("terminal"))
        if scope == "connections":
            col = nm.connections()
            for f in self._normalized_filters(action.get("filters")):
                col = self._apply_connection_filter(col, f)
            return self._terminal_output(col, action.get("terminal"))
        return f"Unknown network scope {scope!r}. Use interfaces or connections."

    def _run_users(self, action: dict[str, Any]) -> str:
        scope = (action.get("scope") or "logged_in").lower()
        um = self.server.users()
        if scope == "logged_in":
            col = um.logged_in()
            return self._terminal_output(col, action.get("terminal"))
        if scope == "failed_logins":
            log_path = action.get("path") or "/var/log/auth.log"
            col = um.failed_logins(str(log_path))
            return self._terminal_output(col, action.get("terminal"))
        return f"Unknown users scope {scope!r}. Use logged_in or failed_logins."

    def _run_docker(self, action: dict[str, Any]) -> str:
        op = (action.get("operation") or "containers").lower()
        dm = self.server.docker()
        if op == "containers":
            col = dm.containers()
            for f in self._normalized_filters(action.get("filters")):
                act = f.get("action")
                if act == "running":
                    col = col.running()
            return self._terminal_output(col, action.get("terminal"))
        if op == "logs":
            name = action.get("container") or action.get("name")
            if not name:
                return "docker logs intent requires string field 'container'."
            tail = int(action.get("tail", 100))
            return dm.logs(str(name), tail=tail)
        if op == "stats":
            name = action.get("container") or action.get("name")
            if not name:
                return "docker stats intent requires string field 'container'."
            stats = dm.stats(str(name))
            return json.dumps(stats, indent=2, default=str)
        return f"Unknown docker operation {op!r}. Use containers, logs, or stats."

    def _run_services(self, action: dict[str, Any]) -> str:
        col = self.server.services()
        for f in self._normalized_filters(action.get("filters")):
            col = self._apply_service_collection_filter(col, f)
        return self._terminal_output(col, action.get("terminal"))

    def _run_systemctl(self, action: dict[str, Any]) -> str:
        op = (action.get("operation") or "list_units").lower()
        sc = self.server.systemctl()
        if op == "list_units":
            col = sc.list_units()
            for f in self._normalized_filters(action.get("filters")):
                col = self._apply_systemctl_service_collection_filter(col, f)
            return self._terminal_output(col, action.get("terminal"))
        if op == "status":
            unit = action.get("unit") or action.get("name")
            if not unit:
                return "systemctl status intent requires string field 'unit'."
            return sc.status(str(unit))
        return f"Unknown systemctl operation {op!r}. Use list_units or status."

    def _run_workflows(self, action: dict[str, Any]) -> str:
        op = (action.get("operation") or "list_saved").lower()
        wm = WorkflowManager()
        if op == "list_saved":
            return self._format_workflow_names(wm.list(), empty="No workflows saved.")
        if op == "list_catalog":
            return self._format_workflow_names(wm.list_catalog(), empty="(no catalog templates)")
        return f"Unknown workflows operation {op!r}. Use list_saved or list_catalog."

    @staticmethod
    def _format_grouped_processes(groups: dict[str, Any]) -> str:
        from serverkit.processes.manager import ProcessCollection

        parts: list[str] = []
        for name, col in sorted(groups.items()):
            if not isinstance(col, ProcessCollection):
                continue
            n = len(col)
            summ = col.summarize()
            parts.append(f"=== {name} ({n} processes) ===\n{summ}")
        return "\n\n".join(parts) if parts else "(no groups)"

    @staticmethod
    def _terminal_output(obj: Any, terminal: str | None) -> str:
        term = (terminal or "summarize").lower()
        if term == "display" and callable(getattr(obj, "display", None)):
            return obj.display()
        if term == "both":
            chunks: list[str] = []
            if callable(getattr(obj, "summarize", None)):
                chunks.append(obj.summarize())
            if callable(getattr(obj, "display", None)):
                chunks.append(obj.display())
            return "\n\n".join(c for c in chunks if c)
        if callable(getattr(obj, "summarize", None)):
            return obj.summarize()
        if callable(getattr(obj, "display", None)):
            return obj.display()
        return str(obj)

    def _apply_process_filter(self, collection: Any, f: dict[str, Any]) -> Any:
        act = f.get("action")
        val = f.get("value")
        if act == "memory_above":
            return collection.memory_above(float(val))
        if act == "cpu_above":
            return collection.cpu_above(float(val))
        if act == "named":
            return collection.named(str(val))
        if act == "sort_by_memory":
            return collection.sort_by_memory()
        if act == "sort_by_cpu":
            return collection.sort_by_cpu()
        if act == "for_user":
            return collection.for_user(str(val))
        return collection

    def _apply_log_filter(self, log: Any, f: dict[str, Any]) -> Any:
        act = f.get("action")
        val = f.get("value")
        if act == "errors":
            return log.errors()
        if act == "warnings":
            return log.warnings()
        if act == "contains":
            return log.contains(str(val))
        if act == "match":
            return log.match(str(val))
        if act == "tail":
            return log.tail(int(val))
        if act == "since":
            ts = self._parse_iso_datetime(val)
            if ts is None:
                return log
            return log.since(ts)
        if act == "until":
            ts = self._parse_iso_datetime(val)
            if ts is None:
                return log
            return log.until(ts)
        if act == "summarize":
            return log
        return log

    @staticmethod
    def _parse_iso_datetime(val: Any) -> datetime | None:
        if val is None:
            return None
        s = str(val).strip()
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _apply_disk_filter(col: Any, f: dict[str, Any]) -> Any:
        act = f.get("action")
        val = f.get("value")
        if act == "usage_above":
            return col.usage_above(float(val))
        if act == "mount_contains":
            return col.mount_contains(str(val))
        if act == "sort_by_used":
            return col.sort_by_used()
        return col

    @staticmethod
    def _apply_ports_filter(col: Any, f: dict[str, Any]) -> Any:
        act = f.get("action")
        val = f.get("value")
        if act == "listening":
            return col.listening()
        if act == "port":
            return col.port(int(val))
        if act == "owned_by":
            return col.owned_by(int(val))
        return col

    @staticmethod
    def _apply_cron_filter(col: Any, f: dict[str, Any]) -> Any:
        if f.get("action") == "suspicious_only":
            return col.suspicious_only()
        return col

    @staticmethod
    def _apply_env_filter(snap: Any, f: dict[str, Any]) -> Any:
        act = f.get("action")
        val = f.get("value")
        if act == "keys_matching":
            return snap.keys_matching(str(val))
        if act == "contains":
            return snap.contains(str(val))
        return snap

    @staticmethod
    def _apply_interface_filter(col: Any, f: dict[str, Any]) -> Any:
        if f.get("action") == "sort_by_traffic":
            return col.sort_by_traffic()
        return col

    @staticmethod
    def _apply_connection_filter(col: Any, f: dict[str, Any]) -> Any:
        act = f.get("action")
        val = f.get("value")
        if act == "listening":
            return col.listening()
        if act == "established":
            return col.established()
        if act == "on_port":
            return col.on_port(int(val))
        return col

    @staticmethod
    def _apply_service_collection_filter(col: Any, f: dict[str, Any]) -> Any:
        act = f.get("action")
        val = f.get("value")
        if act == "active":
            return col.active()
        if act == "named":
            return col.named(str(val))
        return col

    @staticmethod
    def _apply_systemctl_service_collection_filter(col: Any, f: dict[str, Any]) -> Any:
        act = f.get("action")
        val = f.get("value")
        if act == "active":
            return col.active()
        if act == "named":
            return col.named(str(val))
        return col

    def _diagnose(self, query: str) -> str:
        blocks: list[str] = []
        try:
            procs = self.server.processes().sort_by_memory().all()[:10]
            proc_summary = "\n".join(
                f"{p.name}: {p.memory_mb:.0f}MB, CPU {p.cpu_percent:.1f}%" for p in procs
            )
            blocks.append("Top 10 processes by memory:\n" + proc_summary)
        except Exception as exc:
            blocks.append(f"Processes: (unavailable: {exc})")
        for label, fn in (
            ("Memory", lambda: self.server.memory().summarize()),
            ("Disk", lambda: self.server.disk().summarize()),
            ("Ports (sample)", lambda: self.server.ports().listening().summarize()),
        ):
            try:
                blocks.append(f"{label}:\n{fn()}")
            except Exception as exc:
                blocks.append(f"{label}: (unavailable: {exc})")
        try:
            blocks.append("Cron (suspicious sample):\n" + self.server.cron().suspicious_only().summarize())
        except Exception as exc:
            blocks.append(f"Cron: (unavailable: {exc})")
        ctx = "\n\n".join(str(b) for b in blocks)
        prompt = f"""You are a server diagnostician. Use the live metrics below (local or remote target).

{ctx}

User question: {query}

Give a clear, concise diagnosis in 3-6 lines. If a metric block is missing, say what else to check."""
        return self._ollama.ask(prompt, temperature=0.4, num_predict=500)

    def _workflow_prompt(self, query: str) -> str:
        return f"""Convert this request into ONE ServerKit workflow JSON object.
Return ONLY valid JSON. No markdown, no // comments, no text before or after.

Required keys: schema_version (2), name, created_at (null), last_run (null), steps (array).

Example steps for high-memory audit:
{{
  "schema_version": 2,
  "name": "high_memory_audit",
  "created_at": null,
  "last_run": null,
  "steps": [
    {{"type": "process_filter", "memory_above": 500, "cpu_above": null, "named": null}},
    {{"type": "sort", "field": "memory"}},
    {{"type": "summary"}}
  ]
}}

Step types allowed: process_filter, sort, log_filter, tail, summary, export, chain, conditional
process_filter fields: memory_above, cpu_above, named (use null for unused).

Request: {query}
JSON:"""

    def _generate_workflow(self, query: str) -> str:
        prompt = self._workflow_prompt(query)
        raw = self._ollama.ask(prompt, temperature=0.05, num_predict=700)
        wf_data = parse_model_json(raw)
        if wf_data is None:
            raw2 = self._ollama.ask(
                "Return only valid JSON for a workflow (schema_version 2, name, steps). "
                "No // comments. No keys except JSON. Under 800 bytes.\n"
                f"Broken output:\n{raw[:700]}",
                temperature=0.0,
                num_predict=600,
            )
            wf_data = parse_model_json(raw2)
            if wf_data is None:
                return f"Failed to parse workflow JSON.\nRaw:\n{raw}\n\nRetry:\n{raw2}"
        try:
            wf = Workflow.from_dict(wf_data)
            wf.save()
            return f"Workflow created and saved: {wf.name}"
        except Exception as exc:
            return f"Failed to generate workflow: {exc}\nRaw:\n{raw}"
