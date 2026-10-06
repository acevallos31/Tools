from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, Iterable, Tuple

from PIL import Image, ImageDraw, ImageFont


WIDTH = 960
HEIGHT = 480
MARGIN_LEFT = 70
MARGIN_RIGHT = 30
MARGIN_TOP = 55
MARGIN_BOTTOM = 65


def _font() -> ImageFont.ImageFont:
    return ImageFont.load_default()


def _scale_points(
    readings: Iterable[Dict[str, Any]],
    key: str,
    y_max: float,
) -> list[Tuple[float, float]]:
    rows = list(readings)
    if not rows:
        return []

    max_time = max(float(row.get("elapsed_seconds", 0.0)) for row in rows)
    max_time = max(max_time, 1.0)

    plot_w = WIDTH - MARGIN_LEFT - MARGIN_RIGHT
    plot_h = HEIGHT - MARGIN_TOP - MARGIN_BOTTOM

    points: list[Tuple[float, float]] = []
    for row in rows:
        elapsed = float(row.get("elapsed_seconds", 0.0))
        value = max(0.0, min(float(row.get(key, 0.0)), y_max))
        x = MARGIN_LEFT + (elapsed / max_time) * plot_w
        y = MARGIN_TOP + plot_h - (value / y_max) * plot_h
        points.append((x, y))

    return points


def _base_canvas(
    title: str,
    x_label: str,
    y_label: str,
    y_max: float,
    y_suffix: str = "",
) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    font = _font()

    x0 = MARGIN_LEFT
    y0 = HEIGHT - MARGIN_BOTTOM
    x1 = WIDTH - MARGIN_RIGHT
    y1 = MARGIN_TOP

    draw.text((MARGIN_LEFT, 18), title, fill="black", font=font)
    draw.line((x0, y0, x1, y0), fill="black", width=2)
    draw.line((x0, y0, x0, y1), fill="black", width=2)

    for idx in range(5):
        ratio = idx / 4
        y = y0 - ratio * (y0 - y1)
        value = y_max * ratio
        draw.line((x0 - 5, y, x1, y), fill="#dddddd", width=1)
        label = f"{value:.0f}{y_suffix}"
        draw.text((8, y - 6), label, fill="black", font=font)

    draw.text(
        ((WIDTH - len(x_label) * 6) / 2, HEIGHT - 30),
        x_label,
        fill="black",
        font=font,
    )
    draw.text((8, 38), y_label, fill="black", font=font)

    return image, draw


def _png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def render_cpu_chart(sample: Dict[str, Any]) -> bytes:
    readings = sample.get("readings", [])
    image, draw = _base_canvas(
        title="MikroTik CPU load over time",
        x_label="Elapsed time (seconds)",
        y_label="CPU load",
        y_max=100.0,
        y_suffix="%",
    )

    points = _scale_points(readings, "cpu_percent", 100.0)
    if len(points) >= 2:
        draw.line(points, fill="#2457a7", width=3)
    for point in points:
        x, y = point
        draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill="#2457a7")

    return _png_bytes(image)


def render_interface_chart(sample: Dict[str, Any]) -> bytes:
    readings = sample.get("readings", [])
    peak = 1.0
    for row in readings:
        peak = max(
            peak,
            float(row.get("rx_bps", 0.0)),
            float(row.get("tx_bps", 0.0)),
        )

    # Round the ceiling upward to give the graph breathing room.
    y_max = max(1_000.0, peak * 1.10)

    interface = sample.get("interface", "interface")
    image, draw = _base_canvas(
        title=f"MikroTik interface traffic - {interface}",
        x_label="Elapsed time (seconds)",
        y_label="Bits per second",
        y_max=y_max,
    )

    rx = _scale_points(readings, "rx_bps", y_max)
    tx = _scale_points(readings, "tx_bps", y_max)

    if len(rx) >= 2:
        draw.line(rx, fill="#2457a7", width=3)
    if len(tx) >= 2:
        draw.line(tx, fill="#9a3f22", width=3)

    font = _font()
    draw.text((WIDTH - 175, 18), "RX", fill="#2457a7", font=font)
    draw.text((WIDTH - 125, 18), "TX", fill="#9a3f22", font=font)

    return _png_bytes(image)
