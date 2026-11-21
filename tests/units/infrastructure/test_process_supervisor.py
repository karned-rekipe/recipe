from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from infrastructure.process_supervisor import run_isolated_transports, transport_environment


def test_transport_environment_isolates_modes_and_probe_owner():
    base = {"SHARED": "value", "REKIPE_DISABLE_PROBES": "stale"}

    api = transport_environment(base, "api")
    mcp = transport_environment(base, "mcp_http")

    assert api == {"SHARED": "value", "MODE": "api"}
    assert mcp == {
        "SHARED": "value",
        "MODE": "mcp_http",
        "REKIPE_DISABLE_PROBES": "true",
    }
    assert base["REKIPE_DISABLE_PROBES"] == "stale"


def test_supervisor_stops_sibling_when_a_transport_exits():
    api = MagicMock()
    api.poll.return_value = 7
    api.wait.return_value = 7
    mcp = MagicMock()
    mcp.poll.return_value = None
    mcp.wait.return_value = -15
    created = iter([api, mcp])
    calls: list[tuple[list[str], dict[str, str]]] = []

    def factory(command: list[str], *, env: dict[str, str]):
        calls.append((command, env))
        return next(created)

    exit_code = run_isolated_transports(
        Path("/workspace/main.py"),
        process_factory=factory,
        poll_interval=0,
    )

    assert exit_code == 7
    assert [call[1]["MODE"] for call in calls] == ["api", "mcp_http"]
    mcp.terminate.assert_called_once()
    api.wait.assert_called_once()
    mcp.wait.assert_called_once()
