# Dev 2 integration contracts

**Source of truth for shell + AI integration.** SDK is at **v0.3.0** (Dev 1 core + future extensions). If this file disagrees with `docs/serverkit_dev2_shell_ai.pdf`, **trust this file and the code**.

## Ownership

| Layer | Owner | Path |
|-------|--------|------|
| SDK facade, resources, workflows, remote | Dev 1 | `serverkit/*` except `shell/`, `ai/` |
| Interactive REPL (`serverkit` CLI) | Dev 2 | `serverkit/shell/` |
| Ollama / natural language | Dev 2 | `serverkit/ai/` |

Dev 2 should **not** reimplement psutil, systemctl, or SSH — call `Server` / `RemoteServer` only.

---

## Entry points

### Local

```python
from serverkit import Server

server = Server()  # loads ~/.serverkit/config.json
```

### Remote (optional `[remote]` extra)

```python
with Server.connect("host", user="deploy", key_path="~/.ssh/id_ed25519") as remote:
    remote.processes()
    remote.run("memory_audit")
```

`RemoteServer` supports workflow-facing methods only: `processes()`, `logs(path)`, `memory()`, `services()`, `service(name)`, `run(name, …)`. **Not on remote v1:** `disk()`, `docker()`, `cron()`, `workflow()` builder, `import_workflow()` (import locally, then `remote.run(name)`).

---

## `Server` / `RemoteServer` methods

| Method | Returns | Notes |
|--------|---------|--------|
| `processes()` | `ProcessCollection` | Eager scan; may show ASCII spinner if `output.show_progress` |
| `logs(path)` | `LogFile` | Local file; remote uses SSH tail/cat → `LogFile.from_lines` |
| `workflow(name)` | `WorkflowBuilder` | Local only |
| `run(name, dry_run=False, executor=None)` | `dict` | Passes `self` as `context["_server"]` |
| `import_workflow(name)` | `Workflow` | Bundled catalog → saves under `~/.serverkit/workflows/` |
| `memory()` | `MemorySnapshot` | |
| `disk()` | `DiskCollection` | `.largest_files(root, limit=20)` → `FileEntryCollection` |
| `network()` | `NetworkManager` | |
| `ports()` | `PortCollection` | |
| `systemctl()` | `SystemctlManager` | Low-level; prefer `services()` / `service()` |
| `services()` | `ServiceCollection` | |
| `service(name)` | `ServiceHandle` | `.status()`, `.start()`, `.stop()`, `.restart()`, `.is_active()` |
| `cron()` | `CronCollection` | |
| `users()` | `UsersManager` | |
| `env()` | `EnvSnapshot` | |
| `docker()` | `DockerManager` | Requires `pip install serverkit[docker]` |
| `containers()` | `ContainerCollection` | Alias for `docker().containers()` |
| `Server.connect(...)` | `RemoteServer` | Requires `pip install serverkit[remote]` |

---

## Fluent collections (REPL must support chaining)

Most resources return a **fluent collection** that mutates in place and returns `self`:

```python
server.processes().memory_above(500).sort_by_memory().summarize()
server.processes().display_by_name()   # app-level RSS (Mission Center style)
server.logs("app.log").errors().tail(20).summarize()
server.disk().usage_above(80).sort_by_used().display()
server.disk().largest_files("/home", limit=10).display()
server.services().active().named("nginx").summarize()
```

### Terminal methods (print these in REPL)

| Method | Result |
|--------|--------|
| `.all()` | `list` of domain objects or lines |
| `.summarize()` / `.summarise()` | `str` — use `print()` in REPL (repr does not expand newlines) |
| `.display(use_rich=None)` | `str` table (Rich if installed + config) |
| `.export(path, fmt="csv")` | writes file; returns `self` for chaining |

`ProcessCollection` also has `.group_by_name()`, `.display_by_name()`, `.kill_all()` / `.terminate_all()` — destructive; REPL should confirm or restrict.

---

## Workflows

### Storage

- User workflows: `~/.serverkit/workflows/{name}.json`
- Version snapshots: `~/.serverkit/workflows/{name}/versions/v_{timestamp}.json` (when versioning enabled)
- Catalog templates: `serverkit/workflows/catalog/*.json` (read-only package data)

### Catalog (REPL-friendly commands)

```python
from serverkit.workflows.manager import WorkflowManager

WorkflowManager().list_catalog()
# ['log_error_scan', 'memory_audit', 'nginx_health_check', ...]

server.import_workflow("memory_audit")
server.run("memory_audit", dry_run=True)
```

### JSON contract

- `schema_version: 2`
- Step `type` strings (registered in `StepFactory`):  
  `process_filter`, `sort`, `log_filter`, `tail`, `summary`, `export`, `chain`, `conditional`

### Runtime context (`run()` return value)

Workflow steps read/write a shared `dict`. Dev 2 should not assume fixed keys, but commonly:

| Key | Set by |
|-----|--------|
| `_server` | `Workflow.run(server=...)` — **use this for local vs remote** |
| `processes` | `ProcessFilterStep`, `SortStep` |
| `log_path`, `log_file`, `log_lines` | log steps |
| `summary` | `SummaryStep` |

Remote workflows: `srv = Server.connect("vm1"); srv.run("audit")` — steps call `_server(context).processes()` on the remote facade.

### Builder (local)

```python
server.workflow("audit").processes().memory_above(1000).sort_by_memory().summarize().save()
```

---

## Configuration

Path: `~/.serverkit/config.json` (merge with defaults in `serverkit/config.py`).

| Key | Purpose |
|-----|---------|
| `output.use_rich` | Table rendering |
| `output.show_progress` | ASCII spinner on long scans (default `false`) |
| `workflow.executor` | `sequential` or `parallel` |
| `workflow.versioning` | Save versioned copies on `.save()` |
| `remote.default_user`, `remote.key_path`, `remote.port` | SSH defaults for `Server.connect()` |
| `ollama.model` | Dev 2 AI default model |

Load once per REPL session: `Config.load()` or `Server(config=...)`.

---

## Exceptions (map to user-facing REPL messages)

| Exception | When |
|-----------|------|
| `ProcessNotFound` | Invalid PID / kill |
| `WorkflowNotFound` | Missing workflow or catalog name |
| `LogFileNotFound` | Bad log path |
| `ServiceNotFound` | systemctl failure |
| `OptionalDependencyError` | Missing `[docker]`, `[remote]`, or `[rich]` |
| `RemoteConnectionError` | SSH connect or remote command failed |
| `WorkflowValidationError` | Invalid workflow JSON |
| `StepExecutionError` | Step runtime failure |
| `ConfigurationError` | Bad config file |

---

## REPL implementation notes (Dev 2)

**Goal:** faster than ChatGPT for forgotten commands — discoverable verbs, not raw shell.

Suggested scope for v1 REPL:

1. Hold a session `Server` instance (and optional `RemoteServer`).
2. Evaluate Python-like chains or a thin command DSL that maps to SDK calls.
3. Built-in helpers (examples):
   - `run <workflow> [--dry-run]`
   - `import <catalog_name>`
   - `catalog` → `list_catalog()`
   - `connect <host> [--user] [--key] [--port] [--password] [--timeout] [--no-agent] [--no-look-for-keys]`
   - `help` / tab-complete on `server.processes().`
4. Always `print(x.summarize())` and `print(x.display())`, not bare `summarize()` in interactive mode.
5. Entry point already wired: `serverkit` → `serverkit.shell.repl:main` in `pyproject.toml`.
6. Natural language: `ask <query>` in the REPL (requires `pip install serverkit[ai]` and Ollama). Same routing is available as `Server().ask(query)` (lazy import).

**Do not** shell out to `ps`/`grep` directly unless translating into SDK calls for consistency.

---

## AI layer (Dev 2)

Stubs: `serverkit/ai/ollama_client.py`, `serverkit/ai/analyzer.py`.

Intended flow:

1. User phrase → structured intent (workflow name, resource, filters).
2. Prefer **catalog** + **saved workflows** before inventing new JSON.
3. Execute via `server.run(...)` or generated builder chain; never bypass `_server` in workflow context.

Config: `ollama.model` in user config. AI is optional; REPL alone should be useful.

---

## Optional extras

```bash
pip install serverkit[rich]    # tables
pip install serverkit[docker]  # containers
pip install serverkit[remote]  # Server.connect
pip install serverkit[all]
```

---

## Testing (Dev 2)

```bash
pytest                    # offline; mocks remote/docker
pytest -m integration     # live OS (Dev 1)
```

Add Dev 2 tests under `tests/` for REPL parsing/dispatch only; no live SSH in CI.

---

## Changelog vs original Dev 2 PDF

Dev 1 delivered beyond the original SDK milestone:

- Services facade (`service().restart()`)
- Workflow catalog + `import_workflow(name)`
- `FileEntryCollection` / `disk().largest_files()`
- `containers()` alias
- Full `RemoteServer` + `Server.connect()` (paramiko)
- `core/protocol.py` — shared facade typing for local/remote

Update this file when Dev 1 adds new public `Server` methods.
