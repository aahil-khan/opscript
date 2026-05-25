from unittest.mock import MagicMock, patch

from serverkit.services.handle import normalize_unit_name
from serverkit.services.manager import ServicesManager


def test_normalize_unit_name():
    assert normalize_unit_name("nginx") == "nginx.service"
    assert normalize_unit_name("nginx.service") == "nginx.service"


def test_service_restart():
    mock_ctl = MagicMock()
    mgr = ServicesManager(mock_ctl)
    handle = mgr.get("nginx")
    handle.restart()
    mock_ctl.restart.assert_called_once_with("nginx.service")


def test_server_services_entry():
    with patch("serverkit.systemctl.manager._run_systemctl") as run:
        run.return_value = "nginx.service loaded active running Nginx\n"
        from serverkit import Server

        coll = Server().services().active()
        assert len(coll.all()) == 1
