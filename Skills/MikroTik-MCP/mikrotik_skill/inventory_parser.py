import re
from typing import Any, Dict, List


# ============================================================
# Helpers
# ============================================================

def _clean_value(value: str) -> str:
    """Limpia espacios y comillas de valores obtenidos de RouterOS."""
    return value.strip().strip('"')


def _parse_key_value_output(text: str) -> Dict[str, str]:
    """
    Convierte salidas RouterOS del tipo:

        uptime: 3d9h53m23s
        version: 7.24.4 (stable)
        cpu-load: 83%

    en un diccionario.
    """

    result: Dict[str, str] = {}

    for line in text.splitlines():
        line = line.strip()

        if not line or ":" not in line:
            continue

        key, value = line.split(":", 1)

        key = key.strip().replace("-", "_")
        value = _clean_value(value)

        if key:
            result[key] = value

    return result


def _parse_int(value: Any, default: int = 0) -> int:
    """Extrae el primer entero de un valor."""

    if value is None:
        return default

    match = re.search(r"-?\d+", str(value))

    if not match:
        return default

    try:
        return int(match.group())
    except ValueError:
        return default


def _parse_routeros_number(value: str) -> int:
    """
    Convierte números RouterOS con separadores de miles por espacios.

    Ejemplos:

        22 002 657 886 -> 22002657886
        2 811 253 609  -> 2811253609
        0              -> 0
    """

    if not value:
        return 0

    digits = re.sub(r"[^\d]", "", value)

    if not digits:
        return 0

    try:
        return int(digits)
    except ValueError:
        return 0


# ============================================================
# Identity
# ============================================================

def parse_identity(stdout: str) -> Dict[str, Any]:
    """
    Parser tolerante para:

        /system identity print

    Algunas sesiones SSH de RouterOS pueden devolver el nombre
    fragmentado verticalmente.

    Ejemplo:

        name: M
              i
              k
              r
              o
              T
              i
              k

    Reconstruimos el nombre completo.
    """

    if not stdout:
        return {"name": None}

    lines = [
        line.strip()
        for line in stdout.splitlines()
        if line.strip()
    ]

    if not lines:
        return {"name": None}

    characters: List[str] = []
    found_name = False

    for line in lines:
        if line.startswith("name:"):
            found_name = True

            value = line.split(":", 1)[1].strip()

            if value:
                characters.append(value)

            continue

        if found_name:
            characters.append(line)

    if characters:
        return {
            "name": "".join(characters)
        }

    parsed = _parse_key_value_output(stdout)

    return {
        "name": parsed.get("name")
    }


# ============================================================
# Resources
# ============================================================

def parse_resources(stdout: str) -> Dict[str, Any]:
    """Parser para /system resource print."""

    data = _parse_key_value_output(stdout)

    return {
        "uptime": data.get("uptime"),
        "version": data.get("version"),
        "build_time": data.get("build_time"),
        "free_memory": data.get("free_memory"),
        "total_memory": data.get("total_memory"),
        "cpu": data.get("cpu"),
        "cpu_count": _parse_int(
            data.get("cpu_count")
        ),
        "cpu_frequency": data.get(
            "cpu_frequency"
        ),
        "cpu_load_percent": _parse_int(
            data.get("cpu_load")
        ),
        "free_hdd_space": data.get(
            "free_hdd_space"
        ),
        "total_hdd_space": data.get(
            "total_hdd_space"
        ),
        "architecture": data.get(
            "architecture_name"
        ),
        "board_name": data.get(
            "board_name"
        ),
        "platform": data.get(
            "platform"
        ),
    }


# ============================================================
# RouterBOARD
# ============================================================

def parse_routerboard(stdout: str) -> Dict[str, Any]:
    """Parser para /system routerboard print."""

    data = _parse_key_value_output(stdout)

    return {
        "routerboard": data.get(
            "routerboard"
        ),
        "model": data.get(
            "model"
        ),
        "revision": data.get(
            "revision"
        ),
        "serial_number": data.get(
            "serial_number"
        ),
        "firmware_type": data.get(
            "firmware_type"
        ),
        "minimum_firmware": data.get(
            "minimum_firmware"
        ),
        "current_firmware": data.get(
            "current_firmware"
        ),
        "upgrade_firmware": data.get(
            "upgrade_firmware"
        ),
    }


# ============================================================
# IP addresses
# ============================================================

def parse_addresses(stdout: str) -> List[Dict[str, Any]]:
    """
    Parser para:

        /ip address print detail without-paging
    """

    addresses: List[Dict[str, Any]] = []

    pattern = re.compile(
        r"(?:^|\n)"
        r"\s*(\d+)\s*"
        r"([A-Za-z]*)\s*"
        r"address=([^\s]+)"
        r".*?"
        r"network=([^\s]+)"
        r".*?"
        r"interface=([^\s]+)",
        re.MULTILINE | re.DOTALL,
    )

    for match in pattern.finditer(stdout):
        (
            index,
            flags,
            address,
            network,
            interface,
        ) = match.groups()

        addresses.append(
            {
                "index": int(index),
                "flags": flags,
                "dynamic": "D" in flags,
                "address": address,
                "network": network,
                "interface": interface,
            }
        )

    return addresses


# ============================================================
# Routes
# ============================================================

def parse_routes(stdout: str) -> List[Dict[str, Any]]:
    """
    Parser para:

        /ip route print detail without-paging

    Soporta flags como:

        DAd
        DAc
        As
    """

    routes: List[Dict[str, Any]] = []

    if not stdout:
        return routes

    lines = stdout.splitlines()

    current_block: List[str] = []

    def process_block(
        block_lines: List[str],
    ) -> None:

        if not block_lines:
            return

        block = "\n".join(block_lines)

        if "dst-address=" not in block:
            return

        first_line = block_lines[0].strip()

        flags_match = re.match(
            r"([A-Za-z]+)\s+dst-address=",
            first_line,
        )

        dst_match = re.search(
            r"dst-address=([^\s]+)",
            block,
        )

        gateway_match = re.search(
            r"gateway=([^\s]+)",
            block,
        )

        immediate_gateway_match = re.search(
            r"immediate-gw=([^\s]+)",
            block,
        )

        distance_match = re.search(
            r"distance=(\d+)",
            block,
        )

        table_match = re.search(
            r"routing-table=([^\s]+)",
            block,
        )

        local_address_match = re.search(
            r"local-address=([^\s]+)",
            block,
        )

        routes.append(
            {
                "flags": (
                    flags_match.group(1)
                    if flags_match
                    else None
                ),

                "destination": (
                    dst_match.group(1)
                    if dst_match
                    else None
                ),

                "gateway": (
                    gateway_match.group(1)
                    if gateway_match
                    else None
                ),

                "immediate_gateway": (
                    immediate_gateway_match.group(1)
                    if immediate_gateway_match
                    else None
                ),

                "routing_table": (
                    table_match.group(1)
                    if table_match
                    else None
                ),

                "distance": (
                    int(distance_match.group(1))
                    if distance_match
                    else None
                ),

                "local_address": (
                    local_address_match.group(1)
                    if local_address_match
                    else None
                ),
            }
        )

    for line in lines:
        stripped = line.strip()

        if re.match(
            r"^[A-Za-z]+\s+dst-address=",
            stripped,
        ):
            process_block(
                current_block
            )

            current_block = [
                stripped
            ]

        elif current_block:
            if stripped:
                current_block.append(
                    stripped
                )

    process_block(
        current_block
    )

    return routes


# ============================================================
# Connection tracking
# ============================================================

def parse_connection_tracking(
    stdout: str,
) -> Dict[str, Any]:
    """
    Parser para:

        /ip firewall connection tracking print
    """

    data = _parse_key_value_output(
        stdout
    )

    return {
        "enabled": data.get(
            "enabled"
        ),

        "active_ipv4": data.get(
            "active_ipv4"
        ),

        "active_ipv6": data.get(
            "active_ipv6"
        ),

        "max_entries": _parse_int(
            data.get("max_entries")
        ),

        "total_entries": _parse_int(
            data.get("total_entries")
        ),

        "total_ipv4_entries": _parse_int(
            data.get("total_ip4_entries")
        ),

        "total_ipv6_entries": _parse_int(
            data.get("total_ip6_entries")
        ),
    }


# ============================================================
# Interfaces
# ============================================================

def _update_interface_from_text(
    interface: Dict[str, Any],
    text: str,
) -> None:
    """
    Extrae propiedades de una línea perteneciente
    al bloque de una interfaz.
    """

    patterns = {
        "name": (
            r'name="([^"]+)"'
        ),

        "default_name": (
            r'default-name="([^"]+)"'
        ),

        "type": (
            r'type="([^"]+)"'
        ),

        "mtu": (
            r"\bmtu=([^\s]+)"
        ),

        "actual_mtu": (
            r"\bactual-mtu=([^\s]+)"
        ),

        "l2mtu": (
            r"\bl2mtu=([^\s]+)"
        ),

        "max_l2mtu": (
            r"\bmax-l2mtu=([^\s]+)"
        ),

        "vrf": (
            r"\bvrf=([^\s]+)"
        ),

        "mac_address": (
            r"\bmac-address="
            r"([0-9A-Fa-f:]{17})"
        ),

        "last_link_up_time": (
            r"last-link-up-time="
            r"(\d{4}-\d{2}-\d{2}"
            r"\s+\d{2}:\d{2}:\d{2})"
        ),

        "last_link_down_time": (
            r"last-link-down-time="
            r"(\d{4}-\d{2}-\d{2}"
            r"\s+\d{2}:\d{2}:\d{2})"
        ),

        "link_downs": (
            r"\blink-downs=(\d+)"
        ),
    }

    for key, pattern in patterns.items():
        match = re.search(
            pattern,
            text,
        )

        if not match:
            continue

        value: Any = match.group(1)

        if key in {
            "mtu",
            "actual_mtu",
            "l2mtu",
            "max_l2mtu",
            "link_downs",
        }:
            if value.isdigit():
                value = int(value)

        interface[key] = value


def parse_interfaces(
    stdout: str,
) -> List[Dict[str, Any]]:
    """
    Parser para:

        /interface print detail without-paging

    Soporta formatos como:

        0 RS ;;; Uplink
             name="ether1" ...

    y:

        1  S name="ether2" ...
    """

    interfaces: List[Dict[str, Any]] = []

    if not stdout:
        return interfaces

    current: Dict[str, Any] | None = None

    def finish_current() -> None:
        nonlocal current

        if (
            current
            and current.get("name")
        ):
            interfaces.append(
                current
            )

        current = None

    for raw_line in stdout.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("Flags:"):
            continue

        # Inicio de una interfaz.
        #
        # Ejemplos:
        #
        # 0 RS ;;; Uplink
        # 1  S name="ether2" ...
        # 12 R  name="bridge1" ...

        start_match = re.match(
            r"^(\d+)\s+([A-Za-z]*)\s*(.*)$",
            line,
        )

        if start_match:
            finish_current()

            index = int(
                start_match.group(1)
            )

            flags = (
                start_match.group(2)
            )

            rest = (
                start_match.group(3).strip()
            )

            current = {
                "index": index,

                "flags": flags,

                "running": (
                    "R" in flags
                ),

                "slave": (
                    "S" in flags
                ),

                "disabled": (
                    "X" in flags
                ),

                "comment": None,

                "name": None,

                "default_name": None,

                "type": None,

                "mtu": None,

                "actual_mtu": None,

                "l2mtu": None,

                "max_l2mtu": None,

                "vrf": None,

                "mac_address": None,

                "last_link_up_time": None,

                "last_link_down_time": None,

                "link_downs": 0,
            }

            if rest.startswith(";;;"):
                current["comment"] = (
                    rest[3:].strip()
                )

            else:
                _update_interface_from_text(
                    current,
                    rest,
                )

            continue

        if current is None:
            continue

        if line.startswith(";;;"):
            current["comment"] = (
                line[3:].strip()
            )

            continue

        _update_interface_from_text(
            current,
            line,
        )

    finish_current()

    return interfaces


# ============================================================
# Interface statistics
# ============================================================

def parse_interface_stats(
    stdout: str,
) -> Dict[str, Dict[str, int]]:
    """
    Parser para:

        /interface print stats without-paging

    Devuelve estadísticas indexadas por nombre.
    """

    stats: Dict[str, Dict[str, int]] = {}

    if not stdout:
        return stats

    for raw_line in stdout.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("Flags:"):
            continue

        if line.startswith("Columns:"):
            continue

        if line.startswith("#"):
            continue

        if line.startswith(";;;"):
            continue

        # Ejemplo:
        #
        # 0 RS ether1 22 002 657 886  2 811 253 609 ...

        match = re.match(
            r"^(\d+)\s+"
            r"([A-Za-z]*)\s+"
            r"(\S+)\s+"
            r"(.*)$",
            line,
        )

        if not match:
            continue

        index = int(
            match.group(1)
        )

        name = (
            match.group(3)
        )

        numeric_text = (
            match.group(4)
        )

        # RouterOS separa las columnas con múltiples
        # espacios, pero también usa espacios como
        # separadores de miles.
        #
        # En la salida real del CRS112 las columnas
        # quedan separadas por 2+ espacios.

        columns = re.split(
            r"\s{2,}",
            numeric_text.strip(),
        )

        values = [
            _parse_routeros_number(value)
            for value in columns
        ]

        if len(values) < 4:
            continue

        stats[name] = {
            "index": index,

            "rx_bytes": (
                values[0]
            ),

            "tx_bytes": (
                values[1]
            ),

            "rx_packets": (
                values[2]
            ),

            "tx_packets": (
                values[3]
            ),

            "rx_drops": (
                values[4]
                if len(values) > 4
                else 0
            ),

            "tx_drops": (
                values[5]
                if len(values) > 5
                else 0
            ),
        }

    return stats


# ============================================================
# Merge interfaces + statistics
# ============================================================

def merge_interface_data(
    interfaces: List[Dict[str, Any]],
    stats: Dict[str, Dict[str, int]],
) -> List[Dict[str, Any]]:
    """
    Combina propiedades de interfaces con estadísticas.
    """

    result: List[Dict[str, Any]] = []

    for interface in interfaces:
        item = dict(
            interface
        )

        name = item.get(
            "name"
        )

        interface_stats = stats.get(
            name,
            {},
        )

        item["statistics"] = {
            "rx_bytes": interface_stats.get(
                "rx_bytes",
                0,
            ),

            "tx_bytes": interface_stats.get(
                "tx_bytes",
                0,
            ),

            "rx_packets": interface_stats.get(
                "rx_packets",
                0,
            ),

            "tx_packets": interface_stats.get(
                "tx_packets",
                0,
            ),

            "rx_drops": interface_stats.get(
                "rx_drops",
                0,
            ),

            "tx_drops": interface_stats.get(
                "tx_drops",
                0,
            ),
        }

        result.append(
            item
        )

    return result


# ============================================================
# Complete inventory parser
# ============================================================

def parse_inventory(
    inventory: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Convierte el inventario RAW producido por inventory.py
    en información estructurada preparada para análisis.
    """

    def stdout_of(
        section: str,
    ) -> str:

        value = inventory.get(
            section,
            {},
        )

        if not isinstance(
            value,
            dict,
        ):
            return ""

        return (
            value.get(
                "stdout",
                "",
            )
            or ""
        )

    identity = parse_identity(
        stdout_of(
            "identity"
        )
    )

    resources = parse_resources(
        stdout_of(
            "resources"
        )
    )

    routerboard = parse_routerboard(
        stdout_of(
            "routerboard"
        )
    )

    addresses = parse_addresses(
        stdout_of(
            "addresses"
        )
    )

    routes = parse_routes(
        stdout_of(
            "routes"
        )
    )

    connection_tracking = (
        parse_connection_tracking(
            stdout_of(
                "connection_tracking"
            )
        )
    )

    interfaces = parse_interfaces(
        stdout_of(
            "interfaces"
        )
    )

    interface_stats = (
        parse_interface_stats(
            stdout_of(
                "interface_stats"
            )
        )
    )

    interfaces = merge_interface_data(
        interfaces,
        interface_stats,
    )

    return {
        "device": {
            "identity": identity.get(
                "name"
            ),

            "model": routerboard.get(
                "model"
            ),

            "board_name": resources.get(
                "board_name"
            ),

            "platform": resources.get(
                "platform"
            ),

            "architecture": resources.get(
                "architecture"
            ),

            "routeros": resources.get(
                "version"
            ),

            "uptime": resources.get(
                "uptime"
            ),

            "revision": routerboard.get(
                "revision"
            ),

            "serial_number": routerboard.get(
                "serial_number"
            ),

            "firmware": {
                "current": routerboard.get(
                    "current_firmware"
                ),

                "available": routerboard.get(
                    "upgrade_firmware"
                ),
            },
        },

        "health": {
            "cpu": resources.get(
                "cpu"
            ),

            "cpu_count": resources.get(
                "cpu_count"
            ),

            "cpu_frequency": resources.get(
                "cpu_frequency"
            ),

            "cpu_load_percent": resources.get(
                "cpu_load_percent"
            ),

            "memory": {
                "free": resources.get(
                    "free_memory"
                ),

                "total": resources.get(
                    "total_memory"
                ),
            },

            "storage": {
                "free": resources.get(
                    "free_hdd_space"
                ),

                "total": resources.get(
                    "total_hdd_space"
                ),
            },
        },

        "network": {
            "addresses": addresses,
            "routes": routes,
            "interfaces": interfaces,
        },

        "connection_tracking": (
            connection_tracking
        ),
    }