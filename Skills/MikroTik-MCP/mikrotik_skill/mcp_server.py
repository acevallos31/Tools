from __future__ import annotations

import atexit
import base64
import json
from typing import Annotated, Any, Literal, Optional

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, ImageContent, TextContent, ToolAnnotations
from pydantic import Field

from .charting import render_cpu_chart, render_interface_chart
from .observability import audited_call
from .profiles import list_profiles
from .session_manager import SESSION_MANAGER
from .skill import run_skill


StatusSection = Literal["health", "interfaces", "network", "session"]
DeviceName = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="Nombre de un perfil local preconfigurado, por ejemplo laboratorio.",
    ),
]
InterfaceName = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_.:@-]+$",
        description="Nombre de interfaz RouterOS, por ejemplo ether1 o bridge1.",
    ),
]
TimedDuration = Literal[0] | Annotated[
    int,
    Field(
        ge=5,
        le=120,
        description="0 = lectura puntual; 5-120 = ventana de muestreo en segundos.",
    ),
]
SampleInterval = Annotated[
    int,
    Field(
        ge=1,
        le=120,
        description="Segundos entre muestras temporales.",
    ),
]
TorchDuration = Annotated[
    int,
    Field(
        ge=1,
        le=30,
        description="Duración de la captura Torch en segundos.",
    ),
]


READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)


server = MCPServer(
    name="mikrotik-skill",
    title="MikroTik Network Diagnostics",
    description=(
        "Diagnóstico tipado y de solo lectura para MikroTik RouterOS mediante "
        "perfiles locales preconfigurados."
    ),
    instructions=(
        "Usa mikrotik_status para estado y series temporales de CPU o interfaces. "
        "Usa mikrotik_torch_flows solo para hosts, protocolos, puertos y flujos. "
        "Usa mikrotik_inventory solo cuando se necesite inventario completo. "
        "Los contadores acumulados no son ancho de banda actual y una lectura "
        "instantánea de CPU no demuestra carga sostenida."
    ),
    version="0.8.0-dev",
)


def _structured_result(result: dict[str, Any]) -> CallToolResult:
    """Large result: avoid duplicating the full payload into model text."""

    return CallToolResult(
        content=[],
        structuredContent=result,
        isError=result.get("status") == "error",
    )


def _compact_result(
    result: dict[str, Any],
    *,
    image_png: bytes | None = None,
) -> CallToolResult:
    """Compact result: text for the model, structured data for capable clients."""

    text = json.dumps(
        result,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )

    content: list[Any] = [
        TextContent(
            type="text",
            text=text,
        )
    ]

    if image_png is not None:
        content.append(
            ImageContent(
                type="image",
                data=base64.b64encode(image_png).decode("ascii"),
                mime_type="image/png",
            )
        )

    return CallToolResult(
        content=content,
        structuredContent=result,
        isError=result.get("status") == "error",
    )


def _filter_interface(result: dict[str, Any], interface: str) -> dict[str, Any]:
    payload = result.get("interfaces")
    if not isinstance(payload, dict):
        return result

    rows = payload.get("interfaces")
    if not isinstance(rows, list):
        return result

    filtered = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("name") == interface
    ]

    payload = dict(payload)
    payload["interfaces"] = filtered
    payload["requested_interface"] = interface
    payload["matched"] = len(filtered)
    result = dict(result)
    result["interfaces"] = payload
    return result


@server.tool(
    title="MikroTik Devices",
    description="List configured local MikroTik profiles without exposing credentials or management addresses.",
    annotations=READ_ONLY,
    structured_output=False,
)
def mikrotik_devices() -> CallToolResult:
    def execute() -> CallToolResult:
        devices = []
        for profile in list_profiles():
            session = SESSION_MANAGER.telemetry(profile.name)
            devices.append(
                {
                    "device": profile.name,
                    "default_interface": profile.default_interface,
                    "host_key_pinned": bool(profile.host_key_sha256),
                    "session_connected": bool(session.get("connected", False)),
                }
            )

        return _compact_result(
            {
                "status": "ok",
                "operation": "devices",
                "device_count": len(devices),
                "devices": devices,
            }
        )

    return audited_call(
        "mikrotik_devices",
        {},
        execute,
    )


@server.tool(
    title="MikroTik Status",
    description=(
        "Read current RouterOS health, interfaces, network or SSH-session state. "
        "For health/interfaces, duration>0 performs a real time-series sample."
    ),
    annotations=READ_ONLY,
    structured_output=False,
)
def mikrotik_status(
    device: DeviceName,
    section: StatusSection = "health",
    duration: TimedDuration = 0,
    interval: SampleInterval = 1,
    interface: Optional[InterfaceName] = None,
    chart: bool = False,
) -> CallToolResult:
    def execute() -> CallToolResult:
        if duration > 0 and section == "health":
            result = run_skill(
                operation="cpu_sample",
                device=device,
                duration=duration,
                interval=interval,
            )
            image = None
            if chart and result.get("status") == "ok":
                image = render_cpu_chart(result.get("cpu_sample", {}))
            return _compact_result(result, image_png=image)

        if duration > 0 and section == "interfaces":
            result = run_skill(
                operation="interface_sample",
                device=device,
                interface=interface,
                duration=duration,
                interval=interval,
            )
            image = None
            if chart and result.get("status") == "ok":
                image = render_interface_chart(
                    result.get("interface_sample", {})
                )
            return _compact_result(result, image_png=image)

        if duration > 0:
            raise ValueError(
                "duration solo aplica a section=health o section=interfaces."
            )

        if chart:
            raise ValueError(
                "chart requiere una medición temporal con duration > 0."
            )

        operation = "session_status" if section == "session" else section
        result = run_skill(
            operation=operation,
            device=device,
        )

        if section == "interfaces" and interface:
            result = _filter_interface(result, interface)

        return _compact_result(result)

    return audited_call(
        "mikrotik_status",
        {
            "device": device,
            "section": section,
            "duration": duration,
            "interval": interval,
            "interface": interface,
            "chart": chart,
        },
        execute,
    )


@server.tool(
    title="MikroTik Inventory",
    description=(
        "Read the complete normalized device inventory and deterministic findings. "
        "Use only when the full inventory is actually required."
    ),
    annotations=READ_ONLY,
    structured_output=False,
)
def mikrotik_inventory(
    device: DeviceName,
) -> CallToolResult:
    return audited_call(
        "mikrotik_inventory",
        {"device": device},
        lambda: _structured_result(
            run_skill(
                operation="inventory",
                device=device,
            )
        ),
    )


@server.tool(
    title="MikroTik Torch Flows",
    description=(
        "Inspect live network flows with RouterOS Torch: hosts, protocols, ports "
        "and observed rates. This is not a CPU or interface-bandwidth sampler."
    ),
    annotations=READ_ONLY,
    structured_output=False,
)
def mikrotik_torch_flows(
    device: DeviceName,
    interface: Optional[InterfaceName] = None,
    duration: TorchDuration = 5,
) -> CallToolResult:
    return audited_call(
        "mikrotik_torch_flows",
        {
            "device": device,
            "interface": interface,
            "duration": duration,
        },
        lambda: _structured_result(
            run_skill(
                operation="traffic",
                device=device,
                interface=interface,
                duration=duration,
            )
        ),
    )


@server.tool(
    title="MikroTik Full Diagnostic",
    description=(
        "Run complete inventory plus a bounded Torch capture. Expensive; use only "
        "when the user explicitly requests both inventory and live flow analysis."
    ),
    annotations=READ_ONLY,
    structured_output=False,
)
def mikrotik_full(
    device: DeviceName,
    interface: Optional[InterfaceName] = None,
    duration: TorchDuration = 5,
) -> CallToolResult:
    return audited_call(
        "mikrotik_full",
        {
            "device": device,
            "interface": interface,
            "duration": duration,
        },
        lambda: _structured_result(
            run_skill(
                operation="full",
                device=device,
                interface=interface,
                duration=duration,
            )
        ),
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
