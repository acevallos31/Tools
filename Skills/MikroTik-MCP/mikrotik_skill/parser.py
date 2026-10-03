import ipaddress
import re
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Optional


RATE_RE = re.compile(
    r"^([\d.]+)(bps|kbps|Mbps|Gbps)$",
    re.IGNORECASE,
)

PORT_RE = re.compile(
    r"^(\d+)(?:\s+\([^)]+\))?$"
)


@dataclass
class TorchFlow:
    protocol: str
    dscp: Optional[int]
    src_address: str
    src_port: Optional[int]
    dst_address: Optional[str]
    dst_port: Optional[int]
    tx_bps: Optional[int]
    rx_bps: Optional[int]
    observations: int = 1

    def to_dict(self):
        return asdict(self)


def is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def parse_port(value: str) -> Optional[int]:
    match = PORT_RE.match(value)

    if not match:
        return None

    port = int(match.group(1))

    if 0 <= port <= 65535:
        return port

    return None


def parse_rate(value: str) -> Optional[int]:
    match = RATE_RE.match(value)

    if not match:
        return None

    number = float(match.group(1))
    unit = match.group(2).lower()

    multipliers = {
        "bps": 1,
        "kbps": 1_000,
        "mbps": 1_000_000,
        "gbps": 1_000_000_000,
    }

    return int(
        number * multipliers[unit]
    )


def tokenize(line: str):
    return re.findall(
        r"\d+\s+\([^)]+\)|\S+",
        line.strip(),
    )


def parse_line(line: str) -> Optional[TorchFlow]:

    tokens = tokenize(line)

    if not tokens:
        return None

    protocol_index = None

    for index, token in enumerate(tokens):

        if token in {
            "tcp",
            "udp",
            "icmp",
            "icmpv6",
            "igmp",
        }:
            protocol_index = index
            break

    if protocol_index is None:
        return None

    protocol = tokens[protocol_index]

    src_index = None

    for index in range(
        protocol_index + 1,
        len(tokens),
    ):
        if is_ip(tokens[index]):
            src_index = index
            break

    if src_index is None:
        return None

    src_address = tokens[src_index]

    dscp = None

    if src_index > 0:
        candidate = tokens[src_index - 1]

        if candidate.isdigit():
            value = int(candidate)

            if 0 <= value <= 63:
                dscp = value

    cursor = src_index + 1

    src_port = None

    if cursor < len(tokens):
        src_port = parse_port(tokens[cursor])

        if src_port is not None:
            cursor += 1

    dst_address = None

    for index in range(cursor, len(tokens)):

        if is_ip(tokens[index]):
            dst_address = tokens[index]
            cursor = index + 1
            break

    dst_port = None

    if (
        dst_address is not None
        and cursor < len(tokens)
    ):
        dst_port = parse_port(tokens[cursor])

        if dst_port is not None:
            cursor += 1

    rates = []

    for token in tokens[cursor:]:

        rate = parse_rate(token)

        if rate is not None:
            rates.append(rate)

    tx_bps = (
        rates[0]
        if len(rates) >= 1
        else None
    )

    rx_bps = (
        rates[1]
        if len(rates) >= 2
        else None
    )

    return TorchFlow(
        protocol=protocol,
        dscp=dscp,
        src_address=src_address,
        src_port=src_port,
        dst_address=dst_address,
        dst_port=dst_port,
        tx_bps=tx_bps,
        rx_bps=rx_bps,
    )


def flow_key(flow: TorchFlow):
    return (
        flow.protocol,
        flow.dscp,
        flow.src_address,
        flow.src_port,
        flow.dst_address,
        flow.dst_port,
    )


def parse_torch(raw: str):

    flows = {}

    raw_rows = 0
    ignored_lines = 0

    for line in raw.splitlines():

        stripped = line.strip()

        if not stripped:
            continue

        if (
            stripped.startswith("Columns:")
            or "MAC-PROTOCOL" in stripped
            or stripped.startswith("MA ")
            or stripped.startswith("VLAN-ID ")
        ):
            ignored_lines += 1
            continue

        flow = parse_line(line)

        if flow is None:
            ignored_lines += 1
            continue

        raw_rows += 1

        key = flow_key(flow)

        if key not in flows:
            flows[key] = flow
            continue

        existing = flows[key]

        existing.observations += 1

        if flow.tx_bps is not None:
            existing.tx_bps = flow.tx_bps

        if flow.rx_bps is not None:
            existing.rx_bps = flow.rx_bps

    result = list(flows.values())

    protocols = Counter(
        flow.protocol
        for flow in result
    )

    return {
        "raw_rows": raw_rows,
        "unique_flows": len(result),
        "ignored_lines": ignored_lines,
        "protocols": dict(protocols),
        "flows": [
            flow.to_dict()
            for flow in result
        ],
    }
