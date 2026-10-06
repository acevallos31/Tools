from __future__ import annotations

from unittest.mock import patch

import pytest

from mikrotik_skill.client import CommandResult
from mikrotik_skill.cpu_sampling import (
    sample_cpu,
    validate_cpu_sample_request,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def perf_counter(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class FakeClient:
    def __init__(self, values: list[int]):
        self.values = iter(values)

    def execute(self, command: str) -> CommandResult:
        value = next(self.values)
        return CommandResult(
            command=command,
            stdout=f"cpu-load: {value}%\n",
            stderr="",
            exit_status=0,
        )


def test_cpu_sample_validation() -> None:
    assert validate_cpu_sample_request(30, 1) == (30, 1)

    with pytest.raises(ValueError):
        validate_cpu_sample_request(4, 1)

    with pytest.raises(ValueError):
        validate_cpu_sample_request(121, 1)

    with pytest.raises(ValueError):
        validate_cpu_sample_request(30, 0)


def test_cpu_sample_statistics() -> None:
    client = FakeClient([10, 20, 30])
    clock = FakeClock()

    with patch(
        "mikrotik_skill.cpu_sampling.validate_cpu_sample_request",
        return_value=(2, 1),
    ), patch(
        "mikrotik_skill.cpu_sampling.time.perf_counter",
        side_effect=clock.perf_counter,
    ), patch(
        "mikrotik_skill.cpu_sampling.time.sleep",
        side_effect=clock.sleep,
    ):
        result = sample_cpu(client, duration=2, interval=1)

    assert result["sample_count"] == 3
    assert result["statistics"] == {
        "minimum_percent": 10,
        "maximum_percent": 30,
        "average_percent": 20.0,
        "median_percent": 20,
        "first_percent": 10,
        "last_percent": 30,
    }
    assert [x["cpu_percent"] for x in result["readings"]] == [10, 20, 30]
    assert result["actual_duration_seconds"] >= 2
