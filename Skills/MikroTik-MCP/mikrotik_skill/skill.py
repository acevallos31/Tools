from __future__ import annotations

import getpass
from typing import Any, Dict, Optional

from .client import MikroTikClient
from .config import CONFIG
from .inventory import collect_inventory
from .inventory_analyzer import analyze_inventory
from .inventory_parser import parse_inventory
from .profiles import load_profile
from .session_manager import SESSION_MANAGER
from .traffic import analyze_device_traffic


ALLOWED_OPERATIONS = {
    "inventory",
    "traffic",
    "full",
}


def _validate_operation(operation: str) -> str:
    """
    Valida que Hermes/Qwen solamente pueda ejecutar
    operaciones explícitamente permitidas.
    """

    operation = operation.strip().lower()

    if operation not in ALLOWED_OPERATIONS:
        raise ValueError(
            f"Operación no permitida: {operation!r}. "
            f"Permitidas: {sorted(ALLOWED_OPERATIONS)}"
        )

    return operation


def _collect_and_analyze_inventory(
    client: MikroTikClient,
) -> Dict[str, Any]:
    """
    Captura, normaliza y analiza el inventario del MikroTik.
    """

    raw_inventory = collect_inventory(client)

    parsed_inventory = parse_inventory(
        raw_inventory
    )

    analysis = analyze_inventory(
        parsed_inventory
    )

    return {
        "data": parsed_inventory,
        "analysis": analysis,
    }


def run_skill(
    operation: str,
    password: Optional[str] = None,
    interface: Optional[str] = None,
    duration: Optional[int] = None,
    device: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Punto de entrada principal del MikroTik Skill.

    Cuando se especifica device:

    - carga el perfil local del dispositivo;
    - utiliza SESSION_MANAGER;
    - reutiliza la sesión SSH cuando sea posible;
    - utiliza el secreto DPAPI administrado por SESSION_MANAGER;
    - no cierra la sesión al finalizar cada operación.

    Cuando no se especifica device, conserva el flujo
    anterior mediante una conexión SSH temporal.

    El consumidor nunca proporciona comandos RouterOS
    arbitrarios.
    """

    operation = _validate_operation(
        operation
    )

    profile = None
    managed_session = False

    if device:
        profile = load_profile(device)

        if interface is None:
            interface = profile.default_interface

        client = SESSION_MANAGER.get_client(
            device
        )

        managed_session = True
        target = profile.host

    else:
        if not password:
            raise ValueError(
                "Se requiere contraseña SSH "
                "cuando no se utiliza un perfil."
            )

        client = MikroTikClient(
            password=password,
        )

        target = CONFIG.host

    result: Dict[str, Any] = {
        "status": "ok",
        "operation": operation,
        "target": target,
    }

    if profile is not None:
        result["device"] = profile.name

    try:
        # Los clientes administrados por SESSION_MANAGER
        # ya se entregan conectados.
        if not managed_session:
            client.connect()

        if operation == "inventory":
            result["inventory"] = (
                _collect_and_analyze_inventory(
                    client
                )
            )

        elif operation == "traffic":
            result["traffic"] = (
                analyze_device_traffic(
                    client=client,
                    interface=interface,
                    duration=duration,
                )
            )

        elif operation == "full":
            result["inventory"] = (
                _collect_and_analyze_inventory(
                    client
                )
            )

            result["traffic"] = (
                analyze_device_traffic(
                    client=client,
                    interface=interface,
                    duration=duration,
                )
            )

    except Exception as exc:
        result["status"] = "error"
        result["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }

    finally:
        # Las sesiones administradas deben permanecer
        # abiertas para poder reutilizarlas desde MCP/Hermes.
        if not managed_session:
            client.close()

    return result


def run_interactive(
    operation: str = "full",
    interface: Optional[str] = None,
    duration: Optional[int] = None,
    device: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Variante para ejecución manual desde PowerShell.

    Con device utiliza SESSION_MANAGER y el secreto DPAPI.

    Sin device conserva temporalmente el flujo
    interactivo anterior.
    """

    if device:
        return run_skill(
            operation=operation,
            interface=interface,
            duration=duration,
            device=device,
        )

    password = getpass.getpass(
        f"Contraseña SSH para "
        f"{CONFIG.username}@{CONFIG.host}: "
    )

    return run_skill(
        operation=operation,
        password=password,
        interface=interface,
        duration=duration,
    )
