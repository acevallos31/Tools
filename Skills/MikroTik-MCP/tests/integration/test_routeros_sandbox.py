from __future__ import annotations

import os
import socket
import subprocess
import time

import paramiko
import pytest

pytest.importorskip("testcontainers.core.container")
from testcontainers.core.container import DockerContainer

from mikrotik_skill.client import MikroTikClient
from mikrotik_skill.cpu_sampling import sample_cpu
from mikrotik_skill.interface_sampling import sample_interface_traffic
from mikrotik_skill.inventory import collect_inventory_sections
from mikrotik_skill.inventory_parser import parse_inventory


pytestmark = pytest.mark.integration


def _docker_available() -> bool:
    try:
        return subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            check=False,
        ).returncode == 0
    except Exception:
        return False


def _wait_for_ssh_banner(
    host: str,
    port: int,
    max_attempts: int = 60,
    delay: int = 5,
) -> None:
    """Wait for RouterOS itself, not just QEMU hostfwd accepting TCP."""

    for _ in range(max_attempts):
        try:
            with socket.create_connection((host, port), timeout=5) as sock:
                sock.settimeout(5)
                if sock.recv(64).startswith(b"SSH-"):
                    return
        except Exception:
            pass
        time.sleep(delay)

    raise RuntimeError(
        "RouterOS sandbox did not expose an SSH banner in time."
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
    # Fresh evilfreelancer/docker-routeros images boot with an empty admin
    # password. Set it once in the isolated fixture, then verify before tests.
    if _try_set_initial_password(host, port, password):
        if _verify_ssh_auth(host, port, password):
            return

    # Also supports an already-initialized/reused sandbox.
    if _verify_ssh_auth(host, port, password):
        return

    raise RuntimeError(
        "Unable to authenticate to RouterOS sandbox over SSH."
    )


@pytest.fixture(scope="module")
def routeros_sandbox():
    if not _docker_available():
        pytest.skip("Docker is not available.")

    kwargs = {
        "privileged": True,
        "cap_add": ["NET_ADMIN", "NET_RAW"],
    }

    if os.name != "nt":
        kwargs["devices"] = [
            "/dev/net/tun:/dev/net/tun"
        ]

    container = (
        DockerContainer(
            "evilfreelancer/docker-routeros:latest"
        )
        .with_exposed_ports(22)
        .with_kwargs(**kwargs)
    )

    try:
        container.start()
        host = container.get_container_host_ip()
        port = int(
            container.get_exposed_port(22)
        )
        password = "mikrotik-sandbox-123"

        _wait_for_ssh_banner(host, port)
        _ensure_password(host, port, password)

        yield {
            "host": host,
            "port": port,
            "password": password,
        }
    finally:
        try:
            container.stop()
        except Exception:
            pass


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
