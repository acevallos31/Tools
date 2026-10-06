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


def _wait_for_ssh_banner(host: str, port: int) -> None:
    for _ in range(60):
        try:
            with socket.create_connection((host, port), timeout=5) as sock:
                sock.settimeout(5)
                if sock.recv(64).startswith(b"SSH-"):
                    return
        except Exception:
            pass
        time.sleep(5)
    raise RuntimeError("RouterOS sandbox did not expose an SSH banner in time.")


def _set_initial_password(host: str, port: int, password: str) -> None:
    # This is the only write in the sandbox fixture. Tests themselves are read-only.
    for current in ("", password):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=host,
                port=port,
                username="admin",
                password=current,
                timeout=20,
                look_for_keys=False,
                allow_agent=False,
            )
            if current == "":
                _, stdout, stderr = ssh.exec_command(
                    f"/user set 0 password={password}"
                )
                reply = (stdout.read() + stderr.read()).decode(
                    errors="replace"
                ).strip()
                ssh.close()
                if reply:
                    continue
                time.sleep(2)
            else:
                ssh.close()
            return
        except Exception:
            continue
    raise RuntimeError("Could not initialize RouterOS sandbox password.")


@pytest.fixture(scope="module")
def routeros_sandbox():
    if not _docker_available():
        pytest.skip("Docker is not available.")

    kwargs = {
        "privileged": True,
        "cap_add": ["NET_ADMIN", "NET_RAW"],
    }
    if os.name != "nt":
        kwargs["devices"] = ["/dev/net/tun:/dev/net/tun"]

    container = (
        DockerContainer("evilfreelancer/docker-routeros:latest")
        .with_exposed_ports(22)
        .with_kwargs(**kwargs)
    )

    try:
        container.start()
        host = container.get_container_host_ip()
        port = int(container.get_exposed_port(22))
        password = "mikrotik-sandbox-123"
        _wait_for_ssh_banner(host, port)
        _set_initial_password(host, port, password)

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


def test_read_only_health_inventory(routeros_sandbox) -> None:
    client = _client(routeros_sandbox)
    try:
        raw = collect_inventory_sections(
            client,
            ("identity", "resources", "routerboard"),
        )
        parsed = parse_inventory(raw)

        assert parsed["device"]["identity"]
        assert parsed["device"]["routeros"]
        assert isinstance(parsed["health"]["cpu_load_percent"], int)
    finally:
        client.close()


def test_cpu_sampler_collects_real_window(routeros_sandbox) -> None:
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
