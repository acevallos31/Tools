from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import paramiko

from mikrotik_skill.skill import run_skill


def test_profile_connection_failure_is_structured() -> None:
    profile = SimpleNamespace(
        name="laboratorio",
        host="192.0.2.1",
        port=22,
        username="readonly",
        default_interface="ether1",
        host_key_sha256=None,
    )

    with patch(
        "mikrotik_skill.skill.load_profile",
        return_value=profile,
    ), patch(
        "mikrotik_skill.skill.SESSION_MANAGER.get_client",
        side_effect=paramiko.AuthenticationException("bad auth"),
    ), patch(
        "mikrotik_skill.skill.SESSION_MANAGER.telemetry",
        return_value={
            "connected": False,
            "reused": False,
            "reuse_count": 0,
            "age_seconds": 0.0,
        },
    ):
        result = run_skill(
            operation="health",
            device="laboratorio",
        )

    assert result["status"] == "error"
    assert result["error"]["code"] == "SSH_AUTH_FAILED"
    assert result["execution"]["session_connected"] is False
    assert "bad auth" in result["error"]["message"]


def test_missing_profile_is_structured() -> None:
    with patch(
        "mikrotik_skill.skill.load_profile",
        side_effect=FileNotFoundError("missing profile"),
    ), patch(
        "mikrotik_skill.skill.SESSION_MANAGER.telemetry",
        return_value={
            "connected": False,
            "reused": False,
            "reuse_count": 0,
            "age_seconds": 0.0,
        },
    ):
        result = run_skill(
            operation="health",
            device="missing",
        )

    assert result["status"] == "error"
    assert result["error"]["code"] == "LOCAL_RESOURCE_NOT_FOUND"
