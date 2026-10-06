from __future__ import annotations

import atexit
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult

from .session_manager import SESSION_MANAGER
from .skill import run_skill


server = MCPServer(
    name="mikrotik-skill",
    title="MikroTik Network Skill",
    description=(
        "Herramientas seguras de consulta y análisis de dispositivos "
        "MikroTik RouterOS mediante perfiles locales preconfigurados."
    ),
    instructions=(
        "Utiliza estas herramientas únicamente para consultar y analizar "
        "dispositivos MikroTik configurados localmente. "
        "No permiten ejecutar comandos RouterOS arbitrarios ni modificar "
        "la configuración del dispositivo. "
        "La carga de CPU reportada es una medición instantánea y no debe "
        "interpretarse como carga sostenida sin mediciones adicionales. "
        "No atribuyas una carga de CPU elevada a un flujo de tráfico, "
        "puerto, host o posible incidente de seguridad sin evidencia "
        "adicional que demuestre esa relación."
    ),
    version="0.5.0",
)


def _structured_result(
    result: dict[str, Any],
) -> CallToolResult:
    """
    Devuelve el resultado exclusivamente mediante structuredContent.

    Hermes trata content y structuredContent como representaciones
    alternativas. Mantener content vacío evita duplicar el payload
    y permite que Hermes preserve la respuesta estructurada completa.
    """

    return CallToolResult(
        content=[],
        structuredContent=result,
        isError=False,
    )


@server.tool(
    structured_output=False,
)
def mikrotik_inventory(
    device: str,
) -> CallToolResult:
    """
    Obtiene y analiza el inventario de un dispositivo MikroTik.

    Args:
        device:
            Nombre del perfil local preconfigurado.
            Ejemplo: laboratorio.

    Returns:
        Inventario estructurado, análisis determinístico y
        telemetría de ejecución.
    """

    result = run_skill(
        operation="inventory",
        device=device,
    )

    return _structured_result(result)


@server.tool(
    structured_output=False,
)
def mikrotik_health(
    device: str,
) -> CallToolResult:
    """Obtiene estado compacto de CPU, memoria, almacenamiento y firmware."""

    return _structured_result(
        run_skill(operation="health", device=device)
    )


@server.tool(
    structured_output=False,
)
def mikrotik_interfaces(
    device: str,
) -> CallToolResult:
    """Obtiene interfaces, contadores y hallazgos relacionados con enlaces."""

    return _structured_result(
        run_skill(operation="interfaces", device=device)
    )


@server.tool(
    structured_output=False,
)
def mikrotik_network(
    device: str,
) -> CallToolResult:
    """Obtiene direcciones, rutas y estado de connection tracking."""

    return _structured_result(
        run_skill(operation="network", device=device)
    )


@server.tool(
    structured_output=False,
)
def mikrotik_session_status(
    device: str,
) -> CallToolResult:
    """Consulta telemetría de la sesión SSH sin abrir una conexión nueva."""

    return _structured_result(
        run_skill(operation="session_status", device=device)
    )


@server.tool(
    structured_output=False,
)
def mikrotik_traffic(
    device: str,
    duration: int = 5,
) -> CallToolResult:
    """
    Captura y analiza tráfico mediante RouterOS Torch.

    Args:
        device:
            Nombre del perfil local preconfigurado.

        duration:
            Duración de la captura en segundos.
            El backend valida el rango permitido.

    Returns:
        Captura, análisis estructurado y telemetría de ejecución.
    """

    result = run_skill(
        operation="traffic",
        device=device,
        duration=duration,
    )

    return _structured_result(result)


@server.tool(
    structured_output=False,
)
def mikrotik_full(
    device: str,
    duration: int = 5,
) -> CallToolResult:
    """
    Ejecuta inventario y análisis de tráfico del dispositivo.

    Args:
        device:
            Nombre del perfil local preconfigurado.

        duration:
            Duración de la captura Torch en segundos.

    Returns:
        Inventario, análisis determinístico, análisis de tráfico
        y telemetría de ejecución.
    """

    result = run_skill(
        operation="full",
        device=device,
        duration=duration,
    )

    return _structured_result(result)


def _shutdown() -> None:
    """
    Cierra las sesiones SSH persistentes y elimina de memoria
    las credenciales cacheadas cuando termina el servidor MCP.
    """

    SESSION_MANAGER.close_all()


atexit.register(_shutdown)


def main() -> None:
    server.run(
        transport="stdio",
    )


if __name__ == "__main__":
    main()
