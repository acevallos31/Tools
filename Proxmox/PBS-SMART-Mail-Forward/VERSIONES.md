# Historial de versiones — PBS SMART Mail Forward (ARM64)

**Proyecto:** integración del monitoreo SMART del host Raspberry Pi 5 (Debian 12) con notificaciones SMTP de Proxmox Backup Server 4.2.8-1 en Docker hacia Gmail.

> Números de versión usados para **documentar las fases del proyecto**; no son versiones oficiales de Proxmox ni implican que se hayan creado GitHub Releases o tags. El código permanece en el PR [#4](https://github.com/acevallos31/Tools/pull/4), rama `feat/pbs-smart-mail-forward-arm64`, **sin merge a main**.

## Resumen de versiones y despliegue

| Versión del proyecto | Estado en Raspberry | Funcionalidad |
|---|---|---|
| **V1.0 — respaldo funcional** | Conservada para rollback; ya no es el helper activo | `smartd` → `smartd-runner` → `20pbs-smart` → adaptador → helper ARM64 oficial → PBS Notifications SMTP → Gmail; **sin cola ni reintentos persistentes**. |
| **V2.0-RC1 — despliegue parcial** | **Helper activo** en PBS desde paso 78; **cola y timer aún NO activados** | Helper ARM64 modificado para notificar fallos SMTP; cola SQLite persistente; retry/backoff y unidades systemd; pruebas aisladas y build ARM64 aprobados. |

**Fecha del registro:** 14 de octubre de 2026. **No confundir el helper V2 activo con la cola de reintentos V2, todavía pendiente de activar.**

## V1.0 — Versión operativa validada

### Alcance
- Raspberry Pi 5 ARM64 / Debian 12, PBS 4.2.8-1 contenedor Docker `pbs`.
- `smartd` vigila **2 dispositivos**: Micron 2400A NVMe y ADATA SU650 SATA por USB/SAT.
- Configuración del host: `/etc/smartd.conf` usa `smartd-runner` y `/etc/smartmontools/run.d/20pbs-smart`. El `10mail` original permanece en disco sin bit de ejecución.
- Scripts en host `/opt/pbs/smart-alerts/smartd-to-pbs` y `/opt/pbs/smart-alerts/pbs-smart-forward`.
- Helper instalado en el host `/opt/pbs/smart-alerts/bin/proxmox-mail-forward` y montado **solo lectura** en el contenedor `/usr/bin/proxmox-mail-forward` mediante `/opt/pbs/compose.yml`.
- PBS Notifications reutiliza el SMTP Gmail existente `smtp-pbs-alerts` y el matcher `pbs-important-alerts`, sin duplicar credenciales.
- `/mnt/pbs` en `/dev/sda1` ext4; contenedor `running/healthy`, política `unless-stopped`.

### Trazabilidad V1
- Workflow GitHub Actions correcto: [run 38623764393](https://github.com/acevallos31/Tools/actions/runs/38623764393).
- Binario ELF AArch64 V1: SHA256 `a2db207ddf30226eb0be4ad537fc0f563f65a925e54fea7549bc7d2fc468267c`.
- Tarball V1: SHA256 `3644a3bd6320087dcf2c3d8e93e753ac5d24b1f8a873567951c8bbed799a0601`.
- Pruebas sintéticas confirmadas por correo Gmail: desde el contenedor, desde el host, desde adaptador SMART y desde `smartd-runner`; auditoría final de volúmenes y servicio aprobada.
- Respaldo Compose de consolidación: `/opt/pbs/compose.yml.backup-20261014-144827`.
- **Limitación V1:** el helper oficial puede devolver salida exitosa incluso si un endpoint SMTP falla; no hay persistencia ni reenvío al fallar el envío.

## V2.0-RC1 — Cola persistente, build validado, pendiente de instalar

### Cambios funcionales
- Agrega `pbs-smart-queue`: SQLite en `/var/spool/pbs-smart-mail`, transacciones durables, cola acotada (500 mensajes / 16 MiB, 256 KiB por mensaje), acceso restringido a root.
- Alerta se encola primero y un worker manda correos cuando el destino está disponible; retrasos exponenciales de 60 s a 3600 s; lote máximo de 5 mensajes.
- `pbs-smart-queue.service` y `pbs-smart-queue.timer`: reintentos periódicos y al iniciar el sistema, cuando estén activados.
- `smartd-to-pbs-queued` sustituirá en el futuro la entrega directa por encolado (el notificador `20pbs-smart` sigue igual).
- Parche fuente reproducible `patch-checked-delivery.py` para que el helper propague errores de envío y de destino.
- Guardia de compatibilidad: el worker **no confirma ni borra** pendientes si no detecta `checked-delivery-v1` en el helper desplegado.

### Trazabilidad V2
- Código fuente base anclado:
  - `proxmox/proxmox-mail-forward` commit `9890c29a3d3da04262fe5564b2321be59928de5e`.
  - `proxmox/proxmox-rs` commit `89c1d597a9d15743049eadcb1add380573265904`.
- Workflow GitHub Actions: [run 38641594423](https://github.com/acevallos31/Tools/actions/runs/38641594423), **compilación ARM64 y pruebas aisladas correctas**.
- Artifact ID: `11931200973` (caduca según política GitHub).
- SHA256 ZIP del artifact V2: `43725ddc5dc54f992784aff7913d842899717e5f1aac595cdbcdcd6cd46b90c3`.
- SHA256 tar.gz V2: `c5c8de901f20e9f93ddb99407be598d26c0d2c66228b25034966a07ff0566b41`.
- SHA256 binario V2: `4664dab7916ba1955a398bf966fa8862aee0edc4411cb8010b1fbc7ef1b58e35`.
- **Paso 72 validado en Raspberry**: descarga a `~/pbs-smart-queue-staging/`, hashes de ZIP, paquete y binario con resultado `OK`; ejecutable aún sin instalar. Contenido del paquete incluye el parche y manifest `Cargo.lock`.

### Criterios de aceptación pendientes de V2
1. Comprobar `--pbs-smart-queue-protocol` y `ldd -r` del helper corregido **en ruta temporal** del contenedor PBS, sin reemplazar V1.
2. Hacer copia del ejecutable V1 e instalar V2 solo en ventana aprobada sin tareas PBS activas; confirmar `running/healthy`, datastore y test SMTP sintético recibido.
3. Instalar cola y unidades en estado controlado; pruebas de fallo/transitorio sin interrumpir PBS real y verificación de preservación del mensaje pendiente.
4. Activar adaptador encolado y timer; prueba extremo a extremo `smartd-runner` → cola → Gmail; inspeccionar `pending=0`.
5. Actualizar documentación tras resultados reales, conservar pasos de rollback.

### Compatibilidad y limitaciones
- V1 y V2 reutilizan el mismo SMTP y matcher existentes en PBS; la cola V2 se aloja en el **host**, no en el datastore.
- Un acuse positivo confirma que un endpoint aceptó el mensaje, **no** garantiza que Gmail haya depositado finalmente el correo en la bandeja.
- Semántica de reintentos **al menos una vez**: si el envío se acepta y el proceso cae antes de confirmar SQLite, puede producirse un mensaje duplicado.
- Si la cola llena su capacidad, devuelve error y no elimina alertas existentes; es necesario monitorear espacio y pendientes.
- No publicar credenciales, datos de `notifications-priv.cfg` ni correos reales almacenados en el spool.

## Recuperación y rollback

- **Mientras V2 no esté desplegada**: continuar con V1, no cambiar rutas activas ni servicios.
- **Tras instalar V2**: conservar el ejecutable V1 y el `smartd-to-pbs` anterior. En una recuperación, suspender `pbs-smart-queue.timer`, impedir nuevos envíos desde worker, restaurar el adaptador y helper V1 siguiendo ventana aprobada (recrear contenedor solo si imprescindible).
- **Nunca borrar la base SQLite con mensajes pendientes** al volver a V1: los mensajes que quedaron en V2 no se entregarán por la vía directa. Drenarlos con helper V2 corregido antes de retirar el spool.
- Conservación de logs locales `smartd`, PBS y datastore en ambas versiones.

Ver procedimientos técnicos en [OPERACION-Y-RECUPERACION.md](./OPERACION-Y-RECUPERACION.md) (V1) y [QUEUE-Y-REINTENTOS.md](./QUEUE-Y-REINTENTOS.md) (V2).

### Paso 73 — Prueba temporal de compatibilidad V2 en PBS (14-10-2026)

Evidencia entregada desde Raspberry Pi: `docker cp` del nuevo helper a `pbs:/tmp/proxmox-mail-forward-v2`, SHA256 `4664dab7916ba1955a398bf966fa8862aee0edc4411cb8010b1fbc7ef1b58e35` correcto, `--pbs-smart-queue-protocol` respondió `checked-delivery-v1`, `ldd -r` resolvió todas las dependencias ARM64 y `docker inspect pbs` reportó `running/healthy`. **No instalado** en el montaje `/usr/bin/proxmox-mail-forward`, V1 sigue activa. Pendiente prueba SMTP sintética con este ejecutable V2 y verificación de errores antes de cambiar a V2.

### Paso 74 — Prueba SMTP sintética V2 recibida (14-10-2026)

Con el helper corregido ubicado **temporalmente** en `pbs:/tmp/proxmox-mail-forward-v2` se envió un mensaje MIME sintético con asunto `[PRUEBA V2] SMART Queue - Raspberry Pi 5`. El usuario confirmó mediante captura la **recepción en Gmail** desde el remitente `Proxmox Backup Server - pbs` y contenido que indica `Version: V2.0-RC1` y `Protocolo: checked-delivery-v1`. Esto prueba aceptación y entrega de este mensaje de ensayo por la ruta PBS SMTP existente. **No se reemplazó el helper V1 del montaje**, no se activó aún la cola local, y todavía falta probar el caso de fallo con salida no cero, la integración de la cola y el rollback.

### Paso 75 — Prueba negativa de entrada V2 (14-10-2026)

Se ejecutó `docker exec -i pbs /tmp/proxmox-mail-forward-v2 </dev/null` desde la Raspberry. El binario informó `could not forward mail: could not parse forwarded email` y terminó con **código de salida 1**. PBS permaneció `running/healthy`. Esto verifica el rechazo y señalización de **entrada inválida**, pero **no** constituye aún una prueba de fallo SMTP o del transporte ni de recuperación de la cola. El helper V1 instalado y el camino actual de notificación permanecen sin cambios.

### Paso 76 — Dos binarios respaldados por versión (14-10-2026)

Comprobación real enviada desde Raspberry:
- Binario V1 original validado por SHA256 y copiado a `/opt/pbs/smart-alerts/versions/V1.0/proxmox-mail-forward` con `root:root 0755`; SHA256 `a2db207ddf30226eb0be4ad537fc0f563f65a925e54fea7549bc7d2fc468267c`.
- Binario V2.0-RC1 descargado validado por SHA256 y copiado a `/opt/pbs/smart-alerts/versions/V2.0-RC1/proxmox-mail-forward` con `root:root 0755`; SHA256 `4664dab7916ba1955a398bf966fa8862aee0edc4411cb8010b1fbc7ef1b58e35`.
- Se confirmó que **el ejecutable activo en `pbs:/usr/bin/proxmox-mail-forward` es aún V1**, con el hash `a2db207d...`, y que PBS sigue `running/healthy`.
- **Aún no** se ha cambiado el montaje Docker Compose, reiniciado PBS, ni activado la cola.
- Plan de despliegue reversible: cuando llegue la ventana aprobada, cambiar **solo** el `source` del bind mount en `/opt/pbs/compose.yml` desde `/opt/pbs/smart-alerts/bin/proxmox-mail-forward` a `/opt/pbs/smart-alerts/versions/V2.0-RC1/proxmox-mail-forward`, verificar la equivalencia del resto de la configuración y recrear PBS con tareas inactivas. Para rollback, volver al origen anterior sin alterar ninguno de los dos binarios versionados.

### Paso 78 — V2.0-RC1 activada como helper, cola todavía pendiente (14-10-2026)

Se confirmó en la salida real de Raspberry que `docker compose -p pbs -f compose.yml up -d --no-deps --no-build --pull never --wait --wait-timeout 120 pbs` recreó el contenedor correctamente después de comprobar `/mnt/pbs` y ausencia de tareas activas (`[]`). El contenedor volvió a `running/healthy` y el montaje fue:
- Origen: `/opt/pbs/smart-alerts/versions/V2.0-RC1/proxmox-mail-forward`.
- Destino: `/usr/bin/proxmox-mail-forward` (**solo lectura**).
- SHA256 efectivo dentro del contenedor: `4664dab7916ba1955a398bf966fa8862aee0edc4411cb8010b1fbc7ef1b58e35`.
- Protocolo: `checked-delivery-v1`.
- Datastore `/mnt/pbs` sigue en `/dev/sda1`, ext4 `rw,noatime`.

**Estado exacto:** V2 helper **desplegado**, pero el adaptador SMART del host sigue enviando inmediatamente (la cola SQLite y su timer **todavía no están instalados ni activos**). No declarar desplegada la funcionalidad de reintentos hasta verificar pruebas de staging, instalación y entrega.

### Paso 79 — Pruebas aisladas de cola SQLite realizadas en Raspberry (14-10-2026)

El usuario descargó `pbs-smart-queue` y `tests/test_queue.py` de la rama versionada (commit `15dd6b17cb2f1b86f3b311c1411ab4a6fe32f1c4`) a `~/pbs-smart-queue-staging/queue-code/`. Validó sintaxis Python y ejecutó `python3 -m unittest discover -s queue-code/tests -v`: **5 pruebas superadas en 0.087 s** (retención ante error y recuperación posterior, límite de mensaje, límite de capacidad sin eliminar pendientes, eliminación tras acuse y rechazo del helper no verificado). Los registros `pending ... retry_in=60s` son salidas deliberadas de simulaciones mediante transporte ficticio, no errores reales de producción. PBS continuó `running/healthy`. **Cola, spool de producción y timer aún NO instalados ni activados**. El helper V2 corregido ya está activo.

### Paso 80 — Programa SQLite instalado sin activar timer (14-10-2026)

Confirmado por salida de Raspberry: desde `~/pbs-smart-queue-staging/queue-code/pbs-smart-queue` se instaló `/opt/pbs/smart-alerts/pbs-smart-queue` como `root:root` modo `0750`; `cmp` coincidió. Se inicializó `/var/spool/pbs-smart-mail` con `root:root` modo `0700`, y `sudo /opt/pbs/smart-alerts/pbs-smart-queue status` mostró `pending=0 bytes=0 previously_failed=0`. Contenedor `pbs` siguió `running/healthy`. **No se instalaron ni activaron las unidades systemd de retry, ni se cambió el adaptador SMART a encolado.** La versión V2 del helper sí está operativa desde el Paso 78.

### Paso 81.1 — Validación de unidades systemd como root (14-10-2026)

La Raspberry descargó al staging `pbs-smart-queue.service`, `pbs-smart-queue.timer` y `smartd-to-pbs-queued`. La primera verificación, ejecutada como usuario `acevallos`, informó `Command /opt/pbs/smart-alerts/pbs-smart-queue is not executable: Permission denied`, porque el ejecutable está protegido como `root:root 0750`. **No se relajaron los permisos**. Al repetir con `sudo systemd-analyze verify` ambas unidades se validaron: `OK: unidades systemd validas`. `sh -n` validó el adaptador; el contador persistente siguió `pending=0 bytes=0 previously_failed=0`, y PBS siguió `running/healthy`. **Unidades todavía no instaladas ni habilitadas, adaptador de producción sin sustituir.**
