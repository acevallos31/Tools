from __future__ import annotations

from unittest.mock import patch

from mcp.types import ImageContent, TextContent

from mikrotik_skill.mcp_server import mikrotik_devices, mikrotik_status, server


def _fake_result(operation: str) -> dict:
    payload = {
        "status": "ok",
        "operation": operation,
        "device": "laboratorio",
        "execution": {"elapsed_seconds": 0.01},
    }
    if operation == "cpu_sample":
        payload["cpu_sample"] = {
            "sample_count": 2,
            "readings": [
                {"elapsed_seconds": 0, "cpu_percent": 10},
                {"elapsed_seconds": 1, "cpu_percent": 20},
            ],
        }
    elif operation == "interface_sample":
        payload["interface_sample"] = {
            "interface": "ether1",
            "sample_count": 2,
            "readings": [
                {"elapsed_seconds": 0, "rx_bps": 1000, "tx_bps": 500},
                {"elapsed_seconds": 1, "rx_bps": 2000, "tx_bps": 700},
            ],
        }
    else:
        payload[operation] = {"sample": True}
    return payload


def test_server_exposes_small_tool_surface() -> None:
    tools = server._tool_manager.list_tools()
    names = {tool.name for tool in tools}

    assert names == {
        "mikrotik_devices",
        "mikrotik_status",
        "mikrotik_inventory",
        "mikrotik_torch_flows",
        "mikrotik_full",
    }

    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False
        assert tool.annotations.open_world_hint is False



def test_devices_does_not_expose_host_or_username() -> None:
    class Profile:
        name = "laboratorio"
        default_interface = "ether1"
        host_key_sha256 = "SHA256:test"

    with patch(
        "mikrotik_skill.mcp_server.list_profiles",
        return_value=[Profile()],
    ), patch(
        "mikrotik_skill.mcp_server.SESSION_MANAGER.telemetry",
        return_value={"connected": True},
    ):
        result = mikrotik_devices()

    payload = result.structured_content
    assert payload["device_count"] == 1
    assert payload["devices"][0]["device"] == "laboratorio"
    assert payload["devices"][0]["host_key_pinned"] is True
    assert "host" not in payload["devices"][0]
    assert "username" not in payload["devices"][0]

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


def test_status_routes_timed_interface_to_sampler() -> None:
    with patch(
        "mikrotik_skill.mcp_server.run_skill",
        return_value=_fake_result("interface_sample"),
    ) as mocked:
        result = mikrotik_status(
            "laboratorio",
            section="interfaces",
            interface="ether1",
            duration=30,
            interval=1,
        )

    mocked.assert_called_once_with(
        operation="interface_sample",
        device="laboratorio",
        interface="ether1",
        duration=30,
        interval=1,
    )
    assert result.structured_content["operation"] == "interface_sample"


def test_status_can_return_chart_image() -> None:
    with patch(
        "mikrotik_skill.mcp_server.run_skill",
        return_value=_fake_result("cpu_sample"),
    ), patch(
        "mikrotik_skill.mcp_server.render_cpu_chart",
        return_value=b"\x89PNG\r\n\x1a\nTEST",
    ):
        result = mikrotik_status(
            "laboratorio",
            section="health",
            duration=30,
            interval=1,
            chart=True,
        )

    assert len(result.content) == 2
    assert isinstance(result.content[0], TextContent)
    assert isinstance(result.content[1], ImageContent)
    assert result.content[1].mime_type == "image/png"


def test_status_rejects_timed_network_request() -> None:
    try:
        mikrotik_status(
            "laboratorio",
            section="network",
            duration=30,
        )
    except ValueError as exc:
        assert "section=health" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_status_marks_backend_error_as_mcp_error() -> None:
    with patch(
        "mikrotik_skill.mcp_server.run_skill",
        return_value={
            "status": "error",
            "operation": "health",
            "error": {"code": "EXECUTION_FAILED", "message": "test"},
        },
    ):
        result = mikrotik_status("laboratorio")

    assert result.is_error is True
