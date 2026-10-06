from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Optional

from .app_paths import profiles_dir, secrets_dir


PROFILE_NAME_ALLOWED = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789_-"
)


@dataclass(frozen=True)
class DeviceProfile:
    name: str
    host: str
    port: int
    username: str
    default_interface: str
    host_key_sha256: Optional[str] = None


def _validate_profile_name(name: str) -> str:
    name = name.strip()

    if not name:
        raise ValueError(
            "El nombre del perfil está vacío."
        )

    if any(char not in PROFILE_NAME_ALLOWED for char in name):
        raise ValueError(
            f"Nombre de perfil no permitido: {name!r}"
        )

    return name


def load_profile(name: str) -> DeviceProfile:
    name = _validate_profile_name(name)

    path = (
        profiles_dir()
        / f"{name}.json"
    )

    if not path.is_file():
        raise FileNotFoundError(
            f"No existe el perfil {name!r}."
        )

    data = json.loads(
        path.read_text(encoding="utf-8-sig")
    )

    required = {
        "name",
        "host",
        "port",
        "username",
        "default_interface",
    }

    missing = required - data.keys()

    if missing:
        raise ValueError(
            f"Perfil incompleto. Faltan: "
            f"{sorted(missing)}"
        )

    if data["name"] != name:
        raise ValueError(
            "El nombre interno del perfil "
            "no coincide con el archivo."
        )

    port = int(data["port"])

    if not 1 <= port <= 65535:
        raise ValueError(
            f"Puerto inválido: {port}"
        )

    host_key_sha256 = data.get("host_key_sha256")
    if host_key_sha256 is not None:
        host_key_sha256 = str(host_key_sha256).strip()
        if not host_key_sha256:
            host_key_sha256 = None

    return DeviceProfile(
        name=name,
        host=str(data["host"]),
        port=port,
        username=str(data["username"]),
        default_interface=str(
            data["default_interface"]
        ),
        host_key_sha256=host_key_sha256,
    )



def list_profiles() -> list[DeviceProfile]:
    """List valid local device profiles without reading or exposing secrets."""

    directory = profiles_dir()
    if not directory.is_dir():
        return []

    profiles: list[DeviceProfile] = []
    for path in sorted(directory.glob("*.json")):
        try:
            profiles.append(
                load_profile(path.stem)
            )
        except Exception:
            # A malformed profile should not prevent discovery of the others.
            continue

    return profiles

def load_password(name: str) -> str:
    name = _validate_profile_name(name)

    path = (
        secrets_dir()
        / f"{name}-password.dat"
    )

    if not path.is_file():
        raise FileNotFoundError(
            f"No existe el secreto del perfil {name!r}."
        )

    ps_path = str(path).replace("'", "''")

    script = f"""
$encrypted = Get-Content -Raw '{ps_path}'
$secure = $encrypted | ConvertTo-SecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)

try {{
    [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
}}
finally {{
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}}
"""

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "No fue posible descifrar el secreto "
            f"del perfil {name!r}: "
            f"{result.stderr.strip()}"
        )

    password = result.stdout.strip()

    if not password:
        raise RuntimeError(
            f"El secreto del perfil {name!r} está vacío."
        )

    return password
