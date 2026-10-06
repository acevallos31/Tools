import base64
import hashlib
import hmac
from dataclasses import dataclass
from typing import Optional

import paramiko

from .config import CONFIG, MikroTikConfig


def ssh_key_fingerprint_sha256(key: paramiko.PKey) -> str:
    """Return an OpenSSH-style SHA256 host-key fingerprint."""

    digest = hashlib.sha256(key.asbytes()).digest()
    encoded = base64.b64encode(digest).decode("ascii").rstrip("=")
    return f"SHA256:{encoded}"


def normalize_fingerprint(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("El fingerprint SSH está vacío.")
    if value.startswith("SHA256:"):
        return "SHA256:" + value[len("SHA256:"):].rstrip("=")
    return "SHA256:" + value.rstrip("=")


class SSHHostKeyMismatch(paramiko.SSHException):
    def __init__(self, hostname: str, expected: str, actual: str) -> None:
        self.hostname = hostname
        self.expected = expected
        self.actual = actual
        super().__init__(
            "La host key SSH no coincide con el pin configurado."
        )


class PinnedHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    """Verify a SHA256 host-key pin during SSH key exchange, before auth."""

    def __init__(self, expected_fingerprint: str) -> None:
        self.expected = normalize_fingerprint(expected_fingerprint)

    def missing_host_key(
        self,
        client: paramiko.SSHClient,
        hostname: str,
        key: paramiko.PKey,
    ) -> None:
        del client
        actual = ssh_key_fingerprint_sha256(key)

        if not hmac.compare_digest(self.expected, actual):
            raise SSHHostKeyMismatch(
                hostname=hostname,
                expected=self.expected,
                actual=actual,
            )


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

        if self.host_key_sha256:
            # Deliberately do not load known_hosts here. The explicit pin must
            # be the authority and is checked during key exchange before the
            # password is sent.
            client.set_missing_host_key_policy(
                PinnedHostKeyPolicy(
                    self.host_key_sha256
                )
            )
        else:
            # Lab compatibility mode. Existing system known_hosts entries are
            # still checked; an unknown host is accepted. Production profiles
            # should set host_key_sha256.
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

        transport.set_keepalive(
            self.config.keepalive_interval
        )

        actual = ssh_key_fingerprint_sha256(
            remote_key
        )
        self.host_key_fingerprint = actual
        self.host_key_verified = bool(
            self.host_key_sha256
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
