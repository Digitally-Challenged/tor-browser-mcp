"""macOS: the .app ships no profile template, so ephemeral sessions seed an empty profile."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from torbrowser_driver import DriverConfig, PathPolicy, browser_process


def test_ephemeral_profile_without_template_starts_empty(
    fake_macos_app: Path,
    policy: PathPolicy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    config = DriverConfig(tbb_root=fake_macos_app, path_policy=policy)
    session_dir = tmp_path / "session"
    session_dir.mkdir()

    browser_process._build_profile(config, session_dir)

    seed = session_dir / "profile"
    assert seed.is_dir()
    assert list(seed.iterdir()) == []
