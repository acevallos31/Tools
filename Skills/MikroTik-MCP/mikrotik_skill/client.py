import base64
import hashlib
import hmac
from dataclasses import dataclass
from typing import Optional

import paramiko

from .config import CONFIG, MikroTikConfig


@dataclass
class CommandResult:
    command: str
    stdout: str
    stderr: str
    exit_status: int

    @property
    def ok(self) -> bool:
        return (
            self.exit_status == 0
            and not self.stderr.strip()
        )


class MikroTikClient:
    def __init__(
        self,
        config: MikroTikConfig = CONFIG,
        password: Optional[str] = None,
        *,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        host_key_sha256: Optional[str] = None,
    ):
        self.config = config

        self.host = (
            host
            if host is not None
            else config.host
        )

        self.port = (
            port
            if port is not None
            else config.port
        )

        self.username = (
            username
            if username is not None
            else config.username
        )

        self.password = password
        self.host_key_sha256 = host_key_sha256
        self.host_key_verified = False
        self.host_key_fingerprint: Optional[str] = None

        self.client: Optional[
            paramiko.SSHClient
        ] = None

    def connect(self) -> None:
        if self.client is not None:
            return

        if not self.host:
            raise ValueError(
                "El host SSH está vacío."
            )

        if not self.username:
            raise ValueError(
                "El usuario SSH está vacío."
            )

        if not 1 <= int(self.port) <= 65535:
            raise ValueError(
                f"Puerto SSH inválido: {self.port}"
            )

        if not self.password:
            raise ValueError(
                "La contraseña SSH está vacía."
            )

        client = paramiko.SSHClient()

        # System known_hosts is honored when present. A profile-level SHA256
        # pin provides explicit verification even when the host is not known.
        client.load_system_host_keys()
        client.set_missing_host_key_policy(
            paramiko.AutoAddPolicy()
        )

        client.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            timeout=self.config.connect_timeout,
            banner_timeout=self.config.connect_timeout,
            auth_timeout=self.config.connect_timeout,
            look_for_keys=False,
            allow_agent=False,
        )

        transport = client.get_transport()
        remote_key = (
            transport.get_remote_server_key()
            if transport is not None
            else None
        )

        if remote_key is None:
            client.close()
            raise paramiko.SSHException(
                "No fue posible obtener la host key SSH remota."
            )

        digest = hashlib.sha256(remote_key.asbytes()).digest()
        actual = "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")
        self.host_key_fingerprint = actual

        if self.host_key_sha256:
            expected = self.host_key_sha256.strip()
            if not expected.startswith("SHA256:"):
                expected = "SHA256:" + expected.rstrip("=")

            if not hmac.compare_digest(expected, actual):
                client.close()
                raise paramiko.SSHException(
                    "La host key SSH no coincide con el pin del perfil. "
                    f"Esperada {expected}; recibida {actual}."
                )

            self.host_key_verified = True

        self.client = client

    def execute(
        self,
        command: str,
        timeout: Optional[int] = None,
    ) -> CommandResult:

        if self.client is None:
            raise RuntimeError(
                "La conexión SSH no está abierta."
            )

        command_timeout = (
            timeout
            if timeout is not None
            else self.config.command_timeout
        )

        _, stdout, stderr = (
            self.client.exec_command(
                command,
                timeout=command_timeout,
            )
        )

        stdout_text = stdout.read().decode(
            "utf-8",
            errors="replace",
        )

        stderr_text = stderr.read().decode(
            "utf-8",
            errors="replace",
        )

        exit_status = (
            stdout.channel.recv_exit_status()
        )

        return CommandResult(
            command=command,
            stdout=stdout_text,
            stderr=stderr_text,
            exit_status=exit_status,
        )

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        self.close()
