"""Unit tests for Analyzer (stub Ollama, mock server)."""

from __future__ import annotations

from unittest.mock import MagicMock

from serverkit.config import Config
from serverkit.processes.process import Process
from serverkit.processes.manager import ProcessCollection
from serverkit.ai.analyzer import Analyzer
from serverkit.ai.jsonutil import parse_model_json


def test_parse_model_json_fenced():
    raw = """```json
{"resource": "processes", "filters": []}
```"""
    out = parse_model_json(raw)
    assert out == {"resource": "processes", "filters": []}


def test_parse_model_json_prefix_chatter():
    raw = 'Sure thing. {"resource": "processes", "filters": []}'
    out = parse_model_json(raw)
    assert out == {"resource": "processes", "filters": []}


class _StubOllama:
    def __init__(self, response: str) -> None:
        self._response = response
        self.prompts: list[str] = []

    def ask(self, prompt: str, **kwargs) -> str:
        self.prompts.append(prompt)
        return self._response


def _server_mock():
    srv = MagicMock()
    srv._config = Config()

    def _procs():
        return ProcessCollection(
            [
                Process(1, "python", 900.0, 1.0),
                Process(2, "nginx", 50.0, 0.1),
            ]
        )

    srv.processes.side_effect = _procs
    return srv


def test_analyzer_deterministic_cpu_skips_llm():
    srv = _server_mock()
    stub = _StubOllama("SHOULD_NOT_BE_USED")
    a = Analyzer(srv, ollama=stub)
    out = a.ask("list processes with cpu above 0.5 percent")
    assert "SHOULD_NOT" not in out
    assert stub.prompts == []
    assert "python" in out


def test_analyzer_intent_processes_json():
    json_line = '{"resource": "processes", "filters": [{"action": "memory_above", "value": 500}]}'
    stub = _StubOllama(json_line)
    a = Analyzer(_server_mock(), ollama=stub)
    out = a.ask("show heavy processes")
    assert "python" in out
    assert "nginx" not in out


def test_analyzer_diagnose_branch():
    stub = _StubOllama("Likely cause: many browser tabs.")
    a = Analyzer(_server_mock(), ollama=stub)
    out = a.ask("why is memory high? diagnose")
    assert "Likely cause" in out
    assert "python" in stub.prompts[0]


def test_analyzer_deterministic_disk_skips_llm():
    from serverkit.disk.manager import DiskCollection
    from serverkit.disk.partition import Partition

    srv = _server_mock()

    def _disk():
        return DiskCollection(
            [
                Partition(
                    device="/dev/sda1",
                    mountpoint="/",
                    fstype="ext4",
                    total_mb=1000,
                    used_mb=850,
                    percent=85.0,
                ),
                Partition(
                    device="/dev/sdb1",
                    mountpoint="/data",
                    fstype="ext4",
                    total_mb=2000,
                    used_mb=200,
                    percent=10.0,
                ),
            ]
        )

    srv.disk.side_effect = _disk
    stub = _StubOllama("SHOULD_NOT_BE_USED")
    a = Analyzer(srv, ollama=stub)
    out = a.ask("show disks above 50 percent")
    assert stub.prompts == []
    assert "/" in out
    assert "85" in out
    assert "/data" not in out


def test_analyzer_memory_intent_json():
    from serverkit.memory.snapshot import MemorySnapshot

    srv = _server_mock()
    srv.memory.return_value = MemorySnapshot(
        {
            "total_mb": 8000,
            "used_mb": 4000,
            "available_mb": 4000,
            "percent": 50.0,
            "swap_total_mb": 1000,
            "swap_used_mb": 0,
            "swap_percent": 0.0,
        }
    )
    stub = _StubOllama('{"resource": "memory"}')
    a = Analyzer(srv, ollama=stub)
    out = a.ask("memory footprint of this node for the report")
    assert "50" in out or "4000" in out


def test_analyzer_ports_listening_json():
    from serverkit.ports.manager import PortCollection
    from serverkit.ports.port import Port

    srv = _server_mock()

    def _ports():
        return PortCollection(
            [
                Port(port=22, local_addr="0.0.0.0:22", status="LISTEN", pid=1, process_name="sshd"),
                Port(port=443, local_addr="0.0.0.0:443", status="TIME_WAIT", pid=2, process_name=None),
            ]
        )

    srv.ports.side_effect = _ports
    stub = _StubOllama(
        '{"resource": "ports", "filters": [{"action": "listening"}], "terminal": "summarize"}'
    )
    a = Analyzer(srv, ollama=stub)
    out = a.ask("list ports for my audit")
    assert "22" in out
    assert "443" not in out


def test_analyzer_list_workflows_no_llm():
    srv = _server_mock()
    stub = _StubOllama("SHOULD_NOT_BE_USED")
    a = Analyzer(srv, ollama=stub)
    out = a.ask("list workflows")
    assert stub.prompts == []
    assert "No workflows saved." in out or len(out.strip()) >= 1


def test_analyzer_list_catalog_no_llm():
    srv = _server_mock()
    stub = _StubOllama("SHOULD_NOT_BE_USED")
    a = Analyzer(srv, ollama=stub)
    out = a.ask("list catalog")
    assert stub.prompts == []
    assert isinstance(out, str)
    assert len(out) > 0


def test_analyzer_workflows_intent_json():
    srv = _server_mock()
    stub = _StubOllama('{"resource": "workflows", "operation": "list_saved"}')
    a = Analyzer(srv, ollama=stub)
    out = a.ask("tell me about workflow inventory for my report")
    assert isinstance(out, str)


def test_analyzer_workflow_branch(monkeypatch, tmp_path):
    import serverkit.workflows.workflow as wf_mod

    wf_dir = tmp_path / "wf"
    wf_dir.mkdir()
    monkeypatch.setattr(wf_mod, "WORKFLOW_DIR", str(wf_dir) + "/")

    wf_json = """{
      "schema_version": 2,
      "name": "ai_mem_test",
      "created_at": null,
      "last_run": null,
      "steps": [
        { "type": "process_filter", "memory_above": 200, "cpu_above": null, "named": null },
        { "type": "sort", "field": "memory" },
        { "type": "summary" }
      ]
    }"""
    stub = _StubOllama(wf_json)
    a = Analyzer(_server_mock(), ollama=stub)
    out = a.ask("please make a workflow for high memory processes")
    assert "ai_mem_test" in out
    assert (wf_dir / "ai_mem_test.json").exists()


def test_server_ask_delegates(monkeypatch):
    from serverkit import Server

    monkeypatch.setattr(
        "serverkit.ai.analyzer.Analyzer.ask",
        lambda self, q: f"stub:{q}",
    )
    s = Server()
    assert s.ask("ping") == "stub:ping"
