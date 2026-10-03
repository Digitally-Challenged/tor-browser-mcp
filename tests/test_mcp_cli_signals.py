"""A signal from the MCP client must shut the driver down, not orphan tor and firefox.

MCP clients stop stdio servers with SIGTERM. Python's default SIGTERM action
exits without unwinding, so the driver's context manager never runs and tor,
geckodriver and firefox outlive the server. Cancelling the server task is not
enough either: the MCP stdio transport reads stdin on a worker thread that
cannot be cancelled, so the task only unwinds once the client closes stdin.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from contextlib import suppress
from typing import Any

import pytest

from torbrowser_mcp import cli

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")


class _FakeDriver:
    def __init__(self) -> None:
        self.closed = 0

    def close(self) -> None:
        self.closed += 1


class _FakeServer:
    """Stands in for run_server: hands over its driver, then serves until cancelled."""

    def __init__(self) -> None:
        self.driver = _FakeDriver()
        self.ready = False

    async def run_server(self, config: Any, options: Any, *, on_driver: Any = None) -> None:
        if on_driver is not None:
            on_driver(self.driver)
        self.ready = True
        await asyncio.Event().wait()


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGHUP, signal.SIGINT])
def test_shutdown_signal_closes_driver_and_exits(
    sig: signal.Signals, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _FakeServer()
    monkeypatch.setattr(cli, "run_server", fake.run_server)
    exits: list[int] = []
    # If _serve does not handle the signal, fail the test instead of killing pytest.
    unhandled: list[int] = []
    previous = signal.signal(sig, lambda signum, frame: unhandled.append(signum))
    try:

        async def scenario() -> None:
            exited = asyncio.Event()

            def exit_process(code: int) -> None:
                exits.append(code)
                exited.set()

            server = asyncio.ensure_future(
                cli._serve(None, None, exit_process=exit_process)  # type: ignore[arg-type]
            )
            while not fake.ready:
                await asyncio.sleep(0.01)
            os.kill(os.getpid(), sig)
            await asyncio.wait_for(exited.wait(), timeout=5)
            server.cancel()
            with suppress(asyncio.CancelledError):
                await server

        asyncio.run(scenario())
    finally:
        signal.signal(sig, previous)

    assert unhandled == []
    assert fake.driver.closed == 1
    assert exits == [0]
