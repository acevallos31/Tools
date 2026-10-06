from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .app_paths import logs_dir
from typing import Any, Callable, Dict, TypeVar


T = TypeVar("T")

SENSITIVE_KEYS = {
    "password",
    "pass",
    "secret",
    "token",
    "authorization",
    "credentials",
    "private_key",
    "privatekey",
    "psk",
    "passphrase",
    "community",
    "api_key",
    "apikey",
}

_WRITE_LOCK = threading.RLock()


def audit_path() -> Path:
    override = os.getenv("MIKROTIK_SKILL_AUDIT_LOG")
    if override:
        return Path(override)
    return logs_dir() / "mcp-audit.jsonl"


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        output: Dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                output[str(key)] = "<redacted>"
            else:
                output[str(key)] = _redact(item)
        return output
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


def record_event(event: Dict[str, Any]) -> None:
    """Append one redacted JSON event. Audit failures never break a tool call."""

    try:
        path = audit_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        safe_event = _redact(event)
        line = json.dumps(
            safe_event,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        with _WRITE_LOCK:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except Exception:
        # Observability must not become a new failure mode for read-only tools.
        return


def audited_call(
    tool: str,
    params: Dict[str, Any],
    fn: Callable[[], T],
) -> T:
    """Run a public MCP operation and record latency/outcome with a correlation id."""

    correlation_id = uuid.uuid4().hex
    started_wall = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()

    try:
        result = fn()
        duration_ms = round((time.perf_counter() - started) * 1000, 1)

        status = None
        operation = None
        execution = None
        if hasattr(result, "structured_content"):
            structured = getattr(result, "structured_content", None)
            if isinstance(structured, dict):
                status = structured.get("status")
                operation = structured.get("operation")
                execution = structured.get("execution")

        record_event(
            {
                "timestamp": started_wall,
                "correlation_id": correlation_id,
                "tool": tool,
                "device": params.get("device"),
                "phase": "failure" if status == "error" else "success",
                "duration_ms": duration_ms,
                "params": params,
                "result_status": status,
                "operation": operation,
                "execution": execution,
            }
        )
        return result
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        record_event(
            {
                "timestamp": started_wall,
                "correlation_id": correlation_id,
                "tool": tool,
                "device": params.get("device"),
                "phase": "failure",
                "duration_ms": duration_ms,
                "params": params,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        raise
