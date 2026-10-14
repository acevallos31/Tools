# Historial de versiones — PBS SMART Mail Forward (ARM64)

**Proyecto:** integración del monitoreo SMART del host Raspberry Pi 5 (Debian 12) con notificaciones SMTP de Proxmox Backup Server 4.2.8-1 en Docker hacia Gmail.

> Números de versión usados para **documentar las fases del proyecto**; no son versiones oficiales de Proxmox ni implican que se hayan creado GitHub Releases o tags. El código permanece en el PR [#4](https://github.com/acevallos31/Tools/pull/4), rama `feat/pbs-smart-mail-forward-arm64`, **sin merge a main**.

## Resumen de versiones y despliegue

| Versión del proyecto | Estado en Raspberry | Funcionalidad |
|---|---|---|
| **V1.0 — respaldo funcional** | Conservada para rollback; ya no es el helper activo | `smartd` → `smartd-runner` → `20pbs-smart` → adaptador → helper ARM64 oficial → PBS Notifications SMTP → Gmail; **sin cola ni reintentos persistentes**. |
| **V2.0 — operativa y validada** | Helper ARM64, cola SQLite, temporizador y adaptador SMART encolado activos; **flujo final desde `smartd-runner` hasta Gmail recibido y confirmado en Paso 89** | Helper ARM64 modificado para notificar fallos SMTP; cola SQLite persistente; retry/backoff y unidades systemd; pruebas aisladas y build ARM64 aprobados. |

**Fecha del registro:** 14 de octubre de 2026. **V2.0 validada funcionalmente y en operación en Raspberry.** El ejecutable permanece intencionalmente en la ruta `versions/V2.0-RC1/`, referida por Docker Compose; no moverlo ni renombrarlo. Designación interna del proyecto, sin release/tag y sin merge del PR #4.

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

## V2.0 — Cola persistente desplegada y validada

### Cambios funcionales
- Agrega `pbs-smart-queue`: SQLite en `/var/spool/pbs-smart-mail`, transacciones durables, cola acotada (500 mensajes / 16 MiB, 256 KiB por mensaje), acceso restringido a root.
- Alerta se encola primero y un worker manda correos cuando el destino está disponible; retrasos exponenciales de 60 s a 3600 s; lote máximo de 5 mensajes.
- `pbs-smart-queue.service` y `pbs-smart-queue.timer`: reintentos periódicos y al iniciar el sistema, activados y verificados en Paso 86.1.
- `smartd-to-pbs-queued` reemplaza el envío directo: el notificador `20pbs-smart` ya apunta al adaptador encolado desde Paso 88, con respaldo V1 preservado.
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

### Criterios de aceptación V2 — completados
1. **OK (Paso 73):** comprobar `--pbs-smart-queue-protocol` y `ldd -r` del helper corregido en ruta temporal de PBS.
2. **OK (Pasos 74–78):** preservar V1, probar SMTP sintético en Gmail, desplegar V2 sin tareas activas y confirmar `running/healthy` y datastore montado.
3. **OK (Pasos 79–85):** instalar cola y unidades, validar en laboratorio aislado fallo simulado con retención de pendiente y procesamiento tras recuperación. No se generó una falla SMTP real.
4. **OK (Pasos 86–89):** activar timer y adaptador encolado; confirmar recorrido `smartd-runner` → cola → PBS → Gmail recibido y `pending=0`.
5. **OK (cierre del Paso 89):** documentación actualizada y V1 preservada como respaldo. El PR #4 permanece draft/sin fusionar.

### Compatibilidad y limitaciones
- V1 y V2 reutilizan el mismo SMTP y matcher existentes en PBS; la cola V2 se aloja en el **host**, no en el datastore.
- Un acuse positivo confirma que un endpoint aceptó el mensaje, **no** garantiza que Gmail haya depositado finalmente el correo en la bandeja.
- Semántica de reintentos **al menos una vez**: si el envío se acepta y el proceso cae antes de confirmar SQLite, puede producirse un mensaje duplicado.
- Si la cola llena su capacidad, devuelve error y no elimina alertas existentes; es necesario monitorear espacio y pendientes.
- No publicar credenciales, datos de `notifications-priv.cfg` ni correos reales almacenados en el spool.

## Recuperación y rollback

- **Estado actual:** V2.0 está desplegada; V1 ya no es el camino activo, pero conserva wrapper, adaptador y binario para rollback.
- **Rollback del adaptador, sin recrear PBS:** restaurar exclusivamente `/etc/smartmontools/run.d/20pbs-smart` desde `/opt/pbs/smart-alerts/20pbs-smart.direct.pre-v2` de forma atómica, verificando su contenido. Mantener V2 helper y timer para procesar alertas **ya encoladas**; si se desea detener el timer, hacerlo únicamente cuando se haya vaciado o preservado la cola y se acepte la suspensión de sus entregas.
- **Rollback del helper a binario V1** (solo si necesario): tras restaurar adaptador directo, verificar cola vacía o plan para preservarla, detener timer si procede, restaurar el `source:` original desde el respaldo `/opt/pbs/compose.yml.pre-v2-20261014-161215` **sin sobrescribir otros cambios**, y recrear el contenedor solo en una ventana sin tareas PBS activas. **Nunca borrar SQLite con pendientes**: V1 no confirma correctamente fallos SMTP y no debe ejecutarse como worker V2.
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

### Paso 82 — Unidades systemd instaladas sin activar (14-10-2026)

Salida confirmada del host Raspberry: `pbs-smart-queue.service` y `pbs-smart-queue.timer` instalados en `/etc/systemd/system` con permisos 0644, seguidos de `systemctl daemon-reload`. La validación `sudo systemd-analyze verify` indicó `OK: unidades instaladas y validas`. Estado: timer `disabled`, timer `inactive`, service `inactive`. Cola SQLite `pending=0 bytes=0 previously_failed=0` y contenedor `pbs` `running/healthy`. **No se habilitaron reintentos automáticos y no se sustituyó el adaptador SMART de envío inmediato**. Siguiente: ejecutar manualmente una sola alerta sintética encolada mediante el servicio real y comprobar recepción Gmail y `pending=0`.

### Paso 83 — Primera entrega manual desde la cola SQLite (14-10-2026)

Prueba realizada en Raspberry Pi con un mensaje **sintético** con asunto `[PRUEBA COLA V2] Raspberry Pi 5`, 323 bytes. `pbs-smart-queue enqueue` devolvió `INFO queued` y `pending=1 bytes=323 previously_failed=0`. Al ejecutar manualmente `sudo systemctl start pbs-smart-queue.service`, el journal confirmó `INFO forwarded id=1792017858-ca46fa923b9f4ceb9bf9e9d80c4ac8ea after_attempt=1`, servicio finalizado sin error. La cola quedó en `pending=0 bytes=0 previously_failed=0`. **Aún no se ha recibido confirmación explícita de llegada a Gmail para este mensaje del Paso 83**; el acuse del helper confirma aceptación del envío, no entrega final a la bandeja. El timer sigue deshabilitado y no se ha cambiado el adaptador SMART de producción a modo encolado.

### Confirmación de recepción del Paso 83 (14-10-2026)

El usuario confirmó explícitamente que recibió en Gmail el mensaje con asunto `[PRUEBA COLA V2] Raspberry Pi 5`, después de que el worker eliminara el mensaje de SQLite (`pending=0`). Queda verificada la entrega sintética completa **cola local → servicio systemd → helper V2 → PBS SMTP → Gmail**. La cola automática y el adaptador `smartd-to-pbs-queued` todavía no están activados; sigue pendiente validar la retención ante un fallo controlado.

### Paso 84.2 — Fallo de transporte simulado con retención persistente (14-10-2026)

En el laboratorio **aislado** `~/pbs-smart-queue-staging/retry-lab`, no en la cola real, se crearon `fake-check` (protocolo `checked-delivery-v1`), `fake-forwarder` (retorna error 75), y mensaje sintético de 97 bytes. `sudo env PBS_SMART_QUEUE_DIR="$LAB/spool" ... enqueue "$LAB/test.eml"` registró `INFO queued id=1792018607-a58f82f060044535908d6ffe289a09c7 bytes=97`. El `run` con transporte simulado devolvió `ERROR pending id=... attempt=1 retry_in=60s reason=forwarder exit status 75`, y `status` informó `pending=1 bytes=97 previously_failed=1`. **Se verificó que no se elimina el mensaje ante un fallo**. La cola real estaba previamente en `pending=0` y PBS `running/healthy`; no se activó el timer. Falta comprobar el procesamiento posterior del mismo mensaje al recuperar el transporte simulado.

### Paso 85 — Recuperación del transporte simulado y eliminación tras acuse (14-10-2026)

En el laboratorio SQLite aislado `~/pbs-smart-queue-staging/retry-lab` se sustituyó `fake-forwarder` para que devolviera `exit 0`. Tras `sleep 65` (superando el backoff inicial de 60 segundos), se ejecutó manualmente `pbs-smart-queue run` con `PBS_SMART_QUEUE_DIR`, `PBS_SMART_FORWARDER` y `PBS_SMART_PROTOCOL_CHECK` apuntando al laboratorio. La salida de Raspberry confirmó `INFO forwarded id=1792018607-a58f82f060044535908d6ffe289a09c7 after_attempt=2`: **mismo ID de mensaje retenido tras fallo simulado en Paso 84**, reenviado en segundo intento. Luego `pending=0 bytes=0 previously_failed=0`. **Se validó fallo + persistencia + reintento + eliminación tras confirmación** en simulador, no un fallo SMTP real. El timer de producción y el adaptador SMART encolado siguen sin activarse.

### Paso 86 — Timer habilitado, pendiente confirmar siguiente disparo (14-10-2026)

Captura del usuario: helper activo responde `checked-delivery-v1`; cola de producción `pending=0 bytes=0 previously_failed=0`; `sudo systemctl enable --now pbs-smart-queue.timer` creó enlace en `timers.target.wants`; `systemctl is-enabled` = `enabled`, `is-active` = `active`. PBS continúa `Estado=running Salud=healthy`. **Observación importante:** `systemctl list-timers pbs-smart-queue.timer` mostró `NEXT -` y `LAST Wed 2026-10-14 17:03:37 CST (41ms ago)` en la captura, inmediatamente después de la activación. Se requiere repetir consulta de timer y revisar `journalctl`/`systemctl show` para confirmar que `OnUnitInactiveSec=60s` está rearmando el timer antes de sustituir el adaptador SMART. Hasta entonces no declarar los reintentos periódicos validados. `smartd` sigue con adaptador directo.

### Paso 86.1 — Reprogramación periódica systemd confirmada (14-10-2026)

Captura Raspberry: `systemctl list-timers --all pbs-smart-queue.timer` mostró `LAST Wed 2026-10-14 17:04:44 CST` y `NEXT Wed 2026-10-14 17:05:45 CST` (aproximadamente 61 segundos); el aparente `NEXT -` inmediatamente tras activarlo en el Paso 86 era transitorio. `systemctl show pbs-smart-queue.service` mostró `Result=success`, `ActiveState=inactive`, `SubState=dead`, esperado para servicio `Type=oneshot` entre ejecuciones. El journal mostró ejecución inicial 17:03:37 y ejecución 17:04:44–17:04:45 sin errores. Cola real sigue `pending=0 bytes=0 previously_failed=0`. Timer periódico queda **validado**. Aún falta conmutar adaptador SMART al modo encolado y prueba final completa smartd-runner → SQLite → PBS → Gmail.

### Paso 87 — Estado previo a conmutación SMART (14-10-2026)

La captura compartida al ejecutar el Paso 87 permite verificar la cola real `pending=0 bytes=0 previously_failed=0`, el contenedor PBS `Estado=running Salud=healthy` y que `/etc/smartmontools/run.d/20pbs-smart` **todavía contiene** `exec /opt/pbs/smart-alerts/smartd-to-pbs "$1"` (adaptador V1 de envío directo). La parte visible **no muestra** salida de verificación de permisos/copia de respaldo; verificar ambos archivos en el preflight antes de efectuar la sustitución atómica del wrapper. Timer V2 ya había sido validado como activo y periódico en el Paso 86.1. No declarar conmutación completada sin evidencia.

### Paso 87 — Preparación final del adaptador encolado completada (14-10-2026)

Salida completa del usuario confirma: `smartd-to-pbs-queued` instalado en `/opt/pbs/smart-alerts/smartd-to-pbs-queued` (`root:root 0750`); copia de respaldo `/opt/pbs/smart-alerts/20pbs-smart.direct.pre-v2` (`root:root 0750`), tras comprobaciones iniciales y `sudo cmp` de origen/destino. `20pbs-smart` seguía usando `exec /opt/pbs/smart-alerts/smartd-to-pbs "$1"`, cola persistente `pending=0 bytes=0 previously_failed=0`, PBS `running/healthy`. La conmutación a `smartd-to-pbs-queued` **aún no estaba realizada** al terminar el paso. Siguiente: sustituir atómicamente solo `20pbs-smart` con preflight y confirmar su contenido. El respaldo contiene la ruta directa anterior.

### Paso 88 — Activación del adaptador SMART encolado (14-10-2026)

La salida real de la Raspberry confirma preflight completo (respaldo coincide con wrapper anterior, nuevo adaptador ejecutable, timer activo, helper `checked-delivery-v1`, cola real vacía), sustitución del wrapper `/etc/smartmontools/run.d/20pbs-smart` y contenido activo:

```sh
#!/bin/sh
set -eu
exec /opt/pbs/smart-alerts/smartd-to-pbs-queued "$1"
```

PBS permaneció `Estado=running Salud=healthy`. Se conserva `/opt/pbs/smart-alerts/20pbs-smart.direct.pre-v2` (root:root 0750) para rollback. **Falta comprobar el flujo entero `smartd-runner` → cola → worker → PBS → Gmail con prueba sintética antes de declarar V2.0 estable.** No se reiniciaron PBS, Docker ni smartd.

### Paso 89 — Prueba sintética de extremo a extremo desde smartd-runner (14-10-2026)

La Raspberry verificó `run-parts --test --lsbsysinit /etc/smartmontools/run.d` con resultado **solo** `/etc/smartmontools/run.d/20pbs-smart`; el wrapper contiene `exec /opt/pbs/smart-alerts/smartd-to-pbs-queued "$1"` y el timer está activo. Se inyectó una alerta SMART **sintética** con asunto `[PRUEBA FINAL SMARTD V2] Raspberry Pi 5` a través de `/usr/share/smartmontools/smartd-runner`, sin provocar fallos físicos. Resultado: `INFO queued id=1792019809-6e658c24749345958f9640a06beec33e bytes=348`. El journal registró `INFO forwarded id=1792019809-6e658c24749345958f9640a06beec33e after_attempt=1` a las 17:16:51. La cola real quedó `pending=0 bytes=0 previously_failed=0`, y contenedor PBS `Estado=running Salud=healthy`. **Se confirmó aceptación del envío por el helper, pero falta confirmación explícita del usuario de recepción del mensaje específico del Paso 89 en Gmail.** No declarar V2.0 estable hasta esa confirmación.

### Paso 89 — Confirmación final Gmail y cierre de V2.0 (14-10-2026)

Tras registrar `INFO queued id=1792019809-6e658c24749345958f9640a06beec33e bytes=348` generado por `smartd-runner`, el mismo ID fue procesado por `pbs-smart-queue.service` (`INFO forwarded ... after_attempt=1`), la cola real quedó `pending=0 bytes=0 previously_failed=0` y PBS permaneció `running/healthy`. **El usuario confirmó explícitamente la recepción en Gmail** del correo con asunto `[PRUEBA FINAL SMARTD V2] Raspberry Pi 5`.

**Resultado:** V2.0 **validada funcionalmente y operativa**, desde `smartd-runner` hasta Gmail. Pruebas de falla/recuperación simuladas en cola SQLite aislada aprobadas; **no se ha provocado una falla real de disco ni una interrupción SMTP real**. Se conserva el helper físicamente bajo `versions/V2.0-RC1/` para no alterar el bind mount activo. V1 está respaldada y puede recuperarse mediante procedimiento controlado; el PR #4 continúa en borrador, sin merge a `main` ni publicación de release/tag oficial.
