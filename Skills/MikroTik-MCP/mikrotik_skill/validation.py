from __future__ import annotations


INTERFACE_ALLOWED = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789-_.:@"
)


def validate_interface_name(interface: str) -> str:
    """Validate a RouterOS interface name before embedding it in a CLI command."""

    interface = interface.strip()
    if not interface:
        raise ValueError("El nombre de interfaz está vacío.")

    if any(char not in INTERFACE_ALLOWED for char in interface):
        raise ValueError(
            f"Nombre de interfaz no permitido: {interface!r}"
        )

    return interface
