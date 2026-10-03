from __future__ import annotations

from typing import Any, Dict, List


# ============================================================
# Thresholds
# ============================================================

CPU_WARNING_PERCENT = 75
CPU_CRITICAL_PERCENT = 90

LINK_DOWNS_WARNING = 10
LINK_DOWNS_CRITICAL = 50


# ============================================================
# Findings helpers
# ============================================================

def _finding(
    code: str,
    severity: str,
    title: str,
    message: str,
    evidence: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Crea un hallazgo estructurado.

    severity:
        info
        warning
        critical
    """

    return {
        "code": code,
        "severity": severity,
        "title": title,
        "message": message,
        "evidence": evidence or {},
    }


# ============================================================
# CPU analysis
# ============================================================

def analyze_cpu(
    inventory: Dict[str, Any],
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []

    health = inventory.get("health", {})

    cpu_load = health.get(
        "cpu_load_percent"
    )

    if not isinstance(cpu_load, int):
        return findings

    if cpu_load >= CPU_CRITICAL_PERCENT:
        findings.append(
            _finding(
                code="cpu_load_critical",
                severity="critical",
                title="Carga de CPU crítica",
                message=(
                    f"La carga instantánea de CPU es "
                    f"{cpu_load}%."
                ),
                evidence={
                    "cpu_load_percent": cpu_load,
                    "threshold_percent": (
                        CPU_CRITICAL_PERCENT
                    ),
                },
            )
        )

    elif cpu_load >= CPU_WARNING_PERCENT:
        findings.append(
            _finding(
                code="cpu_load_warning",
                severity="warning",
                title="Carga de CPU elevada",
                message=(
                    f"La carga instantánea de CPU es "
                    f"{cpu_load}%."
                ),
                evidence={
                    "cpu_load_percent": cpu_load,
                    "threshold_percent": (
                        CPU_WARNING_PERCENT
                    ),
                },
            )
        )

    return findings


# ============================================================
# Firmware analysis
# ============================================================

def analyze_firmware(
    inventory: Dict[str, Any],
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []

    device = inventory.get(
        "device",
        {},
    )

    firmware = device.get(
        "firmware",
        {},
    )

    current = firmware.get(
        "current"
    )

    available = firmware.get(
        "available"
    )

    if (
        current
        and available
        and current != available
    ):
        findings.append(
            _finding(
                code="routerboard_firmware_difference",
                severity="info",
                title="Firmware RouterBOARD diferente",
                message=(
                    "El firmware RouterBOARD actual "
                    f"es {current} y RouterOS reporta "
                    f"{available} como upgrade-firmware."
                ),
                evidence={
                    "current_firmware": current,
                    "upgrade_firmware": available,
                },
            )
        )

    return findings


# ============================================================
# Interface analysis
# ============================================================

def analyze_interfaces(
    inventory: Dict[str, Any],
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []

    network = inventory.get(
        "network",
        {},
    )

    interfaces = network.get(
        "interfaces",
        [],
    )

    for interface in interfaces:
        name = interface.get(
            "name"
        )

        if not name:
            continue

        link_downs = interface.get(
            "link_downs",
            0,
        )

        running = interface.get(
            "running",
            False,
        )

        disabled = interface.get(
            "disabled",
            False,
        )

        comment = interface.get(
            "comment"
        )

        statistics = interface.get(
            "statistics",
            {},
        )

        rx_bytes = statistics.get(
            "rx_bytes",
            0,
        )

        tx_bytes = statistics.get(
            "tx_bytes",
            0,
        )

        rx_drops = statistics.get(
            "rx_drops",
            0,
        )

        tx_drops = statistics.get(
            "tx_drops",
            0,
        )

        # --------------------------------------------
        # Link-down history
        # --------------------------------------------

        if (
            isinstance(link_downs, int)
            and link_downs >= LINK_DOWNS_CRITICAL
        ):
            findings.append(
                _finding(
                    code="interface_link_downs_critical",
                    severity="critical",
                    title=(
                        "Historial elevado de "
                        "caídas de enlace"
                    ),
                    message=(
                        f"La interfaz {name} registra "
                        f"{link_downs} link-downs."
                    ),
                    evidence={
                        "interface": name,
                        "comment": comment,
                        "link_downs": link_downs,
                        "running": running,
                    },
                )
            )

        elif (
            isinstance(link_downs, int)
            and link_downs >= LINK_DOWNS_WARNING
        ):
            findings.append(
                _finding(
                    code="interface_link_downs_warning",
                    severity="warning",
                    title=(
                        "Historial de caídas "
                        "de enlace"
                    ),
                    message=(
                        f"La interfaz {name} registra "
                        f"{link_downs} link-downs."
                    ),
                    evidence={
                        "interface": name,
                        "comment": comment,
                        "link_downs": link_downs,
                        "running": running,
                    },
                )
            )

        # --------------------------------------------
        # Drops
        # --------------------------------------------

        if rx_drops or tx_drops:
            findings.append(
                _finding(
                    code="interface_packet_drops",
                    severity="warning",
                    title="Drops en interfaz",
                    message=(
                        f"La interfaz {name} presenta "
                        "contadores de drops."
                    ),
                    evidence={
                        "interface": name,
                        "comment": comment,
                        "rx_drops": rx_drops,
                        "tx_drops": tx_drops,
                    },
                )
            )

        # --------------------------------------------
        # Interface enabled but currently not running
        # --------------------------------------------
        #
        # Esto NO se considera automáticamente un error.
        # Un puerto sin cable puede estar perfectamente bien.
        #

        if (
            not running
            and not disabled
        ):
            findings.append(
                _finding(
                    code="interface_not_running",
                    severity="info",
                    title="Interfaz sin enlace activo",
                    message=(
                        f"La interfaz {name} está "
                        "habilitada pero actualmente "
                        "no está running."
                    ),
                    evidence={
                        "interface": name,
                        "comment": comment,
                        "rx_bytes": rx_bytes,
                        "tx_bytes": tx_bytes,
                    },
                )
            )

    return findings


# ============================================================
# Routing analysis
# ============================================================

def analyze_routes(
    inventory: Dict[str, Any],
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []

    network = inventory.get(
        "network",
        {},
    )

    routes = network.get(
        "routes",
        [],
    )

    default_routes = [
        route
        for route in routes
        if route.get("destination")
        == "0.0.0.0/0"
    ]

    if not default_routes:
        findings.append(
            _finding(
                code="default_route_missing",
                severity="warning",
                title="Ruta por defecto no encontrada",
                message=(
                    "No se encontró una ruta IPv4 "
                    "0.0.0.0/0 en el inventario."
                ),
            )
        )

    return findings


# ============================================================
# Connection tracking analysis
# ============================================================

def analyze_connection_tracking(
    inventory: Dict[str, Any],
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []

    tracking = inventory.get(
        "connection_tracking",
        {},
    )

    enabled = tracking.get(
        "enabled"
    )

    total_entries = tracking.get(
        "total_entries",
        0,
    )

    active_ipv4 = tracking.get(
        "active_ipv4"
    )

    active_ipv6 = tracking.get(
        "active_ipv6"
    )

    # Solo registramos el estado.
    # No asumimos que cero conexiones sea una falla.
    if total_entries == 0:
        findings.append(
            _finding(
                code="connection_tracking_zero_entries",
                severity="info",
                title=(
                    "Connection tracking sin entradas"
                ),
                message=(
                    "RouterOS reporta actualmente "
                    "cero entradas de connection tracking."
                ),
                evidence={
                    "enabled": enabled,
                    "active_ipv4": active_ipv4,
                    "active_ipv6": active_ipv6,
                    "total_entries": total_entries,
                },
            )
        )

    return findings


# ============================================================
# Summary
# ============================================================

def build_summary(
    inventory: Dict[str, Any],
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:

    network = inventory.get(
        "network",
        {},
    )

    interfaces = network.get(
        "interfaces",
        [],
    )

    running_interfaces = [
        interface
        for interface in interfaces
        if interface.get("running")
    ]

    inactive_interfaces = [
        interface
        for interface in interfaces
        if not interface.get("running")
    ]

    severity_counts = {
        "critical": 0,
        "warning": 0,
        "info": 0,
    }

    for finding in findings:
        severity = finding.get(
            "severity"
        )

        if severity in severity_counts:
            severity_counts[severity] += 1

    return {
        "device": inventory.get(
            "device",
            {},
        ),

        "cpu_load_percent": (
            inventory
            .get("health", {})
            .get("cpu_load_percent")
        ),

        "interfaces": {
            "total": len(
                interfaces
            ),

            "running": len(
                running_interfaces
            ),

            "not_running": len(
                inactive_interfaces
            ),
        },

        "findings": severity_counts,

        "total_findings": len(
            findings
        ),
    }


# ============================================================
# Complete inventory analysis
# ============================================================

def analyze_inventory(
    inventory: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Ejecuta todas las reglas determinísticas de análisis.

    Esta función NO modifica el MikroTik.
    """

    findings: List[Dict[str, Any]] = []

    findings.extend(
        analyze_cpu(
            inventory
        )
    )

    findings.extend(
        analyze_firmware(
            inventory
        )
    )

    findings.extend(
        analyze_interfaces(
            inventory
        )
    )

    findings.extend(
        analyze_routes(
            inventory
        )
    )

    findings.extend(
        analyze_connection_tracking(
            inventory
        )
    )

    severity_order = {
        "critical": 0,
        "warning": 1,
        "info": 2,
    }

    findings.sort(
        key=lambda item: (
            severity_order.get(
                item.get("severity"),
                99,
            ),
            item.get("code", ""),
        )
    )

    summary = build_summary(
        inventory,
        findings,
    )

    return {
        "status": "ok",
        "summary": summary,
        "findings": findings,
    }
