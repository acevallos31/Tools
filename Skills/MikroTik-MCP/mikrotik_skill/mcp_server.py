from __future__ import annotations

import atexit
from typing import Any

from mcp.server.mcpserver import MCPServer

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
    version="0.3.0",
)


@server.tool()
def mikrotik_inventory(
    device: str,
) -> dict[str, Any]:
    """
    Obtiene y analiza el inventario de un dispositivo MikroTik.

    Args:
        device:
            Nombre del perfil local preconfigurado.
            Ejemplo: laboratorio.

    Returns:
        Inventario estructurado y análisis determinístico.
    """

    return run_skill(
        operation="inventory",
        device=device,
    )


@server.tool()
def mikrotik_traffic(
    device: str,
    duration: int = 5,
) -> dict[str, Any]:
    """
    Captura y analiza tráfico mediante RouterOS Torch.

    Args:
        device:
            Nombre del perfil local preconfigurado.

        duration:
            Duración de la captura en segundos.
            El backend valida el rango permitido.

    Returns:
        Captura y análisis estructurado del tráfico observado.
    """

    return run_skill(
        operation="traffic",
        device=device,
        duration=duration,
    )


@server.tool()
def mikrotik_full(
    device: str,
    duration: int = 5,
) -> dict[str, Any]:
    """
    Ejecuta inventario y análisis de tráfico del dispositivo.

    Args:
        device:
            Nombre del perfil local preconfigurado.

        duration:
            Duración de la captura Torch en segundos.

    Returns:
        Inventario, análisis determinístico y análisis de tráfico.
    """

    return run_skill(
        operation="full",
        device=device,
        duration=duration,
    )


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
