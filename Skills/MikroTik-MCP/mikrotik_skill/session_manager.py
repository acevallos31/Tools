from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

from .client import MikroTikClient
from .profiles import DeviceProfile, load_password, load_profile


@dataclass
class ManagedSession:
    """
    Representa una conexión SSH reutilizable hacia un dispositivo MikroTik.
    """

    profile: DeviceProfile
    client: MikroTikClient
    created_at: float
    last_used_at: float
    reuse_count: int = 0


class MikroTikSessionManager:
    """
    Administra conexiones SSH reutilizables por perfil MikroTik.

    Objetivos:
    - Evitar una nueva autenticación SSH en cada llamada MCP.
    - Cachear temporalmente la contraseña descifrada mientras vive el proceso.
    - Verificar la conexión antes de reutilizarla.
    - Reconectar automáticamente si la sesión murió.
    - Mantener una sesión independiente por dispositivo.
    - Exponer telemetría segura sobre reutilización de sesiones.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, ManagedSession] = {}
        self._password_cache: Dict[str, str] = {}
        self._lock = threading.RLock()

    def _get_password(self, device: str) -> str:
        """
        Obtiene la contraseña del perfil.

        La contraseña se descifra mediante DPAPI únicamente la primera vez
        durante la vida de este SessionManager.
        """

        password = self._password_cache.get(device)

        if password:
            return password

        password = load_password(device)

        if not password:
            raise RuntimeError(
                f"No fue posible obtener la contraseña del perfil "
                f"{device!r}."
            )

        self._password_cache[device] = password

        return password

    def _create_client(
        self,
        profile: DeviceProfile,
        password: str,
    ) -> MikroTikClient:
        """
        Crea y conecta un nuevo cliente SSH.
        """

        client = MikroTikClient(
            host=profile.host,
            port=profile.port,
            username=profile.username,
            password=password,
            host_key_sha256=profile.host_key_sha256,
        )

        client.connect()

        return client

    @staticmethod
    def _client_is_alive(
        client: MikroTikClient,
    ) -> bool:
        """
        Comprueba el transporte SSH de Paramiko sin ejecutar
        un comando RouterOS adicional.
        """

        ssh_client = client.client

        if ssh_client is None:
            return False

        transport = ssh_client.get_transport()

        if transport is None:
            return False

        return (
            transport.is_active()
            and transport.is_authenticated()
        )

    def get_client(
        self,
        device: str,
    ) -> MikroTikClient:
        """
        Devuelve una conexión SSH válida para el perfil solicitado.

        Si existe una sesión activa, la reutiliza.
        Si la conexión murió, la reemplaza automáticamente.
        """

        with self._lock:
            session = self._sessions.get(device)

            if session is not None:
                if self._client_is_alive(session.client):
                    session.last_used_at = time.monotonic()
                    session.reuse_count += 1

                    return session.client

                try:
                    session.client.close()
                except Exception:
                    pass

                self._sessions.pop(
                    device,
                    None,
                )

            profile = load_profile(device)
            password = self._get_password(device)

            client = self._create_client(
                profile=profile,
                password=password,
            )

            now = time.monotonic()

            self._sessions[device] = ManagedSession(
                profile=profile,
                client=client,
                created_at=now,
                last_used_at=now,
                reuse_count=0,
            )

            return client

    def reconnect(
        self,
        device: str,
    ) -> MikroTikClient:
        """
        Fuerza la reconstrucción de la conexión de un dispositivo.
        """

        with self._lock:
            self.close(device)

            return self.get_client(device)

    def close(
        self,
        device: str,
    ) -> None:
        """
        Cierra la sesión SSH de un dispositivo específico.

        La contraseña permanece cacheada hasta clear_password_cache()
        o close_all().
        """

        with self._lock:
            session = self._sessions.pop(
                device,
                None,
            )

            if session is not None:
                try:
                    session.client.close()
                except Exception:
                    pass

    def close_all(self) -> None:
        """
        Cierra todas las conexiones y elimina las contraseñas
        cacheadas en memoria.
        """

        with self._lock:
            sessions = list(
                self._sessions.values()
            )

            self._sessions.clear()

            for session in sessions:
                try:
                    session.client.close()
                except Exception:
                    pass

            self._password_cache.clear()

    def clear_password_cache(
        self,
        device: Optional[str] = None,
    ) -> None:
        """
        Elimina credenciales cacheadas.

        Si device es None, elimina todas.
        """

        with self._lock:
            if device is None:
                self._password_cache.clear()
                return

            self._password_cache.pop(
                device,
                None,
            )

    def telemetry(
        self,
        device: str,
    ) -> dict:
        """
        Devuelve telemetría segura de la sesión.

        No expone contraseña, host ni nombre de usuario.

        reused indica si la sesión actual ya fue reutilizada
        al menos una vez desde que fue creada.
        """

        with self._lock:
            session = self._sessions.get(device)

            if session is None:
                return {
                    "connected": False,
                    "reused": False,
                    "reuse_count": 0,
                    "age_seconds": 0.0,
                    "idle_seconds": 0.0,
                    "host_key_verified": False,
                    "host_key_fingerprint": None,
                }

            now = time.monotonic()

            return {
                "connected": self._client_is_alive(
                    session.client
                ),
                "reused": session.reuse_count > 0,
                "reuse_count": session.reuse_count,
                "age_seconds": round(
                    now - session.created_at,
                    2,
                ),
                "idle_seconds": round(
                    now - session.last_used_at,
                    2,
                ),
                "host_key_verified": session.client.host_key_verified,
                "host_key_fingerprint": session.client.host_key_fingerprint,
            }

    def status(self) -> dict:
        """
        Devuelve información operativa del SessionManager
        sin exponer credenciales.
        """

        with self._lock:
            devices = {}

            now = time.monotonic()

            for name, session in self._sessions.items():
                devices[name] = {
                    "host": session.profile.host,
                    "port": session.profile.port,
                    "username": session.profile.username,
                    "connected": self._client_is_alive(
                        session.client
                    ),
                    "age_seconds": round(
                        now - session.created_at,
                        2,
                    ),
                    "idle_seconds": round(
                        now - session.last_used_at,
                        2,
                    ),
                    "reuse_count": session.reuse_count,
                }

            return {
                "sessions": devices,
                "session_count": len(devices),
                "cached_passwords": len(
                    self._password_cache
                ),
            }


SESSION_MANAGER = MikroTikSessionManager()
