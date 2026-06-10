"""Unit tests for Dev 2 shell parser and completer (no live SSH)."""

from __future__ import annotations

from unittest.mock import MagicMock

from serverkit.config import Config
from serverkit.processes.process import Process
from serverkit.processes.manager import ProcessCollection
from serverkit.shell.autocomplete import SDKCompleter
from serverkit.shell.chains import fluent_chain, try_extended_sdk_commands
from serverkit.shell.parser import (
    apply_step_command,
    extract_number,
    extract_string_arg,
    format_processes,
    parse_input,
)
from serverkit.workflows.builder import WorkflowBuilder


class _MiniState:
    """Minimal stand-in for ReplState in parser unit tests."""

    def __init__(self, active: object, server: object | None = None) -> None:
        self.active = active
        self.server = server if server is not None else active
        self.remote = None

    def close_remote(self) -> None:
        return None


def _fake_processes():
    return ProcessCollection(
        [
            Process(1, "python", 1200.0, 12.0),
            Process(2, "nginx", 80.0, 0.5),
        ]
    )


def test_extract_number():
    assert extract_number("processes.memory_above(500)") == 500.0
    assert extract_number("processes.memory_above(12.5)") == 12.5


def test_extract_string_arg_logs():
    assert extract_string_arg('logs("/tmp/a.log").errors()', "logs") == "/tmp/a.log"
    assert extract_string_arg("logs('b').warnings()", "logs") == "b"


def test_format_processes_empty():
    assert "No processes" in format_processes([])


def test_parse_help():
    active = MagicMock()
    out = parse_input("help", _MiniState(active))
    assert "processes.all()" in out


def test_parse_clr_clear_invokes_os_system(monkeypatch):
    calls: list[str] = []

    def fake_system(cmd: str) -> int:
        calls.append(cmd)
        return 0

    monkeypatch.setattr("serverkit.shell.parser.os.system", fake_system)
    active = MagicMock()
    assert parse_input("clr", _MiniState(active)) is None
    assert parse_input("  CLEAR  ", _MiniState(active)) is None
    assert calls == ["cls", "cls"] or calls == ["clear", "clear"]


def test_parse_unknown():
    active = MagicMock()
    out = parse_input("not_a_command", _MiniState(active))
    assert "Unknown command" in out


def test_parse_processes_all():
    active = MagicMock()
    active.processes.side_effect = _fake_processes
    out = parse_input("processes.all()", _MiniState(active))
    assert "python" in out
    assert "1200" in out


def test_parse_processes_memory_above():
    active = MagicMock()
    active.processes.side_effect = _fake_processes
    out = parse_input("processes.memory_above(500)", _MiniState(active))
    assert "python" in out
    assert "nginx" not in out


def test_apply_step_command_unknown():
    b = WorkflowBuilder("t")
    msg = apply_step_command(b, "nope")
    assert msg is not None and "Unknown" in msg


def test_apply_step_command_processes_summarize():
    b = WorkflowBuilder("t2")
    assert apply_step_command(b, "processes") is None
    assert apply_step_command(b, "memory_above 100") is None
    assert apply_step_command(b, "summarize") is None


def test_sdk_completer_yields_processes_prefix():
    comp = SDKCompleter()
    doc = MagicMock()
    doc.text_before_cursor = "proc"
    names = [c.text for c in comp.get_completions(doc, None)]
    assert any(n.startswith("processes") for n in names)


def test_sdk_completer_nested_logs():
    comp = SDKCompleter()
    doc = MagicMock()
    doc.text_before_cursor = "logs"
    names = [c.text for c in comp.get_completions(doc, None)]
    assert any("logs(" in n for n in names)


def test_parse_ask_invokes_analyzer(monkeypatch):
    from serverkit import Server
    from serverkit.shell.state import ReplState

    monkeypatch.setattr(
        "serverkit.ai.analyzer.Analyzer.ask",
        lambda self, q: f"stub:{q}",
    )
    state = ReplState(Server())
    out = parse_input("ask list hungry processes", state)
    assert out == "stub:list hungry processes"


def test_parse_disk_summarize_mock():
    col = MagicMock()
    col.summarize.return_value = "S"
    col.display.return_value = "D"
    active = MagicMock()
    active.disk.return_value = col
    out = parse_input("disk", _MiniState(active))
    assert "S" in out and "D" in out


def test_parse_ports_chain_mock():
    leaf = MagicMock()
    leaf.summarize.return_value = "listen"
    mid = MagicMock()
    mid.listening.return_value = leaf
    active = MagicMock()
    active.ports.return_value = mid
    out = parse_input("ports.listening().summarize()", _MiniState(active))
    assert out == "listen"
    mid.listening.assert_called_once()


def test_workflow_one_liner_requires_save_suffix():
    active = MagicMock()
    srv = MagicMock()
    st = _MiniState(active, server=srv)
    out = try_extended_sdk_commands('workflow("w").processes()', st)
    assert out is not None and "save" in out.lower()


def test_workflow_one_liner_local_only_when_remote():
    active = MagicMock()
    srv = MagicMock()
    st = _MiniState(active, server=srv)
    st.remote = object()
    out = try_extended_sdk_commands('workflow("w").save()', st)
    assert out is not None and "local" in out.lower()


def test_disk_unavailable_without_method():
    class Minimal:
        pass

    out = parse_input("disk", _MiniState(Minimal()))
    assert "not available" in (out or "").lower()


def test_fluent_chain_summarize_only():
    o = MagicMock()
    o.summarize.return_value = "X"
    o.display.return_value = "Y"
    assert fluent_chain(o, ".summarize()") == "X"


def test_parse_logs_contains_chain(tmp_path):
    from serverkit.shell.state import ReplState
    from serverkit import Server

    logf = tmp_path / "t.log"
    logf.write_text("line one\nERR timeout happened\nline three\n", encoding="utf-8")
    state = ReplState(Server())
    out = parse_input(f'logs("{logf}").contains("timeout").display()', state)
    assert "timeout" in (out or "")


def test_parse_processes_fluent_for_user_mock():
    col = MagicMock()
    col.summarize.return_value = "S"
    col.display.return_value = "D"
    user_col = MagicMock()
    user_col.for_user.return_value = col
    active = MagicMock()
    active.processes.return_value = user_col
    out = parse_input('processes().for_user("x").summarize()', _MiniState(active))
    assert out == "S"
    user_col.for_user.assert_called_once_with("x")


def test_connect_passes_password(monkeypatch):
    captured: dict = {}

    def fake_connect(
        cls,
        host,
        user=None,
        *,
        port=22,
        key_path=None,
        password=None,
        config=None,
        timeout=None,
        allow_agent=True,
        look_for_keys=True,
        **kwargs,
    ):
        captured["host"] = host
        captured["user"] = user
        captured["password"] = password
        captured["timeout"] = timeout
        captured["allow_agent"] = allow_agent
        captured["look_for_keys"] = look_for_keys
        m = MagicMock()
        m.user = user or "u"
        m.host = host
        return m

    monkeypatch.setattr(
        "serverkit.core.server.Server.connect",
        classmethod(fake_connect),
    )
    active = MagicMock()
    active._config = Config()
    srv = MagicMock()
    srv._config = Config()
    st = _MiniState(active, server=srv)
    parse_input(
        "connect myhost --user u1 --password secret --timeout 99 --no-agent --no-look-for-keys",
        st,
    )
    assert captured["host"] == "myhost"
    assert captured["user"] == "u1"
    assert captured["password"] == "secret"
    assert captured["timeout"] == 99
    assert captured["allow_agent"] is False
    assert captured["look_for_keys"] is False


def test_parse_logs_json_lines(tmp_path):
    from serverkit.shell.state import ReplState
    from serverkit import Server

    logf = tmp_path / "j.log"
    logf.write_text('{"a":1}\n{"b":2}\n', encoding="utf-8")
    state = ReplState(Server())
    out = parse_input(f'logs("{logf}").json_lines()', state)
    assert '"a"' in (out or "") and "1" in (out or "")


def test_parse_logs_error_rate(tmp_path):
    from serverkit.shell.state import ReplState
    from serverkit import Server

    logf = tmp_path / "e.log"
    logf.write_text("ERROR one\nINFO x\nERROR two\n", encoding="utf-8")
    state = ReplState(Server())
    out = parse_input(f'logs("{logf}").error_rate(5)', state)
    assert "errors=2" in (out or "")


def test_processes_group_by_name_summarize():
    active = MagicMock()
    active.processes.side_effect = _fake_processes
    out = parse_input("processes().group_by_name().summarize()", _MiniState(active))
    assert "python" in (out or "") or "nginx" in (out or "")


def test_memory_json_has_keys(monkeypatch):
    from serverkit.shell.state import ReplState
    from serverkit import Server

    monkeypatch.setattr(
        "serverkit.memory.snapshot.psutil.virtual_memory",
        lambda: MagicMock(
            total=8 * 1024**3,
            used=4 * 1024**3,
            available=4 * 1024**3,
            percent=50.0,
        ),
    )
    monkeypatch.setattr(
        "serverkit.memory.snapshot.psutil.swap_memory",
        lambda: MagicMock(total=1, used=0, percent=0.0),
    )
    state = ReplState(Server())
    out = parse_input("memory.json", state)
    assert "total_mb" in (out or "") and "used_mb" in (out or "")


def test_apply_step_command_export():
    b = WorkflowBuilder("ex")
    assert apply_step_command(b, "processes") is None
    assert apply_step_command(b, "export /tmp/out.txt") is None


def test_parse_import_calls_server():
    class S:
        _config = Config()

        def import_workflow(self, name: str) -> None:
            self.last = name

    srv = S()
    out = parse_input("import memory_audit", _MiniState(srv, server=srv))
    assert "Imported" in out
    assert srv.last == "memory_audit"
