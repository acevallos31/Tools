import ipaddress
from collections import Counter, defaultdict
from typing import Any, Dict, Optional


def is_private(address: Optional[str]) -> bool:
    if not address:
        return False

    try:
        return ipaddress.ip_address(address).is_private
    except ValueError:
        return False


def format_bps(bps: int) -> str:
    if bps >= 1_000_000_000:
        return f"{bps / 1_000_000_000:.2f} Gbps"

    if bps >= 1_000_000:
        return f"{bps / 1_000_000:.2f} Mbps"

    if bps >= 1_000:
        return f"{bps / 1_000:.2f} Kbps"

    return f"{bps} bps"


def classify_flow(flow: Dict[str, Any]) -> str:
    src = flow.get("src_address")
    dst = flow.get("dst_address")

    src_private = is_private(src)
    dst_private = is_private(dst)

    if src_private and dst_private:
        return "internal"

    if src_private and not dst_private:
        return "outbound"

    if not src_private and dst_private:
        return "inbound"

    if not src_private and not dst_private:
        return "external"

    return "unknown"


def analyze_torch(
    parsed: Dict[str, Any],
    top_n: int = 10,
) -> Dict[str, Any]:

    flows = parsed.get("flows", [])

    protocols = Counter()
    classifications = Counter()

    source_flows = Counter()
    destination_flows = Counter()

    source_bps = defaultdict(int)
    destination_bps = defaultdict(int)

    destination_ports = Counter()
    destination_port_bps = defaultdict(int)

    measured_flows = 0
    total_observed_bps = 0

    for flow in flows:

        protocol = flow.get("protocol", "unknown")
        src = flow.get("src_address")
        dst = flow.get("dst_address")
        dst_port = flow.get("dst_port")

        tx = flow.get("tx_bps")
        rx = flow.get("rx_bps")

        protocols[protocol] += 1

        classification = classify_flow(flow)
        classifications[classification] += 1

        if src:
            source_flows[src] += 1

        if dst:
            destination_flows[dst] += 1

        if dst_port is not None:
            destination_ports[dst_port] += 1

        observed_bps = 0

        if tx is not None:
            observed_bps += tx

        if rx is not None:
            observed_bps += rx

        if tx is not None or rx is not None:
            measured_flows += 1

        if observed_bps:

            total_observed_bps += observed_bps

            if src:
                source_bps[src] += observed_bps

            if dst:
                destination_bps[dst] += observed_bps

            if dst_port is not None:
                destination_port_bps[dst_port] += observed_bps

    def top_rates(values):
        result = []

        for key, bps in sorted(
            values.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:top_n]:

            result.append(
                {
                    "value": key,
                    "bps": bps,
                    "human": format_bps(bps),
                }
            )

        return result

    return {
        "summary": {
            "raw_rows":
                parsed.get("raw_rows", 0),

            "unique_flows":
                parsed.get("unique_flows", 0),

            "measured_flows":
                measured_flows,

            "total_observed_bps":
                total_observed_bps,

            "total_observed_human":
                format_bps(total_observed_bps),
        },

        "protocols":
            dict(protocols),

        "flow_classification":
            dict(classifications),

        "top_sources_by_flows": [
            {
                "ip": ip,
                "flows": count,
            }
            for ip, count
            in source_flows.most_common(top_n)
        ],

        "top_destinations_by_flows": [
            {
                "ip": ip,
                "flows": count,
            }
            for ip, count
            in destination_flows.most_common(top_n)
        ],

        "top_destination_ports_by_flows": [
            {
                "port": port,
                "flows": count,
            }
            for port, count
            in destination_ports.most_common(top_n)
        ],

        "top_sources_by_observed_rate":
            top_rates(source_bps),

        "top_destinations_by_observed_rate":
            top_rates(destination_bps),

        "top_ports_by_observed_rate":
            top_rates(destination_port_bps),
    }


def build_traffic_report(
    parsed: Dict[str, Any],
    target: str,
    interface: str,
    duration: int,
    timestamp: str,
    top_n: int = 10,
) -> Dict[str, Any]:

    analysis = analyze_torch(
        parsed,
        top_n=top_n,
    )

    return {
        "device": {
            "target": target,
            "interface": interface,
        },

        "capture": {
            "duration_seconds": duration,
            "timestamp": timestamp,
        },

        "analysis": analysis,
    }
