from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from typing import Optional

from .skill import ALLOWED_OPERATIONS, run_skill


def get_password() -> str:
    """
    Obtiene la contraseña SSH para el modo legacy.

    Prioridad:
    1. Variable de entorno MIKROTIK_PASSWORD
    2. Solicitud interactiva

    Cuando se utiliza --device, esta función no se ejecuta,
    porque la contraseña se obtiene desde el secreto DPAPI
    asociado al perfil.

    Nunca imprime la contraseña.
    """

    password = os.getenv("MIKROTIK_PASSWORD")

    if password:
        return password

    if not sys.stdin.isatty():
        raise RuntimeError(
            "MIKROTIK_PASSWORD no está definida y "
            "la ejecución no es interactiva."
        )

    return getpass.getpass(
        "Contraseña SSH MikroTik: "
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mikrotik-skill",
        description=(
            "Skill seguro de análisis MikroTik "
            "para Hermes Agent."
        ),
    )

    parser.add_argument(
        "operation",
        choices=sorted(ALLOWED_OPERATIONS),
        help="Operación permitida.",
    )

    parser.add_argument(
        "--device",
        default=None,
        help=(
            "Perfil de dispositivo configurado "
            "en MikroTikSkill."
        ),
    )

    parser.add_argument(
        "--interface",
        default=None,
        help=(
            "Interfaz RouterOS para análisis Torch. "
            "Si se omite y se utiliza --device, "
            "se usa la interfaz predeterminada del perfil."
        ),
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Duración de Torch entre 1 y 30 segundos.",
    )

    parser.add_argument(
        "--compact",
        action="store_true",
        help="Devuelve JSON compacto.",
    )

    return parser


def main(
    argv: Optional[list[str]] = None,
) -> int:
    parser = build_parser()

    args = parser.parse_args(argv)

    try:
        # Con --device la contraseña se recupera
        # internamente desde el secreto DPAPI.
        #
        # Sin --device conservamos temporalmente
        # el mecanismo anterior.
        password = (
            None
            if args.device
            else get_password()
        )

        result = run_skill(
            operation=args.operation,
            password=password,
            interface=args.interface,
            duration=args.duration,
            device=args.device,
        )

        indent = (
            None
            if args.compact
            else 2
        )

        print(
            json.dumps(
                result,
                indent=indent,
                ensure_ascii=False,
            )
        )

        return (
            0
            if result.get("status") == "ok"
            else 1
        )

    except Exception as exc:
        error = {
            "status": "error",
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }

        print(
            json.dumps(
                error,
                indent=2,
                ensure_ascii=False,
            )
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())