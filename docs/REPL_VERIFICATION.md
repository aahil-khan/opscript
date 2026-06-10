# REPL verification checklist

Run `serverkit`, then try the lines below. Adjust paths, hosts, and container names for your environment.

## Screen

```text
clr
clear
```

Same effect: clear the REPL terminal (`clr` / `clear` are handled in the shell parser; on Windows this runs `cls`, on Unix `clear`).

---

## Local (`disconnect` or fresh shell)

### Disk / ports / cron / env

These use the same **`disk` / `ports` / `cron` / `env`** entry points as `help` (optional `()`, then fluent chains). On **Windows**, `cron` may be empty; **`disk` / `ports`** need psutil/OS support.

```text
disk
disk()
disk.usage_above(80).summarize()
disk.mount_contains("C").display()

ports
ports()
ports.listening().summarize()
ports.port(443).display()

cron
cron()
cron.suspicious_only().display()

env
env()
env.keys_matching("PATH").display()
env.contains("OneDrive").display()
```

### Logs (including SDK-style terminals)

```text
logs("C:\Windows\Logs\DISM\dism.log").contains("DISM").display()
logs("C:\path\to\your.log").since("2024-01-01T00:00:00").display()
logs("C:\path\to\your.log").until("2099-12-31T23:59:59").display()
logs("C:\path\to\jsonl.log").json_lines()
logs("C:\path\to\your.log").error_rate()
logs("C:\path\to\your.log").error_rate(10)
```

### Processes (grouped dict terminal)

```text
processes().group_by_name().summarize()
processes().group_by_name().display()
```

### Docker manager fluent (local needs `pip install serverkit[docker]` + Docker running)

```text
docker().containers().summarize()
docker().containers().running().display()
docker.logs("CONTAINER_NAME", 50)
docker.stats("CONTAINER_NAME")
```

### Memory

```text
memory
memory.json
```

### Systemd (Linux only; on Windows expect `ExternalCommandNotFound` / clear message)

```text
systemctl.list_units().summarize()
systemctl.status("ssh.service")
```

---

## Remote (`pip install serverkit[remote]`)

After **`connect`**, the same **disk / ports / cron / env** shapes run on the **SSH target** (remote `df`, `ss`, crontabs, `printenv`, etc.):

```text
connect USER@HOST --key C:\Users\YOU\.ssh\id_ed25519 --timeout 45
disk
disk.usage_above(50).summarize()
ports
ports.listening().summarize()
cron.suspicious_only().summarize()
env.keys_matching("PATH").display()
network.interfaces().summarize()
network.connections().summarize()
users.logged_in().summarize()
users.failed_logins("/var/log/auth.log").display()
docker().containers().summarize()
docker.logs("CONTAINER_NAME", 100)
processes().memory_above(100).summarize()
memory
ask list processes with cpu above 5 percent
disconnect
```

### SSH connect flags (parity with `Server.connect`)

```text
connect HOST --user myuser --password SECRET --port 2222 --timeout 60
connect HOST --no-agent --no-look-for-keys
```

---

## Workflow one-liner (local only — must `disconnect` first)

```text
workflow("wf_demo").processes().memory_above(200).summarize().save()
```

---

Full automated suite: from repo root `python -m pytest` (expect **2 deselected** integration tests if configured).
