from __future__ import annotations

import getpass
import time
from typing import Any, Dict, Optional

from .client import MikroTikClient
from .config import CONFIG
from .cpu_sampling import sample_cpu
from .inventory import collect_inventory
from .inventory_analyzer import analyze_inventory
from .inventory_parser import parse_inventory
from .profiles import load_profile
from .session_manager import SESSION_MANAGER
from .traffic import analyze_device_traffic


ALLOWED_OPERATIONS = {
    "inventory",
    "health",
    "interfaces",
    "network",
    "cpu_sample",
    "session_status",
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


def _inventory_view(
    inventory: Dict[str, Any],
    operation: str,
) -> Dict[str, Any]:
    """Construye vistas compactas para herramientas MCP especializadas."""

    data = inventory.get("data", {})
    analysis = inventory.get("analysis", {})
    summary = analysis.get("summary", {})
    findings = analysis.get("findings", [])

    if operation == "health":
        health_codes = {
            "cpu_load_warning",
            "cpu_load_critical",
            "routerboard_firmware_difference",
        }
        return {
            "device": data.get("device", {}),
            "health": data.get("health", {}),
            "findings": [
                item
                for item in findings
                if item.get("code") in health_codes
            ],
        }

    if operation == "interfaces":
        return {
            "interfaces": data.get("network", {}).get("interfaces", []),
            "summary": summary.get("interfaces", {}),
            "findings": [
                item
                for item in findings
                if str(item.get("code", "")).startswith("interface_")
            ],
        }

    if operation == "network":
        network = data.get("network", {})
        return {
            "addresses": network.get("addresses", []),
            "routes": network.get("routes", []),
            "connection_tracking": data.get("connection_tracking", {}),
            "findings": [
                item
                for item in findings
                if item.get("code") in {
                    "default_route_missing",
                    "connection_tracking_zero_entries",
                }
            ],
        }

    raise ValueError(f"Vista de inventario no soportada: {operation!r}")


def _session_status(device: str) -> Dict[str, Any]:
    """Devuelve telemetría segura sin abrir una conexión SSH nueva."""

    profile = load_profile(device)
    telemetry = SESSION_MANAGER.telemetry(device)

    return {
        "status": "ok",
        "operation": "session_status",
        "device": profile.name,
        "session": telemetry,
    }


def run_skill(
    operation: str,
    password: Optional[str] = None,
    interface: Optional[str] = None,
    duration: Optional[int] = None,
    interval: Optional[int] = None,
    device: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Punto de entrada principal del MikroTik Skill.

    Cuando se especifica device:

    - carga el perfil local del dispositivo;
    - utiliza SESSION_MANAGER;
    - reutiliza la sesión SSH cuando sea posible;
    - utiliza el secreto DPAPI administrado por SESSION_MANAGER;
    - no cierra la sesión al finalizar cada operación;
    - devuelve telemetría segura de ejecución y sesión.

    Cuando no se especifica device, conserva el flujo
    anterior mediante una conexión SSH temporal.

    El consumidor nunca proporciona comandos RouterOS
    arbitrarios.
    """

    operation = _validate_operation(
        operation
    )

    if operation == "session_status":
        if not device:
            raise ValueError(
                "session_status requiere un perfil de dispositivo."
            )
        return _session_status(device)

    started_at = time.perf_counter()

    profile = None
    managed_session = False
    session_reused = False
    session_reuse_count = 0
    session_age_seconds = 0.0

    if device:
        profile = load_profile(device)

        if interface is None:
            interface = profile.default_interface

        client = SESSION_MANAGER.get_client(
            device
        )

        managed_session = True
        target = profile.host

        session_info = SESSION_MANAGER.telemetry(
            device
        )

        session_reused = bool(
            session_info.get(
                "reused",
                False,
            )
        )

        session_reuse_count = int(
            session_info.get(
                "reuse_count",
                0,
            )
        )

        session_age_seconds = float(
            session_info.get(
                "age_seconds",
                0.0,
            )
        )

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

        if operation in {
            "inventory",
            "health",
            "interfaces",
            "network",
        }:
            inventory = _collect_and_analyze_inventory(
                client
            )

            if operation == "inventory":
                result["inventory"] = inventory
            else:
                result[operation] = _inventory_view(
                    inventory,
                    operation,
                )

        elif operation == "cpu_sample":
            result["cpu_sample"] = sample_cpu(
                client=client,
                duration=duration if duration is not None else 30,
                interval=interval if interval is not None else 1,
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

        elapsed_seconds = (
            time.perf_counter() - started_at
        )

        execution: Dict[str, Any] = {
            "elapsed_seconds": round(
                elapsed_seconds,
                3,
            ),
            "managed_session": managed_session,
        }

        if device:
            final_session_info = (
                SESSION_MANAGER.telemetry(
                    device
                )
            )

            execution.update(
                {
                    "session_reused": (
                        session_reused
                    ),
                    "session_reuse_count": (
                        session_reuse_count
                    ),
                    "session_age_seconds": round(
                        float(
                            final_session_info.get(
                                "age_seconds",
                                session_age_seconds,
                            )
                        ),
                        2,
                    ),
                    "session_connected": bool(
                        final_session_info.get(
                            "connected",
                            False,
                        )
                    ),
                }
            )

        result["execution"] = execution

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
