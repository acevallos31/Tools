from typing import Dict

from .client import MikroTikClient, CommandResult


INVENTORY_COMMANDS = {
    "identity": "/system identity print",
    "resources": "/system resource print",
    "routerboard": "/system routerboard print",
    "addresses": "/ip address print detail without-paging",
    "interfaces": "/interface print detail without-paging",
    "interface_stats": "/interface print stats without-paging",
    "routes": "/ip route print detail without-paging",
    "connection_tracking": "/ip firewall connection tracking print",
}


def result_to_dict(result: CommandResult) -> Dict:
    return {
        "command": result.command,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_status": result.exit_status,
        "ok": result.ok,
    }


def collect_inventory_sections(
    client: MikroTikClient,
    sections: list[str] | tuple[str, ...] | set[str],
) -> Dict:
    """Collect only explicitly requested inventory sections."""

    unknown = set(sections) - set(INVENTORY_COMMANDS)
    if unknown:
        raise ValueError(
            f"Secciones de inventario desconocidas: {sorted(unknown)}"
        )

    data = {}

    for name in sections:
        command = INVENTORY_COMMANDS[name]

        try:
            result = client.execute(command)

            data[name] = result_to_dict(result)

        except Exception as exc:

            data[name] = {
                "command": command,
                "stdout": "",
                "stderr": (
                    f"{type(exc).__name__}: {exc}"
                ),
                "exit_status": -1,
                "ok": False,
            }

    return data


def collect_inventory(
    client: MikroTikClient,
) -> Dict:
    return collect_inventory_sections(
        client,
        tuple(INVENTORY_COMMANDS),
    )
