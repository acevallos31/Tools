from __future__ import annotations

from unittest.mock import patch

import pytest

from mikrotik_skill.client import CommandResult
from mikrotik_skill.interface_sampling import (
    _parse_monitor_traffic,
    sample_interface_traffic,
    validate_interface_sample_request,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def perf_counter(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class FakeClient:
    def __init__(self, values: list[tuple[str, str]]) -> None:
        self.values = iter(values)
        self.commands: list[str] = []

    def execute(self, command: str) -> CommandResult:
        self.commands.append(command)
        rx, tx = next(self.values)
        return CommandResult(
            command=command,
            stdout=(
                "name: ether1\n"
                f"rx-bits-per-second: {rx}\n"
                f"tx-bits-per-second: {tx}\n"
                "rx-packets-per-second: 10\n"
                "tx-packets-per-second: 5\n"
                "tx-queue-drops-per-second: 0\n"
            ),
            stderr="",
            exit_status=0,
        )


def test_parse_monitor_traffic_rates() -> None:
    parsed = _parse_monitor_traffic(
        "rx-bits-per-second: 27.8kbps\n"
        "tx-bits-per-second: 1.2Mbps\n"
    )
    assert parsed["rx_bps"] == 27_800
    assert parsed["tx_bps"] == 1_200_000


def test_interface_sample_validation() -> None:
    assert validate_interface_sample_request(30, 1) == (30, 1)
    assert validate_interface_sample_request(120, 1) == (120, 1)

    with pytest.raises(ValueError):
        validate_interface_sample_request(4, 1)

    with pytest.raises(ValueError):
        validate_interface_sample_request(30, 0)

    with pytest.raises(ValueError):
        validate_interface_sample_request(30, 121)


def test_interface_sampling_statistics_and_timestamps() -> None:
    client = FakeClient(
        [
            ("1kbps", "500bps"),
            ("3kbps", "1500bps"),
        ]
    )
    clock = FakeClock()

    with patch(
        "mikrotik_skill.interface_sampling.time.perf_counter",
        side_effect=clock.perf_counter,
    ), patch(
        "mikrotik_skill.interface_sampling.time.sleep",
        side_effect=clock.sleep,
    ), patch(
        "mikrotik_skill.interface_sampling.validate_interface_sample_request",
        return_value=(2, 1),
    ):
        result = sample_interface_traffic(
            client,
            "ether1",
            duration=2,
            interval=1,
        )

    assert result["sample_count"] == 2
    assert result["statistics"]["rx_bps"] == {
        "minimum": 1000,
        "maximum": 3000,
        "average": 2000.0,
        "median": 2000.0,
        "first": 1000,
        "last": 3000,
    }
    assert result["statistics"]["tx_bps"]["average"] == 1000.0
    assert result["statistics"]["rx_packets_per_second"]["average"] == 10.0
    assert (
        result["statistics"]["tx_queue_drops_per_second"]["observed_nonzero"]
        is False
    )
    assert all(row["timestamp"] for row in result["readings"])
    assert [row["elapsed_seconds"] for row in result["readings"]] == [0.0, 1.0]
    assert result["actual_duration_seconds"] == 2.0
    assert all(
        command == "/interface monitor-traffic ether1 once"
        for command in client.commands
    )


def test_interface_sampling_does_not_overshoot_non_divisible_window() -> None:
    client = FakeClient(
        [
            ("1kbps", "500bps"),
            ("2kbps", "1kbps"),
        ]
    )
    clock = FakeClock()

    with patch(
        "mikrotik_skill.interface_sampling.time.perf_counter",
        side_effect=clock.perf_counter,
    ), patch(
        "mikrotik_skill.interface_sampling.time.sleep",
        side_effect=clock.sleep,
    ):
        result = sample_interface_traffic(
            client,
            "ether1",
            duration=5,
            interval=4,
        )

    assert result["sample_count"] == 2
    assert [row["elapsed_seconds"] for row in result["readings"]] == [0.0, 4.0]
    assert result["actual_duration_seconds"] == 5.0
