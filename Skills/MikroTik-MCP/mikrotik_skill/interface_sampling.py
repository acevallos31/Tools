from __future__ import annotations

import math
import statistics
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from .client import MikroTikClient
from .parser import parse_rate
from .validation import validate_interface_name


MIN_DURATION_SECONDS = 5
MAX_DURATION_SECONDS = 120
MIN_INTERVAL_SECONDS = 1
MAX_INTERVAL_SECONDS = 120
MAX_SAMPLES = 120


def validate_interface_sample_request(
    duration: int,
    interval: int,
) -> tuple[int, int]:
    duration = int(duration)
    interval = int(interval)

    if not MIN_DURATION_SECONDS <= duration <= MAX_DURATION_SECONDS:
        raise ValueError(
            f"duration debe estar entre {MIN_DURATION_SECONDS} y "
            f"{MAX_DURATION_SECONDS} segundos."
        )
    if not MIN_INTERVAL_SECONDS <= interval <= MAX_INTERVAL_SECONDS:
        raise ValueError(
            f"interval debe estar entre {MIN_INTERVAL_SECONDS} y "
            f"{MAX_INTERVAL_SECONDS} segundos."
        )

    expected = math.ceil(duration / interval)
    if expected > MAX_SAMPLES:
        raise ValueError(
            f"La solicitud excede el máximo de {MAX_SAMPLES} muestras."
        )

    return duration, interval


def _parse_monitor_traffic(stdout: str) -> Dict[str, int]:
    fields: Dict[str, str] = {}
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()

    rx_text = (
        fields.get("rx-bits-per-second")
        or fields.get("received-bits-per-second")
        or "0bps"
    )
    tx_text = (
        fields.get("tx-bits-per-second")
        or fields.get("sent-bits-per-second")
        or "0bps"
    )

    rx_bps = parse_rate(rx_text)
    tx_bps = parse_rate(tx_text)

    if rx_bps is None or tx_bps is None:
        raise RuntimeError(
            "RouterOS devolvió una tasa de interfaz que no se pudo interpretar."
        )

    def integer_field(*names: str) -> int:
        for name in names:
            value = fields.get(name)
            if value is not None:
                digits = "".join(ch for ch in value if ch.isdigit())
                return int(digits) if digits else 0
        return 0

    return {
        "rx_bps": rx_bps,
        "tx_bps": tx_bps,
        "rx_packets_per_second": integer_field(
            "rx-packets-per-second",
            "received-packets-per-second",
        ),
        "tx_packets_per_second": integer_field(
            "tx-packets-per-second",
            "sent-packets-per-second",
        ),
        "tx_queue_drops_per_second": integer_field(
            "tx-queue-drops-per-second",
        ),
    }


def _sleep_until(deadline: float) -> None:
    remaining = deadline - time.perf_counter()
    if remaining > 0:
        time.sleep(remaining)


def _statistics(values: list[int]) -> Dict[str, float | int]:
    return {
        "minimum": min(values),
        "maximum": max(values),
        "average": round(statistics.fmean(values), 2),
        "median": round(statistics.median(values), 2),
        "first": values[0],
        "last": values[-1],
    }


def sample_interface_traffic(
    client: MikroTikClient,
    interface: str,
    duration: int = 30,
    interval: int = 1,
) -> Dict[str, Any]:
    """Sample live interface rates using RouterOS monitor-traffic once."""

    interface = validate_interface_name(interface)
    duration, interval = validate_interface_sample_request(duration, interval)

    window_started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    deadline = started + duration
    next_sample = started
    readings: List[Dict[str, Any]] = []

    while True:
        _sleep_until(next_sample)

        sample_started = time.perf_counter()
        result = client.execute(
            f"/interface monitor-traffic {interface} once"
        )

        if not result.ok:
            raise RuntimeError(
                "No se pudo ejecutar /interface monitor-traffic: "
                f"{result.stderr.strip() or 'salida no válida'}"
            )

        rates = _parse_monitor_traffic(result.stdout)
        readings.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "elapsed_seconds": round(sample_started - started, 3),
                **rates,
            }
        )

        after_sample = time.perf_counter()
        if after_sample >= deadline:
            break

        candidate = next_sample + interval

        if candidate >= deadline:
            _sleep_until(deadline)
            break

        # Si el comando tardó más que el intervalo, omitimos slots vencidos
        # en lugar de generar una ráfaga de mediciones atrasadas.
        if candidate <= after_sample:
            candidate = after_sample + interval

        if candidate >= deadline:
            _sleep_until(deadline)
            break

        next_sample = candidate

    metric_values = {
        "rx_bps": [item["rx_bps"] for item in readings],
        "tx_bps": [item["tx_bps"] for item in readings],
        "rx_packets_per_second": [
            item["rx_packets_per_second"] for item in readings
        ],
        "tx_packets_per_second": [
            item["tx_packets_per_second"] for item in readings
        ],
        "tx_queue_drops_per_second": [
            item["tx_queue_drops_per_second"] for item in readings
        ],
    }

    statistics_payload = {
        name: _statistics(values)
        for name, values in metric_values.items()
    }
    statistics_payload["tx_queue_drops_per_second"]["observed_nonzero"] = any(
        value > 0
        for value in metric_values["tx_queue_drops_per_second"]
    )

    return {
        "measurement": {
            "kind": "time_series",
            "metric": "interface_rate_bps",
            "source": f"/interface monitor-traffic {interface} once",
            "window_started_at": window_started_at,
            "window_completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "interface": interface,
        "requested_duration_seconds": duration,
        "interval_seconds": interval,
        "actual_duration_seconds": round(time.perf_counter() - started, 3),
        "sample_count": len(readings),
        "statistics": statistics_payload,
        "readings": readings,
        "evidence_note": (
            "Estas tasas provienen de /interface monitor-traffic y corresponden "
            "a la ventana observada; no son contadores acumulados."
        ),
    }
