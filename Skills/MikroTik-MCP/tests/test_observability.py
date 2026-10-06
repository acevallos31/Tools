from __future__ import annotations

import json

from mikrotik_skill.observability import audited_call


class FakeResult:
    structured_content = {
        "status": "ok",
        "operation": "health",
        "execution": {"elapsed_seconds": 0.1},
    }


def test_audit_log_redacts_sensitive_values(tmp_path, monkeypatch) -> None:
    path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("MIKROTIK_SKILL_AUDIT_LOG", str(path))

    result = audited_call(
        "test_tool",
        {
            "device": "laboratorio",
            "password": "should-not-appear",
            "nested": {"token": "secret-token"},
        },
        lambda: FakeResult(),
    )

    assert isinstance(result, FakeResult)
    event = json.loads(path.read_text(encoding="utf-8").strip())
    assert event["tool"] == "test_tool"
    assert event["params"]["password"] == "<redacted>"
    assert event["params"]["nested"]["token"] == "<redacted>"
    assert "should-not-appear" not in path.read_text(encoding="utf-8")
