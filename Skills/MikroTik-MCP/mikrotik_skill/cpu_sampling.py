from __future__ import annotations

import statistics
import time
from typing import Any, Dict, List

from .client import MikroTikClient
from .inventory_parser import parse_resources


CPU_SAMPLE_COMMAND = "/system resource print"
MIN_DURATION_SECONDS = 5
MAX_DURATION_SECONDS = 120
MIN_INTERVAL_SECONDS = 1
MAX_SAMPLES = 120
CPU_MIN_PERCENT = 0
CPU_MAX_PERCENT = 100


def validate_cpu_sample_request(
    duration: int,
    interval: int,
) -> tuple[int, int]:
    """Valida límites para evitar loops arbitrarios contra RouterOS."""

    duration = int(duration)
    interval = int(interval)

    if not MIN_DURATION_SECONDS <= duration <= MAX_DURATION_SECONDS:
        raise ValueError(
            f"duration debe estar entre {MIN_DURATION_SECONDS} y "
            f"{MAX_DURATION_SECONDS} segundos."
        )

    if interval < MIN_INTERVAL_SECONDS:
        raise ValueError(
            f"interval debe ser al menos {MIN_INTERVAL_SECONDS} segundo."
        )

    expected = (duration // interval) + 1
    if expected > MAX_SAMPLES:
        raise ValueError(
            f"La solicitud excede el máximo de {MAX_SAMPLES} muestras."
        )

    return duration, interval


def sample_cpu(
    client: MikroTikClient,
    duration: int = 30,
    interval: int = 1,
) -> Dict[str, Any]:
    """Muestrea CPU durante una ventana temporal usando una sola sesión SSH."""

    duration, interval = validate_cpu_sample_request(duration, interval)

    started = time.perf_counter()
    next_sample = started
    readings: List[Dict[str, Any]] = []

    while True:
        now = time.perf_counter()
        if now < next_sample:
            time.sleep(next_sample - now)

        sample_started = time.perf_counter()
        result = client.execute(CPU_SAMPLE_COMMAND)

        if not result.ok:
            raise RuntimeError(
                "No se pudo consultar /system resource print: "
                f"{result.stderr.strip() or 'salida no válida'}"
            )

        resources = parse_resources(result.stdout)
        raw_cpu = resources.get("cpu_load_percent")
        if raw_cpu is None:
            raise RuntimeError(
                "RouterOS no devolvió cpu-load en la muestra."
            )

        cpu = int(raw_cpu)
        if not CPU_MIN_PERCENT <= cpu <= CPU_MAX_PERCENT:
            raise RuntimeError(
                f"Valor cpu-load fuera de rango: {cpu}"
            )
        elapsed = sample_started - started

        readings.append(
            {
                "elapsed_seconds": round(elapsed, 3),
                "cpu_percent": cpu,
            }
        )

        if sample_started - started >= duration:
            break

        next_sample += interval

        # Si SSH tardó más que el intervalo, no intentamos recuperar
        # muestras atrasadas en ráfaga: reanudamos desde el tiempo actual.
        if next_sample <= time.perf_counter():
            next_sample = time.perf_counter() + interval

    values = [item["cpu_percent"] for item in readings]

    return {
        "requested_duration_seconds": duration,
        "interval_seconds": interval,
        "actual_duration_seconds": round(time.perf_counter() - started, 3),
        "sample_count": len(readings),
        "statistics": {
            "minimum_percent": min(values),
            "maximum_percent": max(values),
            "average_percent": round(statistics.fmean(values), 2),
            "median_percent": round(statistics.median(values), 2),
            "first_percent": values[0],
            "last_percent": values[-1],
        },
        "readings": readings,
    }
