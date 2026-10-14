# PBS SMART Mail Forward — Raspberry Pi 5 ARM64

> **Estado operativo validado: V2.0 (14-10-2026).** En la Raspberry están activos el helper ARM64 con `checked-delivery-v1`, la cola persistente SQLite, el worker/timer de systemd y el adaptador encolado de `smartd`. **Prueba sintética completa `smartd-runner → SQLite → PBS SMTP → Gmail` recibida y confirmada por el usuario (Paso 89).** Se conserva V1.0 para recuperación. V2.0 es una designación interna de este proyecto, no una release oficial de Proxmox ni un tag de GitHub. El binario validado permanece en la ruta denominada `V2.0-RC1`: **no moverlo ni renombrarlo**, ya que Docker Compose utiliza esa ruta.
>
> **Código:** PR [#4](https://github.com/acevallos31/Tools/pull/4) en rama `feat/pbs-smart-mail-forward-arm64`, **sin merge a `main`**. Detalle histórico: [VERSIONES.md](./VERSIONES.md). Operación y reintentos: [QUEUE-Y-REINTENTOS.md](./QUEUE-Y-REINTENTOS.md). V1/recuperación: [OPERACION-Y-RECUPERACION.md](./OPERACION-Y-RECUPERACION.md).

## Objetivo y arquitectura activa

Reutilizar SMTP de **Proxmox Backup Server (PBS)** para alertas de discos generadas por `smartd` del host Raspberry Pi, **sin instalar un MTA adicional ni duplicar contraseñas de Gmail**.

```text
Micron 2400A NVMe ─┐
                   ├── smartd (Debian 12, host Raspberry Pi 5)
ADATA SU650 SATA ──┘       └─ smartd-runner
                                └─ /etc/smartmontools/run.d/20pbs-smart
                                     └─ smartd-to-pbs-queued
                                          └─ pbs-smart-queue enqueue
                                               └─ /var/spool/pbs-smart-mail/queue.sqlite3
                                                    └─ systemd pbs-smart-queue.timer (~1 min)
                                                         └─ pbs-smart-queue.service
                                                              └─ pbs-smart-forward
                                                                   └─ docker exec -i pbs
                                                                        └─ proxmox-mail-forward V2
                                                                             └─ PBS Notifications
                                                                                  └─ smtp-pbs-alerts → Gmail
```

El worker espera un **acuse de envío verificado** (`checked-delivery-v1`) antes de eliminar un mensaje; si el destino falla, conserva el mensaje y lo reintenta con backoff. Esto **no equivale a garantizar entrega definitiva** en la bandeja Gmail; puede haber duplicados si un correo se acepta y el proceso falla antes de confirmar SQLite.

## Entorno validado

| Elemento | Configuración / evidencia |
|---|---|
| Raspberry | Pi 5 ARM64, Debian 12 |
| PBS | 4.2.8-1 ARM64, contenedor `pbs` (`dockurr/proxmox-backup:latest`) |
| Discos monitoreados | Micron 2400A `/dev/nvme0`; ADATA SU650 `/dev/sda` USB/SAT |
| Datastore | `/mnt/pbs` en `/dev/sda1` ext4; host `/mnt/pbs/datastore` → contenedor `/var/lib/proxmox-backup` |
| Configuración PBS | Host `/opt/pbs/config` → contenedor `/etc/proxmox-backup` |
| SMTP/matcher | `smtp-pbs-alerts` / `pbs-important-alerts` existentes; Gmail confirmado |
| Configuración Docker | `/opt/pbs/compose.yml`; política de reinicio `unless-stopped` |
| Helper V2 activo | `/opt/pbs/smart-alerts/versions/V2.0-RC1/proxmox-mail-forward`, montado solo lectura en `pbs:/usr/bin/proxmox-mail-forward` |
| SHA256 helper V2 | `4664dab7916ba1955a398bf966fa8862aee0edc4411cb8010b1fbc7ef1b58e35` |
| Protocolo de acuse | `checked-delivery-v1` |
| Adaptador activo | `/etc/smartmontools/run.d/20pbs-smart` ejecuta `/opt/pbs/smart-alerts/smartd-to-pbs-queued` |
| Cola | `/var/spool/pbs-smart-mail`, `root:root 0700`; base SQLite |
| Systemd | `pbs-smart-queue.timer` habilitado/activo; `pbs-smart-queue.service` oneshot periódico |
| Estado último control (Paso 89) | Cola `pending=0 bytes=0 previously_failed=0`; PBS `running / healthy` |

No se alteró `/etc/smartd.conf`, que utiliza `smartd-runner` para enviar avisos de SMART. El `run.d/10mail` original sigue guardado pero sin ejecución; únicamente `20pbs-smart` quedó habilitado.

## Rutas operativas y respaldo V1

```text
/etc/smartmontools/run.d/20pbs-smart                    wrapper V2 en producción
/opt/pbs/smart-alerts/smartd-to-pbs-queued               adaptador V2
/opt/pbs/smart-alerts/pbs-smart-queue                    cola y worker SQLite
/opt/pbs/smart-alerts/pbs-smart-forward                  puente con contenedor
/var/spool/pbs-smart-mail/queue.sqlite3                 estado persistente de avisos
/etc/systemd/system/pbs-smart-queue.service             worker de reintentos
/etc/systemd/system/pbs-smart-queue.timer               temporizador de reintentos
/opt/pbs/smart-alerts/versions/V2.0-RC1/proxmox-mail-forward    helper activo
/opt/pbs/compose.yml                                    Compose principal
```

Respaldos verificados:
- `/opt/pbs/smart-alerts/20pbs-smart.direct.pre-v2`: wrapper anterior que llama al adaptador directo `smartd-to-pbs` (root:root 0750).
- `/opt/pbs/smart-alerts/smartd-to-pbs`: adaptador directo V1 preservado.
- `/opt/pbs/smart-alerts/versions/V1.0/proxmox-mail-forward`: binario V1 SHA256 `a2db207ddf30226eb0be4ad537fc0f563f65a925e54fea7549bc7d2fc468267c`.
- `/opt/pbs/compose.yml.pre-v2-20261014-161215`: Compose anterior al cambio de helper.
- `/opt/pbs/compose.yml.backup-20261014-144827`: respaldo histórico previo a la consolidación inicial.

**No borrar ni renombrar archivos de respaldo o el spool.** Si existen alertas pendientes al hacer rollback, **no se deben borrar**; mantener el worker V2 hasta drenarlas cuando sea posible. Para volver al binario V1 se requiere ventana sin tareas de respaldo, actualizar Compose y recrear únicamente `pbs`; para volver solo al wrapper V1 no se requiere reiniciar PBS.

## Pruebas completadas

1. Build ARM64 reproducible V2 en GitHub Actions [run 38641594423](https://github.com/acevallos31/Tools/actions/runs/38641594423); artefactos ZIP, tar.gz y SHA256 del ejecutable validados en Raspberry. Revisiones upstream fijadas: `proxmox/proxmox-mail-forward` `9890c29a3d3da04262fe5564b2321be59928de5e`; `proxmox/proxmox-rs` `89c1d597a9d15743049eadcb1add380573265904`.
2. Protocolo `checked-delivery-v1`, `ldd -r`, envío SMTP sintético con Gmail recibido; prueba negativa de mensaje vacío devuelve código 1. **No se provocó una caída SMTP real**.
3. Cinco tests aislados de SQLite en Raspberry aprobados (Paso 79), instalación root y spool vacío.
4. Cola → servicio systemd → PBS → Gmail confirmada por el usuario (Paso 83).
5. En laboratorio aislado, fallo simulado de forwarder (`exit 75`) retuvo el mensaje; tras `exit 0` se procesó el mismo ID en el intento 2 y se vació la cola (Pasos 84–85).
6. Timer systemd `enabled`, `active` y reprogramación ~60 s verificada (Paso 86.1).
7. Sustitución atómica del wrapper SMART con respaldo (Paso 88).
8. `smartd-runner` sintético → `INFO queued` 348 bytes → `INFO forwarded ... after_attempt=1` → `pending=0` → **Gmail recibido y confirmado por el usuario** (Paso 89). No se indujeron fallos físicos SMART.

## Operación segura (consultas)

```bash
sudo /opt/pbs/smart-alerts/pbs-smart-queue status
systemctl is-enabled pbs-smart-queue.timer
systemctl is-active pbs-smart-queue.timer
systemctl list-timers pbs-smart-queue.timer --no-pager
sudo journalctl -u pbs-smart-queue.service -n 30 --no-pager
sudo run-parts --test --lsbsysinit /etc/smartmontools/run.d
sudo docker inspect pbs --format 'Estado={{.State.Status}} Salud={{.State.Health.Status}}'
findmnt /mnt/pbs
```

No borrar pendientes ni editar la base SQLite manualmente. La cola admite hasta 500 mensajes, 16 MiB total y 256 KiB por aviso; reintentos exponenciales entre 60 y 3600 segundos, máximo 5 mensajes por ejecución. Los errores recurrentes se consultan en journal de systemd. El éxito del helper garantiza aceptación por el servicio de envío configurado, no entrega final a Gmail.

**Seguridad y límites:** spool y ejecutables protegidos para root; no subir credenciales ni `notifications-priv.cfg`; si falla el almacenamiento del host o se llena la cola, ninguna garantía de durabilidad puede prevenir la pérdida de una alerta nueva. Los logs locales SMART y el datastore PBS se mantienen independientes. Revisar [QUEUE-Y-REINTENTOS.md](./QUEUE-Y-REINTENTOS.md) para mantenimiento y rollback sin pérdida de pendientes.

**Desarrollo:** el PR #4 permanece en draft y sin fusionar a `main` hasta aprobación explícita.
