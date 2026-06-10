"""Parse common Linux CLI output fetched over SSH into SDK collections."""

from __future__ import annotations

import re

from serverkit.cron.job import CronJob
from serverkit.disk.partition import Partition
from serverkit.network.connection import Connection, NetworkInterface
from serverkit.ports.port import Port


def disk_partitions_from_df(output: str) -> list[Partition]:
    """Parse ``df -P`` (POSIX) output into Partition rows."""
    parts_out: list[Partition] = []
    for raw in output.strip().splitlines():
        line = raw.strip()
        if not line or line.startswith("Filesystem"):
            continue
        bits = line.split()
        if len(bits) < 6:
            continue
        device = bits[0]
        try:
            total_kb = float(bits[1])
            used_kb = float(bits[2])
            avail_kb = float(bits[3])
        except ValueError:
            continue
        pct_s = bits[4].rstrip("%")
        try:
            pct = float(pct_s)
        except ValueError:
            pct = 100.0 * used_kb / total_kb if total_kb else 0.0
        mount = " ".join(bits[5:])
        total_mb = total_kb / 1024
        used_mb = used_kb / 1024
        parts_out.append(
            Partition(
                device=device,
                mountpoint=mount,
                fstype="",
                total_mb=total_mb,
                used_mb=used_mb,
                percent=pct,
            )
        )
    return parts_out


def env_dict_from_printenv(output: str) -> dict[str, str]:
    """Parse ``printenv`` / ``env`` KEY=value lines."""
    env: dict[str, str] = {}
    for line in output.splitlines():
        line = line.rstrip("\r")
        if not line or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k:
            env[k] = v
    return env


def cron_jobs_from_remote_text(blob: str) -> list[CronJob]:
    """Parse crontab bodies with ``# FILE/path`` source markers between files."""
    jobs: list[CronJob] = []
    current_source = "remote"
    for line in blob.splitlines():
        if line.startswith("# FILE"):
            current_source = line[len("# FILE") :].strip() or current_source
            continue
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        schedule = " ".join(parts[:5])
        jobs.append(CronJob(schedule, parts[5], current_source))
    return jobs


def network_interfaces_from_proc_net_dev(output: str) -> list[NetworkInterface]:
    """Rough RX/TX MB from /proc/net/dev (since boot)."""
    items: list[NetworkInterface] = []
    for line in output.strip().splitlines():
        if ":" not in line:
            continue
        name, rest = line.split(":", 1)
        name = name.strip()
        if name == "lo":
            continue
        cols = rest.split()
        if len(cols) < 16:
            continue
        try:
            recv_b = int(cols[0])
            sent_b = int(cols[8])
        except ValueError:
            continue
        items.append(
            NetworkInterface(
                name,
                sent_b / 1024 / 1024,
                recv_b / 1024 / 1024,
            )
        )
    return items


def connections_from_ss(output: str) -> list[Connection]:
    """Parse ``ss -tan`` table (skip header)."""
    conns: list[Connection] = []
    lines = [ln.rstrip() for ln in output.strip().splitlines() if ln.strip()]
    start = 1 if lines and lines[0].startswith("State") else 0
    for line in lines[start:]:
        parts = line.split(None, 5)
        if len(parts) < 5:
            continue
        state, local_a, peer = parts[0], parts[3], parts[4]
        pid = None
        m = re.search(r"pid=(\d+)", line)
        if m:
            pid = int(m.group(1))
        conns.append(
            Connection(
                fd=-1,
                family="inet",
                type="tcp",
                local_addr=local_a,
                remote_addr=peer,
                status=state,
                pid=pid,
            )
        )
    return conns


def ports_from_ss(output: str) -> list[Port]:
    """Listening sockets from ``ss -tulpn`` (best-effort)."""
    ports: list[Port] = []
    seen: set[tuple[int, str]] = set()
    lines = [ln.rstrip() for ln in output.strip().splitlines() if ln.strip()]
    start = 1 if lines and ("Netid" in lines[0] or "State" in lines[0]) else 0
    for line in lines[start:]:
        if "LISTEN" not in line and "UNCONN" not in line:
            continue
        m = re.search(r":(\d+)\s+", line)
        if not m:
            continue
        port_num = int(m.group(1))
        local_m = re.search(r"(\S+:\d+)", line)
        local_addr = local_m.group(1) if local_m else f"*:{port_num}"
        key = (port_num, local_addr)
        if key in seen:
            continue
        seen.add(key)
        pid_m = re.search(r"pid=(\d+)", line)
        pid = int(pid_m.group(1)) if pid_m else None
        ports.append(
            Port(
                port=port_num,
                local_addr=local_addr,
                status="LISTEN",
                pid=pid,
                process_name=None,
            )
        )
    return ports


def containers_from_docker_ps(output: str) -> list:
    """Parse ``docker ps -a`` tab-separated id, name, image, status."""
    from serverkit.docker.container import Container

    rows: list[Container] = []
    for line in output.strip().splitlines():
        if not line.strip():
            continue
        bits = line.split("\t")
        if len(bits) < 4:
            continue
        cid, name, image, status = bits[0], bits[1], bits[2], bits[3]
        rows.append(
            Container(id=cid[:12], name=name or "", image=image or "", status=status or "")
        )
    return rows
