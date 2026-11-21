from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from types import FrameType
from typing import Protocol


class ChildProcess(Protocol):
    def poll(self) -> int | None: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...


class ProcessFactory(Protocol):
    def __call__(self, command: list[str], *, env: Mapping[str, str]) -> ChildProcess: ...


def transport_environment(base: Mapping[str, str], mode: str) -> dict[str, str]:
    environment = dict(base)
    environment["MODE"] = mode
    if mode.startswith("mcp_"):
        # Only the API child owns the shared local probe port.
        environment["REKIPE_DISABLE_PROBES"] = "true"
    else:
        environment.pop("REKIPE_DISABLE_PROBES", None)
    return environment


def run_isolated_transports(
    entrypoint: Path,
    *,
    process_factory: ProcessFactory | None = None,
    poll_interval: float = 0.2,
    termination_timeout: float = 10.0,
) -> int:
    """Run REST and MCP in separate processes and supervise their lifecycle."""
    command = [sys.executable, str(entrypoint)]
    factory = process_factory or _start_process
    children: list[ChildProcess] = []
    termination_requested: set[int] = set()
    received_signal: int | None = None

    def stop_children(signum: int | None = None, _frame: FrameType | None = None) -> None:
        nonlocal received_signal
        if signum is not None:
            received_signal = signum
        for child in children:
            child_id = id(child)
            if child.poll() is None and child_id not in termination_requested:
                termination_requested.add(child_id)
                child.terminate()

    previous_handlers = {
        signum: signal.getsignal(signum)
        for signum in (signal.SIGINT, signal.SIGTERM)
    }
    for signum in previous_handlers:
        signal.signal(signum, stop_children)

    try:
        for mode in ("api", "mcp_http"):
            children.append(
                factory(
                    command,
                    env=transport_environment(os.environ, mode),
                )
            )

        while received_signal is None:
            for child in children:
                exit_code = child.poll()
                if exit_code is not None:
                    stop_children()
                    return exit_code
            time.sleep(poll_interval)
        return 128 + received_signal
    finally:
        stop_children()
        for child in children:
            try:
                child.wait(timeout=termination_timeout)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


def _start_process(command: list[str], *, env: Mapping[str, str]) -> ChildProcess:
    return subprocess.Popen(command, env=env)
