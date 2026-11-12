from __future__ import annotations

import os
from pathlib import Path


def app_home() -> Path:
    """Return the per-user runtime directory without depending on cwd."""

    override = os.getenv("MIKROTIK_SKILL_HOME")
    if override:
        return Path(override).expanduser()

    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "MikroTikSkill"

    return Path.home() / ".mikrotik-skill"


def profiles_dir() -> Path:
    return app_home() / "profiles"


def secrets_dir() -> Path:
    return app_home() / "secrets"


def logs_dir() -> Path:
    return app_home() / "logs"


def captures_dir() -> Path:
    return app_home() / "captures"
