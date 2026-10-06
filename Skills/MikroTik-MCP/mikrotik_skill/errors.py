from __future__ import annotations

import socket
from typing import Any, Dict

import paramiko

from .client import SSHHostKeyMismatch


def classify_error(exc: Exception) -> Dict[str, Any]:
    """Return a stable, model-readable error classification."""

    details: Dict[str, Any] = {}

    if isinstance(exc, SSHHostKeyMismatch):
        code = "SSH_HOST_KEY_MISMATCH"
        retryable = False
        suggestion = (
            "Detén la conexión y verifica fuera de banda el fingerprint SSH "
            "del router antes de actualizar el pin del perfil."
        )
        details = {
            "expected_fingerprint": exc.expected,
            "actual_fingerprint": exc.actual,
        }
    elif isinstance(exc, FileNotFoundError):
        code = "LOCAL_RESOURCE_NOT_FOUND"
        retryable = False
        suggestion = (
            "Verifica que el perfil y su secreto local existan para el "
            "usuario de Windows que ejecuta Hermes."
        )
    elif isinstance(exc, paramiko.AuthenticationException):
        code = "SSH_AUTH_FAILED"
        retryable = False
        suggestion = "Verifica usuario, secreto DPAPI y permisos SSH del perfil."
    elif isinstance(exc, (socket.timeout, TimeoutError)):
        code = "SSH_TIMEOUT"
        retryable = True
        suggestion = "Verifica conectividad y vuelve a intentar la consulta."
    elif isinstance(exc, paramiko.SSHException):
        code = "SSH_CONNECTION_ERROR"
        retryable = True
        suggestion = (
            "La sesión SSH falló. El Session Manager intentará abrir una "
            "sesión nueva en la próxima llamada; no reutilices datos anteriores."
        )
    elif isinstance(exc, OSError):
        code = "DEVICE_UNREACHABLE"
        retryable = True
        suggestion = (
            "Verifica alcance IP/puerto SSH del router y vuelve a intentar."
        )
    elif isinstance(exc, ValueError):
        code = "INVALID_ARGUMENT"
        retryable = False
        suggestion = "Corrige los parámetros de la herramienta y vuelve a llamar."
    elif isinstance(exc, RuntimeError):
        code = "EXECUTION_FAILED"
        retryable = False
        suggestion = (
            "Revisa el detalle y la auditoría de la herramienta antes de "
            "repetir una medición costosa."
        )
    else:
        code = "UNEXPECTED_ERROR"
        retryable = False
        suggestion = "Revisa el log del MCP; no inventes un resultado alternativo."

    return {
        "code": code,
        "type": type(exc).__name__,
        "message": str(exc),
        "retryable": retryable,
        "suggested_action": suggestion,
        "details": details,
    }
