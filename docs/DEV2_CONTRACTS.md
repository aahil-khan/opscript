# Dev 2 integration contracts

Stable SDK surface for shell and AI layers.

## Server entry points

| Method | Returns |
|--------|---------|
| `server.processes()` | `ProcessCollection` |
| `server.logs(path)` | `LogFile` |
| `server.workflow(name)` | `WorkflowBuilder` |
| `server.run(name, dry_run=False, executor=None)` | `dict` context |
| `server.memory()` | `MemorySnapshot` |
| `server.disk()` | `DiskCollection` |
| `server.network()` | `NetworkManager` |
| `server.ports()` | `PortCollection` |
| `server.systemctl()` | `SystemctlManager` |
| `server.cron()` | `CronCollection` |
| `server.users()` | `UsersManager` |
| `server.env()` | `EnvSnapshot` |
| `server.docker()` | `DockerManager` (requires `[docker]` extra) |
| `server.containers()` | Same as `docker().containers()` |
| `server.services()` | `ServiceCollection` |
| `server.service(name)` | `ServiceHandle` (`.restart()`, `.start()`, …) |
| `server.import_workflow(name)` | `Workflow` from bundled catalog |
| `Server.connect(host, user=None, **ssh)` | `RemoteServer` (requires `[remote]` extra) |

`RemoteServer` implements the same workflow-facing methods: `processes()`, `logs(path)`, `memory()`, `services()`, `service(name)`, `run(name, …)`.

## Terminal methods

- `.all()` → `list`
- `.summarize()` → `str` (plain text; use `print()` in REPL)

## Workflow JSON

Includes `schema_version: 2`. Steps use canonical `type` strings registered in `StepFactory`.
