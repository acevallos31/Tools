from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MikroTikConfig:
    # Valores genéricos.
    # Los datos específicos de cada dispositivo deben venir
    # de los perfiles locales administrados por profiles.py.
    host: str = ""
    port: int = 22
    username: str = ""

    connect_timeout: int = 10
    command_timeout: int = 30

    default_interface: str = "ether1"
    torch_duration: int = 5

    output_dir: Path = Path("output")
    raw_dir: Path = Path("output/raw")
    reports_dir: Path = Path("output/reports")


CONFIG = MikroTikConfig()
