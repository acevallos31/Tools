from __future__ import annotations

import atexit
import json
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent

from .session_manager import SESSION_MANAGER
from .skill import run_skill


StatusSection = Literal["health", "interfaces", "network", "session"]


server = MCPServer(
    name="mikrotik-skill",
    title="MikroTik Network Skill",
    description=(
        "Consulta segura y de solo lectura de dispositivos MikroTik RouterOS "
        "mediante perfiles locales preconfigurados."
    ),
    instructions=(
        "Para cualquier pregunta sobre el estado actual de un MikroTik usa "
        "mikrotik_status. CPU, memoria, almacenamiento, uptime y firmware "
        "corresponden a section=health; puertos, interfaces, enlaces y "
        "contadores a section=interfaces; IP, rutas, gateway y connection "
        "tracking a section=network; estado o reutilización SSH a "
        "section=session. Si el usuario pide analizar, observar, muestrear o graficar CPU durante varios segundos usa mikrotik_cpu_sample. Usa mikrotik_inventory únicamente cuando el usuario "
        "pida inventario completo, mikrotik_torch_flows para Torch y mikrotik_full "
        "solo cuando necesite inventario y tráfico juntos. Todas las "
        "herramientas son de solo lectura. Nunca afirmes que no existe acceso "
        "al dispositivo sin intentar primero mikrotik_status cuando la "
        "pregunta sea sobre su estado."
    ),
    version="0.7.2",
)


def _structured_result(result: dict[str, Any]) -> CallToolResult:
    """Resultado grande: structuredContent sin duplicar el payload como texto."""

    return CallToolResult(
        content=[],
        structuredContent=result,
        isError=result.get("status") == "error",
    )


def _compact_result(result: dict[str, Any]) -> CallToolResult:
    """Resultado compacto visible al modelo y disponible también como JSON."""

    text = json.dumps(
        result,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )

    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=text,
            )
        ],
        structuredContent=result,
        isError=result.get("status") == "error",
    )


@server.tool(
    structured_output=False,
)
def mikrotik_status(
    device: str,
    section: StatusSection = "health",
) -> CallToolResult:
    """Consulta el estado actual de un MikroTik. USA ESTA TOOL para CPU y salud.

    Args:
        device:
            Perfil local del dispositivo. Ejemplo: laboratorio.
        section:
            health = CPU, RAM, almacenamiento, uptime, RouterOS y firmware.
            interfaces = puertos, enlaces, contadores y link-downs.
            network = direcciones IP, rutas, gateway y connection tracking.
            session = conexión SSH, reutilización y edad de la sesión.

    Esta es la herramienta preferida SOLO para estado puntual.
    Para "¿cómo está el CPU?" usa section="health".
    NO usar si el usuario pide CPU durante X segundos/minutos, monitorear,
    muestrear, promedio, máximo, mínimo, tendencia o gráfico; en esos casos
    usa obligatoriamente mikrotik_cpu_sample.
    """

    operation = "session_status" if section == "session" else section

    return _compact_result(
        run_skill(
            operation=operation,
            device=device,
        )
    )


@server.tool(
    structured_output=False,
)
def mikrotik_cpu_sample(
    device: str,
    duration: int = 30,
    interval: int = 1,
) -> CallToolResult:
    """Muestrea CPU en el tiempo y devuelve datos listos para reporte o gráfico.

    Args:
        device:
            Perfil local del dispositivo. Ejemplo: laboratorio.
        duration:
            Ventana de muestreo en segundos, entre 5 y 120.
        interval:
            Separación entre muestras en segundos, mínimo 1.

    USA ESTA TOOL OBLIGATORIAMENTE cuando CPU aparezca junto a una duración
    (por ejemplo 30 segundos o 2 minutos), o cuando el usuario pida observar,
    monitorear, muestrear, promedio/mínimo/máximo, tendencia, serie temporal
    o gráfico. mikrotik_status solo da una lectura puntual y NO satisface
    solicitudes de CPU durante un período. Una sola llamada realiza todo el muestreo; no hagas múltiples
    llamadas a mikrotik_status para simular una serie temporal.

    El campo readings contiene elapsed_seconds y cpu_percent y puede
    representarse directamente como un gráfico de línea CPU (%) vs tiempo.
    """

    return _compact_result(
        run_skill(
            operation="cpu_sample",
            device=device,
            duration=duration,
            interval=interval,
        )
    )


@server.tool(
    structured_output=False,
)
def mikrotik_inventory(
    device: str,
) -> CallToolResult:
    """Obtiene el inventario completo. Úsala solo si se pide inventario completo."""

    return _structured_result(
        run_skill(
            operation="inventory",
            device=device,
        )
    )


@server.tool(
    structured_output=False,
)
def mikrotik_torch_flows(
    device: str,
    duration: int = 5,
) -> CallToolResult:
    """Inspecciona FLUJOS DE RED con RouterOS Torch.

    USA ESTA TOOL exclusivamente para preguntas sobre hosts/IP, protocolos,
    puertos, conversaciones o quién genera/recibe tráfico de red.

    NO usar para CPU, RAM, almacenamiento, uptime ni recursos del sistema.
    Si la pregunta menciona CPU durante un período usa mikrotik_cpu_sample,
    aunque también mencione segundos, análisis o gráfico.
    """

    return _structured_result(
        run_skill(
            operation="traffic",
            device=device,
            duration=duration,
        )
    )


@server.tool(
    structured_output=False,
)
def mikrotik_full(
    device: str,
    duration: int = 5,
) -> CallToolResult:
    """Ejecuta inventario completo y Torch. Úsala solo cuando se necesiten ambos."""

    return _structured_result(
        run_skill(
            operation="full",
            device=device,
            duration=duration,
        )
    )


def _shutdown() -> None:
    SESSION_MANAGER.close_all()


atexit.register(_shutdown)


def main() -> None:
    server.run(
        transport="stdio",
    )


if __name__ == "__main__":
    main()
