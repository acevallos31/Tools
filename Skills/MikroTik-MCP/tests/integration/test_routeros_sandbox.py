from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path

import paramiko
import pytest

from mikrotik_skill.client import MikroTikClient
from mikrotik_skill.cpu_sampling import sample_cpu
from mikrotik_skill.interface_sampling import sample_interface_traffic
from mikrotik_skill.inventory import collect_inventory_sections
from mikrotik_skill.inventory_parser import parse_inventory


pytestmark = pytest.mark.integration

COMPOSE_FILE = Path(__file__).with_name("docker-compose.routeros.yml")
COMPOSE_PROJECT = f"mikrotik-mcp-routeros-{os.getpid()}"


def _run(
    command: list[str],
    *,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=check,
    )


def _compose(
    *args: str,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            "docker",
            "compose",
            "-p",
            COMPOSE_PROJECT,
            "-f",
            str(COMPOSE_FILE),
            *args,
        ],
        check=check,
    )


def _docker_available() -> bool:
    try:
        return (
            _run(["docker", "info"]).returncode == 0
            and _run(["docker", "compose", "version"]).returncode == 0
        )
    except Exception:
        return False


def _compose_port() -> int:
    result = _compose("port", "routeros", "22")
    if result.returncode != 0:
        raise RuntimeError(
            "No se pudo obtener el puerto SSH publicado por Docker Compose: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )

    line = result.stdout.strip().splitlines()[-1]
    try:
        return int(line.rsplit(":", 1)[1])
    except (IndexError, ValueError) as exc:
        raise RuntimeError(
            f"Formato inesperado de 'docker compose port': {line!r}"
        ) from exc


def _compose_diagnostics() -> str:
    chunks: list[str] = []

    ps = _compose("ps", "-a")
    chunks.append(
        "=== docker compose ps -a ===\n"
        + (ps.stdout or ps.stderr or "(sin salida)")
    )

    logs = _compose(
        "logs",
        "--no-color",
        "--tail",
        "250",
        "routeros",
    )
    chunks.append(
        "=== docker compose logs routeros ===\n"
        + (logs.stdout or logs.stderr or "(sin salida)")
    )

    cid = _compose("ps", "-q", "routeros")
    container_id = cid.stdout.strip()
    if container_id:
        inspect = _run(
            [
                "docker",
                "inspect",
                "--format",
                (
                    "status={{.State.Status}} "
                    "exit={{.State.ExitCode}} "
                    "error={{.State.Error}} "
                    "networks={{json .NetworkSettings.Networks}}"
                ),
                container_id,
            ]
        )
        chunks.append(
            "=== docker inspect ===\n"
            + (inspect.stdout or inspect.stderr or "(sin salida)")
        )

    return "\n\n".join(chunks)


def _wait_for_ssh_banner(
    host: str,
    port: int,
    max_wait_seconds: int = 180,
) -> None:
    """Wait for RouterOS itself, not only for Docker port publication."""

    deadline = time.monotonic() + max_wait_seconds
    last_error = "sin detalle"

    while time.monotonic() < deadline:
        try:
            with socket.create_connection(
                (host, port),
                timeout=2,
            ) as sock:
                sock.settimeout(2)
                banner = sock.recv(64)
                if banner.startswith(b"SSH-"):
                    return
                last_error = f"banner inesperado: {banner!r}"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"

        time.sleep(2)

    raise RuntimeError(
        "RouterOS sandbox no expuso un banner SSH dentro de "
        f"{max_wait_seconds}s. Último estado: {last_error}"
    )


def _try_set_initial_password(
    host: str,
    port: int,
    password: str,
) -> bool:
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(
            paramiko.AutoAddPolicy()
        )
        ssh.connect(
            hostname=host,
            port=port,
            username="admin",
            password="",
            timeout=20,
            look_for_keys=False,
            allow_agent=False,
        )
        _, stdout, stderr = ssh.exec_command(
            f"/user set 0 password={password}"
        )
        reply = (
            stdout.read() + stderr.read()
        ).decode(errors="replace").strip()
        ssh.close()
        return not reply
    except Exception:
        return False


def _verify_ssh_auth(
    host: str,
    port: int,
    password: str,
    max_attempts: int = 6,
    delay: int = 5,
) -> bool:
    for _ in range(max_attempts):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(
                paramiko.AutoAddPolicy()
            )
            ssh.connect(
                hostname=host,
                port=port,
                username="admin",
                password=password,
                timeout=10,
                look_for_keys=False,
                allow_agent=False,
            )
            _, stdout, _ = ssh.exec_command(
                "/system identity print"
            )
            output = stdout.read().decode(
                errors="replace"
            )
            ssh.close()

            if output:
                return True
        except Exception:
            pass

        time.sleep(delay)

    return False


def _ensure_password(
    host: str,
    port: int,
    password: str,
) -> None:
    # Fresh CHR starts with admin and an empty password. Set a temporary
    # password only inside this disposable sandbox, then verify SSH.
    if _try_set_initial_password(host, port, password):
        if _verify_ssh_auth(host, port, password):
            return

    # Supports an already-initialized/reused local sandbox as well.
    if _verify_ssh_auth(host, port, password):
        return

    raise RuntimeError(
        "No se pudo autenticar al RouterOS sandbox por SSH."
    )


@pytest.fixture(scope="module")
def routeros_sandbox():
    if not _docker_available():
        pytest.skip("Docker + Docker Compose no están disponibles.")

    up = _compose("up", "-d", "routeros")
    if up.returncode != 0:
        pytest.fail(
            "No se pudo iniciar RouterOS con Docker Compose.\n\n"
            + (up.stderr or up.stdout)
            + "\n\n"
            + _compose_diagnostics()
        )

    try:
        host = "127.0.0.1"
        port = _compose_port()
        password = "mikrotik-sandbox-123"

        try:
            _wait_for_ssh_banner(host, port)
            _ensure_password(host, port, password)
        except Exception as exc:
            pytest.fail(
                f"{exc}\n\n{_compose_diagnostics()}"
            )

        yield {
            "host": host,
            "port": port,
            "password": password,
        }
    finally:
        _compose(
            "down",
            "-v",
            "--remove-orphans",
        )


def _client(sandbox) -> MikroTikClient:
    client = MikroTikClient(
        host=sandbox["host"],
        port=sandbox["port"],
        username="admin",
        password=sandbox["password"],
    )
    client.connect()
    return client


def test_read_only_health_inventory(
    routeros_sandbox,
) -> None:
    client = _client(routeros_sandbox)
    try:
        raw = collect_inventory_sections(
            client,
            ("identity", "resources", "routerboard"),
        )
        parsed = parse_inventory(raw)

        assert parsed["device"]["identity"]
        assert parsed["device"]["routeros"]
        assert isinstance(
            parsed["health"]["cpu_load_percent"],
            int,
        )
    finally:
        client.close()


def test_cpu_sampler_collects_real_window(
    routeros_sandbox,
) -> None:
    client = _client(routeros_sandbox)
    try:
        result = sample_cpu(
            client,
            duration=5,
            interval=1,
        )

        assert result["actual_duration_seconds"] >= 5
        assert result["sample_count"] >= 5
        assert all(
            0 <= row["cpu_percent"] <= 100
            for row in result["readings"]
        )
    finally:
        client.close()


def test_interface_sampler_uses_real_monitor_traffic(
    routeros_sandbox,
) -> None:
    client = _client(routeros_sandbox)
    try:
        result = sample_interface_traffic(
            client,
            interface="ether1",
            duration=5,
            interval=1,
        )

        assert result["interface"] == "ether1"
        assert result["actual_duration_seconds"] >= 5
        assert result["sample_count"] >= 5
        assert all(
            row["rx_bps"] >= 0 and row["tx_bps"] >= 0
            for row in result["readings"]
        )
    finally:
        client.close()
