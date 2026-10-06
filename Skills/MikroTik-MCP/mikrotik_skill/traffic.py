from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from .client import MikroTikClient
from .config import CONFIG
from .validation import validate_interface_name


@dataclass
class TorchResult:
    status: str
    target: str
    interface: str
    duration_seconds: int
    timestamp: str
    command: str
    stdout: str
    stderr: str
    exit_status: int

    def to_dict(self):
        return asdict(self)


def capture_torch(
    client: MikroTikClient,
    interface: Optional[str] = None,
    duration: Optional[int] = None,
) -> TorchResult:
    """
    Ejecuta MikroTik Torch de forma controlada.

    La duración está limitada para evitar capturas excesivamente
    largas cuando la función sea invocada por Hermes/Qwen.
    """

    interface = interface or CONFIG.default_interface
    duration = duration or CONFIG.torch_duration

    # Guardrail: limitar duración de Torch.
    if not 1 <= duration <= 30:
        raise ValueError(
            "La duración de Torch debe estar entre 1 y 30 segundos."
        )

    interface = validate_interface_name(interface)

    command = (
        f"/tool torch "
        f"interface={interface} "
        f"duration={duration}s"
    )

    result = client.execute(
        command,
        timeout=duration + 10,
    )

    return TorchResult(
        status=(
            "ok"
            if result.ok and result.stdout
            else "empty"
        ),
        target=client.host,
        interface=interface,
        duration_seconds=duration,
        timestamp=datetime.now().isoformat(),
        command=command,
        stdout=result.stdout,
        stderr=result.stderr,
        exit_status=result.exit_status,
    )


def save_raw_capture(
    capture: TorchResult,
    directory: Optional[Path] = None,
) -> Path:
    """
    Guarda la salida RAW de RouterOS Torch.

    Esto permite auditoría y reprocesamiento posterior
    sin tener que ejecutar una nueva captura.
    """

    directory = directory or CONFIG.raw_dir

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    filename = (
        f"torch_{capture.interface}_"
        f"{timestamp}.txt"
    )

    path = directory / filename

    path.write_text(
        capture.stdout,
        encoding="utf-8",
    )

    return path


def analyze_device_traffic(
    client: MikroTikClient,
    interface: Optional[str] = None,
    duration: Optional[int] = None,
) -> dict:
    """
    Ejecuta el pipeline completo de análisis de tráfico.

    Flujo:

        MikroTik
            ↓
        Torch
            ↓
        captura RAW
            ↓
        parse_torch()
            ↓
        build_traffic_report()
            ↓
        analyze_torch()
            ↓
        reporte estructurado

    Esta función será el punto de entrada principal
    para Hermes/Qwen y futuras automatizaciones.
    """

    # Imports locales para mantener los módulos desacoplados
    # y reducir el riesgo de imports circulares.
    from .parser import parse_torch
    from .analyzer import build_traffic_report

    interface = (
        interface
        or CONFIG.default_interface
    )

    duration = (
        duration
        or CONFIG.torch_duration
    )

    # -----------------------------------------------------
    # 1. Capturar tráfico
    # -----------------------------------------------------

    capture = capture_torch(
        client=client,
        interface=interface,
        duration=duration,
    )

    if capture.status != "ok":
        raise RuntimeError(
            "Torch no devolvió datos válidos. "
            f"status={capture.status}, "
            f"stderr={capture.stderr!r}"
        )

    # -----------------------------------------------------
    # 2. Guardar captura RAW
    # -----------------------------------------------------

    raw_path = save_raw_capture(
        capture
    )

    # -----------------------------------------------------
    # 3. Parsear salida RouterOS
    # -----------------------------------------------------

    parsed = parse_torch(
        capture.stdout
    )

    # No continuamos si Torch devolvió texto pero
    # el parser no logró detectar ningún flujo.
    if parsed.get("unique_flows", 0) == 0:
        raise RuntimeError(
            "Torch produjo datos, pero el parser "
            "no detectó ningún flujo."
        )

    # -----------------------------------------------------
    # 4. Construir reporte
    #
    # build_traffic_report() llama internamente
    # a analyze_torch(), por lo que NO debemos
    # ejecutar analyze_torch() otra vez aquí.
    # -----------------------------------------------------

    report = build_traffic_report(
        parsed=parsed,
        target=capture.target,
        interface=capture.interface,
        duration=capture.duration_seconds,
        timestamp=capture.timestamp,
    )

    # -----------------------------------------------------
    # 5. Agregar trazabilidad
    # -----------------------------------------------------

    report["capture"]["raw_capture_file"] = raw_path.name
    report["capture"]["evidence_note"] = (
        "Torch describe flujos y tasas observadas durante esta captura. "
        "No demuestra por sí solo estabilidad, causalidad ni ausencia de amenazas."
    )

    return report
