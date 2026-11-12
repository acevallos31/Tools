from __future__ import annotations

from io import BytesIO

from PIL import Image

from mikrotik_skill.charting import render_cpu_chart, render_interface_chart


def test_cpu_chart_is_valid_png() -> None:
    data = render_cpu_chart(
        {
            "readings": [
                {"elapsed_seconds": 0, "cpu_percent": 10},
                {"elapsed_seconds": 1, "cpu_percent": 50},
                {"elapsed_seconds": 2, "cpu_percent": 20},
            ]
        }
    )

    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    image = Image.open(BytesIO(data))
    assert image.size == (960, 480)


def test_interface_chart_is_valid_png() -> None:
    data = render_interface_chart(
        {
            "interface": "ether1",
            "readings": [
                {"elapsed_seconds": 0, "rx_bps": 1000, "tx_bps": 500},
                {"elapsed_seconds": 1, "rx_bps": 3000, "tx_bps": 800},
            ],
        }
    )

    assert data.startswith(b"\x89PNG\r\n\x1a\n")
