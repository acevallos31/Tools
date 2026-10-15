from __future__ import annotations

from mikrotik_skill.client import CommandResult
from mikrotik_skill.inventory import collect_inventory_sections


class FakeClient:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def execute(self, command: str) -> CommandResult:
        self.commands.append(command)
        return CommandResult(
            command=command,
            stdout="ok",
            stderr="",
            exit_status=0,
        )


def test_targeted_health_collection_avoids_full_inventory() -> None:
    client = FakeClient()

    data = collect_inventory_sections(
        client,
        ("identity", "resources", "routerboard"),
    )

    assert set(data) == {"identity", "resources", "routerboard"}
    assert len(client.commands) == 3
    assert "/interface print detail without-paging" not in client.commands
    assert "/ip route print detail without-paging" not in client.commands
