# PBS SMART Mail Forward — Raspberry Pi 5 ARM64

> **Estado del laboratorio (14-10-2026): integración configurada, validada y operativa.** Las pruebas sintéticas de entrega por Gmail fueron confirmadas. No se provocó una falla física SMART, por lo que la recepción de un aviso real se verificará únicamente cuando ocurra un evento legítimo.

## Objetivo

Reutilizar el destino SMTP de **Proxmox Backup Server** para las alertas de discos generadas por `smartd` del host Raspberry Pi, sin instalar otro MTA ni duplicar las credenciales de Gmail.

```text
Micron 2400A NVMe ─┐
                   ├── smartd (host Debian 12)
ADATA SU650 SATA ──┘       │
                           └─ smartd-runner
                                 └─ /etc/smartmontools/run.d/20pbs-smart
                                       └─ /opt/pbs/smart-alerts/smartd-to-pbs
                                             └─ /opt/pbs/smart-alerts/pbs-smart-forward
                                                   └─ docker exec -i pbs
                                                         └─ /usr/bin/proxmox-mail-forward
                                                               └─ PBS Notifications
                                                                     └─ smtp-pbs-alerts → Gmail
```

## Entorno y estado comprobados

| Elemento | Configuración / evidencia |
|---|---|
| Hardware | Raspberry Pi 5 ARM64 |
| Host | Debian 12, `smartmontools` activo |
| Contenedor | `pbs`, PBS 4.2.8-1 ARM64 (`dockurr/proxmox-backup:latest`) |
| Discos | `/dev/nvme0` Micron 2400A; `/dev/sda` ADATA SU650 vía SAT/USB |
| Datastore | Host `/mnt/pbs` sobre `/dev/sda1` ext4, bind a `/var/lib/proxmox-backup` |
| Config PBS | Host `/opt/pbs/config` bind a `/etc/proxmox-backup` |
| SMTP y matcher | `smtp-pbs-alerts` y `pbs-important-alerts`; recepción Gmail confirmada |
| `smartd` | Unidad `smartmontools` activa, estado de systemd: `Next check of 2 devices` |
| Binario ARM64 | SHA256 `a2db207ddf30226eb0be4ad537fc0f563f65a925e54fea7549bc7d2fc468267c` |
| Host | `/opt/pbs/smart-alerts/bin/proxmox-mail-forward`, `root:root`, 0755 |
| Contenedor | `/usr/bin/proxmox-mail-forward`, bind **solo lectura** |
| Compose principal | `/opt/pbs/compose.yml` integra tres volúmenes; `config --quiet` OK |
| Reinicio del contenedor | `unless-stopped`; `running/healthy` después de recreación |
| Notificador host | `20pbs-smart` activo vía `run-parts --lsbsysinit` |
| Notificador antiguo | `10mail` conservado, pero sin bit de ejecución porque no existe `/usr/bin/mail` |

## Archivos desplegados en el host

- `/opt/pbs/compose.yml`: configuración **principal**; incluye montaje persistente del helper.
- `/opt/pbs/compose.smart-mail.override.yml`: archivo usado durante el despliegue inicial; **no hace falta utilizarlo** para las recreaciones futuras si se usa el principal ya consolidado.
- `/opt/pbs/compose.yml.backup-20261014-144827`: respaldo anterior a la consolidación.
- `/opt/pbs/smart-alerts/bin/proxmox-mail-forward`: ejecutable ARM64 autenticado con SHA256.
- `/opt/pbs/smart-alerts/pbs-smart-forward`: valida el mensaje y el contenedor, lo pasa al helper mediante `docker exec -i`.
- `/opt/pbs/smart-alerts/smartd-to-pbs`: transforma el cuerpo de `smartd` + `SMARTD_SUBJECT` en un mensaje MIME.
- `/etc/smartmontools/run.d/20pbs-smart`: invoca el adaptador anterior.
- `/etc/smartmontools/run.d/10mail`: conserva el script Debian original, sin ejecución.
- `/opt/pbs/smart-alerts/10mail.original`: copia de respaldo del notificador original.

No se cambió `/etc/smartd.conf`; mantiene:

```text
DEVICESCAN -d removable -n standby -m root -M exec /usr/share/smartmontools/smartd-runner
```

La carpeta `run.d` se consulta por cada aviso. El puente usa un fichero temporal y lo elimina al terminar. Los registros locales de `smartd` y el almacenamiento de backups son independientes del SMTP.

## Validaciones ejecutadas

1. **Compilación:** GitHub Actions [run 38623764393](https://github.com/acevallos31/Tools/actions/runs/38623764393), artifact `11922951805`, runner ARM64. Paquete descargado en Raspberry y comprobado con SHA256.
2. **Binario:** `ELF 64-bit ... ARM aarch64`; `ldd` y `ldd -r` dentro del contenedor resolvieron todas las bibliotecas.
3. **Notificación interna:** mensaje sintético inyectado en `proxmox-mail-forward`; Gmail recibido.
4. **Puente host → contenedor:** mensaje MIME desde Raspberry vía `pbs-smart-forward`; Gmail recibido.
5. **Adaptador real de `smartd`:** cuerpo + `SMARTD_SUBJECT` vía `smartd-to-pbs`; Gmail recibido.
6. **Camino `smartd-runner` + `run.d`:** alerta sintética `[PRUEBA FINAL SMARTD] Raspberry Pi 5`; **Gmail recibido**.
7. **Monitoreo de discos:** `smartctl --scan` detectó SAT en `/dev/sda` y NVMe en `/dev/nvme0`; `smartmontools.service` informó próximo chequeo de **2 dispositivos**. Se observaron archivos de estado de ambos en `/var/lib/smartmontools/`.
8. **Persistencia:** contenedor recreado una vez con montaje de solo lectura, retornó `running/healthy`; configuración principal consolidada después y verificada equivalente a la configuración activa.
9. **Auditoría final:** tres volúmenes declarados, montaje activo `SoloLectura=true`, únicamente `20pbs-smart` habilitado, `smartd` activo y `/mnt/pbs` montado en ext4 `rw,noatime`.

## Construcción reproducible

Workflow: [`.github/workflows/build-proxmox-mail-forward-arm64.yml`](../../.github/workflows/build-proxmox-mail-forward-arm64.yml).

Revisiones upstream fijas:

- `proxmox/proxmox-mail-forward` — `9890c29a3d3da04262fe5564b2321be59928de5e`
- `proxmox/proxmox-rs` — `89c1d597a9d15743049eadcb1add380573265904`

El build necesita `uuid-dev`, enlaza contra bibliotecas del sistema y empaqueta el ejecutable, `Cargo.lock`, commits de origen y `SHA256SUMS`. El artifact de GitHub Actions puede caducar: conservar el paquete verificado o ejecutar nuevamente el workflow cuando sea necesario.

SHA256 del archivo tar.gz verificado: `3644a3bd6320087dcf2c3d8e93e753ac5d24b1f8a873567951c8bbed799a0601`.

## Operación, actualización y recuperación

Consultar [**OPERACION-Y-RECUPERACION.md**](./OPERACION-Y-RECUPERACION.md) para los comandos de diagnóstico, prueba sintética, actualización segura, respaldos y rollback.

### Limitaciones importantes

- La prueba de extremo a extremo fue **sintética**; no se indujo un fallo real del hardware.
- `proxmox-mail-forward` puede devolver exit code 0 aunque la notificación falle más adelante. El criterio de éxito es la **recepción efectiva** de Gmail y la revisión de logs.
- No hay cola de reintentos persistente en el puente: si PBS, Docker, la conectividad o Gmail no están disponibles en el momento del aviso, puede perderse el envío. Se recomienda revisar periódicamente el servicio y considerar una cola local en una mejora posterior.
- No subir contraseñas SMTP, `notifications-priv.cfg`, ni archivos privados de `/opt/pbs/config`.
- El PR [#4](https://github.com/acevallos31/Tools/pull/4) permanece en **draft**, sin fusionar a `main`.

## Mejora pendiente de despliegue: cola local SQLite (14-10-2026)

**No está activada en la Raspberry todavía.** Se implementaron en la rama la cola de reintentos, tests, adaptador y unidades systemd; consultar [QUEUE-Y-REINTENTOS.md](./QUEUE-Y-REINTENTOS.md) antes de desplegar.

- **Workflow ARM64 con helper de confirmación**: [run 38641594423](https://github.com/acevallos31/Tools/actions/runs/38641594423) — compilación y 5 pruebas aisladas finalizadas correctamente.
- Artefacto nuevo ZIP SHA256: `43725ddc5dc54f992784aff7913d842899717e5f1aac595cdbcdcd6cd46b90c3`
- Paquete tar.gz SHA256: `c5c8de901f20e9f93ddb99407be598d26c0d2c66228b25034966a07ff0566b41`
- **Binario ARM64 corregido SHA256:** `4664dab7916ba1955a398bf966fa8862aee0edc4411cb8010b1fbc7ef1b58e35`
- **Helper viejo actualmente desplegado:** `a2db207ddf30226eb0be4ad537fc0f563f65a925e54fea7549bc7d2fc468267c`; **NO usarlo para confirmar una alerta encolada**. El worker comprueba el protocolo `checked-delivery-v1` y, si no está, conserva los mensajes.
- Activación solo tras reemplazar y validar el helper nuevo y realizar prueba SMTP sintética sin interrumpir backups.
