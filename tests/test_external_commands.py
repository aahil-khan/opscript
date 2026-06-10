"""External CLI availability (systemctl, who)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from serverkit.exceptions import ExternalCommandNotFound
from serverkit.systemctl.service import _run_systemctl


def test_run_systemctl_file_not_found_message():
    with patch("serverkit.systemctl.service.subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(ExternalCommandNotFound) as excinfo:
            _run_systemctl("status", "foo")
    assert "systemctl" in str(excinfo.value).lower()
    assert "linux" in str(excinfo.value).lower()
