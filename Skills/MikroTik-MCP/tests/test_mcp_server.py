from __future__ import annotations

from unittest.mock import patch

from mcp.types import TextContent

from mikrotik_skill.mcp_server import mikrotik_status, server


def _fake_result(operation: str) -> dict:
    return {
        "status": "ok",
        "operation": operation,
        "device": "laboratorio",
        operation: {"sample": True},
        "execution": {"elapsed_seconds": 0.01},
    }


def test_server_exposes_small_tool_surface() -> None:
    names = {tool.name for tool in server._tool_manager.list_tools()}
    assert names == {
        "mikrotik_status",
        "mikrotik_inventory",
        "mikrotik_torch_flows",
        "mikrotik_full",
    }


def test_status_defaults_to_health() -> None:
    with patch(
        "mikrotik_skill.mcp_server.run_skill",
        return_value=_fake_result("health"),
    ) as mocked:
        result = mikrotik_status("laboratorio")

    mocked.assert_called_once_with(
        operation="health",
        device="laboratorio",
    )
    assert result.is_error is False
    assert result.structured_content["operation"] == "health"
    assert len(result.content) == 1
    assert isinstance(result.content[0], TextContent)
    assert '"operation":"health"' in result.content[0].text


def test_status_routes_timed_cpu_to_sampler() -> None:
    with patch(
        "mikrotik_skill.mcp_server.run_skill",
        return_value=_fake_result("cpu_sample"),
    ) as mocked:
        result = mikrotik_status(
            "laboratorio",
            section="health",
            duration=30,
            interval=1,
        )

    mocked.assert_called_once_with(
        operation="cpu_sample",
        device="laboratorio",
        duration=30,
        interval=1,
    )
    assert result.structured_content["operation"] == "cpu_sample"


def test_status_routes_sections() -> None:
    cases = {
        "health": "health",
        "interfaces": "interfaces",
        "network": "network",
        "session": "session_status",
    }

    for section, operation in cases.items():
        with patch(
            "mikrotik_skill.mcp_server.run_skill",
            return_value=_fake_result(operation),
        ) as mocked:
            result = mikrotik_status(
                "laboratorio",
                section=section,
            )

        mocked.assert_called_once_with(
            operation=operation,
            device="laboratorio",
        )
        assert result.structured_content["operation"] == operation


def test_status_marks_backend_error_as_mcp_error() -> None:
    with patch(
        "mikrotik_skill.mcp_server.run_skill",
        return_value={
            "status": "error",
            "operation": "health",
            "error": {"type": "RuntimeError", "message": "test"},
        },
    ):
        result = mikrotik_status("laboratorio")

    assert result.is_error is True
