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

        # Temporal para el laboratorio.
        # Luego usaremos known_hosts + SSH key.
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