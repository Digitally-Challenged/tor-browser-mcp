"""The bundled tor must not outlive the process that launched it."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from torbrowser_driver import DriverConfig, PathPolicy, tor_process


class _StopLaunch(Exception):
    pass


def test_tor_watches_the_launching_process(
    fake_tbb_layout: Path, policy: PathPolicy, tmp_path: Path
) -> None:
    config = DriverConfig(
        tbb_root=fake_tbb_layout, path_policy=policy, tor_data_dir=tmp_path / "tor-data"
    )
    captured: dict[str, Any] = {}

    def fake_launch(**kwargs: Any) -> None:
        captured.update(kwargs["config"])
        raise _StopLaunch

    with patch.object(tor_process, "preflight_ports"), patch(
        "stem.process.launch_tor_with_config", side_effect=fake_launch
    ), pytest.raises(_StopLaunch):
        tor_process.launch_tor(config)

    # tor polls this PID and exits once it is gone, even after SIGKILL of the server.
    assert captured["__OwningControllerProcess"] == str(os.getpid())
