from __future__ import annotations

from mikrotik_skill.client import CommandResult
from mikrotik_skill.traffic import capture_torch


class FakeClient:
    host = "192.0.2.55"

    def execute(
        self,
        command: str,
        timeout: int | None = None,
    ) -> CommandResult:
        return CommandResult(
            command=command,
            stdout=(
                "SRC-ADDRESS        DST-ADDRESS        PROTOCOL TX RX\n"
                "192.0.2.10         198.51.100.10      tcp      1k 2k\n"
            ),
            stderr="",
            exit_status=0,
        )


def test_torch_uses_logical_target_not_management_host() -> None:
    capture = capture_torch(
        client=FakeClient(),  # type: ignore[arg-type]
        interface="ether1",
        duration=1,
        target="laboratorio",
    )

    payload = capture.to_dict()
    assert payload["target"] == "laboratorio"
    assert FakeClient.host not in str(payload)


def test_torch_direct_mode_still_hides_management_host() -> None:
    capture = capture_torch(
        client=FakeClient(),  # type: ignore[arg-type]
        interface="ether1",
        duration=1,
    )

    payload = capture.to_dict()
    assert payload["target"] == "direct"
    assert FakeClient.host not in str(payload)
