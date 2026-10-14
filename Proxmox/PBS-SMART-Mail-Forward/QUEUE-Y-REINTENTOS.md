# V2.0 — Cola local persistente de reintentos SMART → PBS → Gmail

Historial y diferencias con la **V1.0 preservada para rollback**: [VERSIONES.md](./VERSIONES.md).

**Estado al 14-10-2026 (tras Paso 89): V2.0 operativa y validada.** Helper ARM64 parcheado, SQLite y unidades systemd activos, `20pbs-smart` apuntando a `smartd-to-pbs-queued`. El correo sintético final desde `smartd-runner` fue encolado, enviado, eliminado de SQLite y **recibido en Gmail** (confirmación del usuario). Pruebas aisladas de fallo simulado (exit 75) y recuperación (intento 2) superadas. El binario se mantiene en la ruta histórica `versions/V2.0-RC1/` **sin renombrar** para no invalidar Compose. V1 respaldada; PR #4 draft sin merge.

## Motivación: no confiar en el código de salida del helper original

En el código oficial fijado de Proxmox, `proxmox_notify::api::common::send` llama a `Bus::send`, que **solo registra en logs las fallas de endpoints SMTP**; devuelve éxito incluso ante esos errores. Además, el `main()` oficial registra otros fallos sin terminar con código distinto de cero. Por tanto, una cola que borrase el mensaje cuando el helper antiguo devuelve 0 podría **perder** alertas.

El workflow compila una versión parcheada de las mismas revisiones oficiales:
- `patch-checked-delivery.py` agrega `Bus::send_checked`: error si no hay targets, si están deshabilitados o si falla cualquier endpoint.
- La función principal propaga fallos con código de salida no cero.
- `proxmox-mail-forward --pbs-smart-queue-protocol` debe imprimir exactamente `checked-delivery-v1`. El trabajador **rechaza liberar cualquier mensaje** hasta que el contenedor demuestre ese protocolo.

El resultado exitoso demuestra aceptación por el destino SMTP configurado en PBS, **no garantiza entrega en bandeja Gmail**. Si se aceptó SMTP pero el proceso muere antes de eliminar el mensaje, puede haber reenvío duplicado (semántica *al menos una vez*).

## Arquitectura

```text
Micron NVMe / ADATA SATA → smartd → smartd-runner → 20pbs-smart
    → smartd-to-pbs-queued → pbs-smart-queue enqueue
        → SQLite durable /var/spool/pbs-smart-mail/queue.sqlite3
            → systemd timer (~1 min) → worker (flock + retry/backoff)
                → protocolo checked-delivery-v1
                → pbs-smart-forward → Docker PBS → SMTP PBS → Gmail
```

## Protecciones y parámetros

| Parámetro | Valor |
|---|---|
| Spool local | `/var/spool/pbs-smart-mail` (0700, root) |
| Base SQLite | `queue.sqlite3` (0600); WAL, `synchronous=FULL` |
| Alta | Transacción SQLite `BEGIN IMMEDIATE`, confirmación antes de responder a `smartd` |
| Capacidad | 500 alertas, 16 MiB total, 256 KiB por correo |
| Al saturarse | **No elimina** mensajes: falla el alta y registra error local |
| Trabajador | Un proceso por vez (flock); hasta 5 mensajes por ejecución |
| Timeout | 30 s por intento; verifica primero el helper |
| Reintentos | 60, 120, 240, 480... hasta 3600 segundos; persistentes, sin caducidad |
| Temporizador | `OnBootSec=45s`, `OnUnitInactiveSec=60s` |
| Pruebas | 5 tests aislados y simulación de fallo/recuperación sin SMTP real; entrega sintética real a Gmail confirmada |

Los fallos recurrentes se registran en `journalctl -u pbs-smart-queue.service`. La cola contiene correos diagnósticos: conservar permisos restringidos y respaldar cifrada si corresponde. No almacena contraseñas SMTP.

## Despliegue comprobado por fases — referencia, NO ejecutar en bloque

1. **Preparación sin impacto**: descargar y revisar `pbs-smart-queue`, `tests/test_queue.py`, unidades systemd y adaptador `smartd-to-pbs-queued` desde esta rama; ejecutar `python3 -m unittest discover -s tests -v` en un directorio temporal. No tocar las rutas operativas.
2. **Helper ARM64 verificado**: esperar éxito del nuevo workflow GitHub Actions; validar hash del artefacto; preservar copia del binario anterior; instalar en el host y recrear PBS en una ventana **sin tareas de backup activas**. Confirmar `sudo docker exec pbs /usr/bin/proxmox-mail-forward --pbs-smart-queue-protocol` → `checked-delivery-v1` y hacer una prueba de envío sintético recibida en Gmail.
3. **Validación del fallo**: el flujo de pruebas aisladas debe retener en SQLite un mensaje cuando un forwarder falso devuelve código no cero. No cortar la conectividad real del PBS ni generar fallos SMART físicos.
4. **Activación controlada realizada (Pasos 80–88)**: preparar `/var/spool/pbs-smart-mail` `root:root 0700`; instalar `/opt/pbs/smart-alerts/pbs-smart-queue` `root:root 0750`, unidades `.service` y `.timer`; conservar `/opt/pbs/smart-alerts/smartd-to-pbs` (V1) sin modificar; respaldar `/etc/smartmontools/run.d/20pbs-smart` como `/opt/pbs/smart-alerts/20pbs-smart.direct.pre-v2`; instalar `/opt/pbs/smart-alerts/smartd-to-pbs-queued` `root:root 0750`; activar timer y reemplazar **solo el wrapper** `/etc/smartmontools/run.d/20pbs-smart` para apuntar al adaptador encolado. El binario V2 permanece montado solo lectura.
5. **Verificación final realizada (Paso 89)**: la alerta sintética por `smartd-runner` con asunto `[PRUEBA FINAL SMARTD V2] Raspberry Pi 5` registró `INFO queued` (348 bytes), `INFO forwarded ... after_attempt=1`, `pending=0` y el usuario confirmó recepción Gmail.

## Mantenimiento

```bash
sudo /opt/pbs/smart-alerts/pbs-smart-queue status
sudo systemctl status pbs-smart-queue.timer --no-pager
sudo journalctl -u pbs-smart-queue.service -n 50 --no-pager
sudo systemctl start --no-block pbs-smart-queue.service
```

No borrar archivos SQLite para resolver fallas SMTP. Antes de recrear PBS, comprobar tareas activas con `proxmox-backup-manager task list --output-format json-pretty`, estado `healthy` y datastore montado.

## Rollback seguro sin perder pendientes

**Nunca deshabilitar primero el worker si la cola todavía contiene avisos sin entregar:** los mensajes seguirían almacenados pero se suspenderían los reintentos. **Nunca borrar ni editar** los archivos de SQLite/WAL para «desatascar» alertas.

**A. Volver solo al envío directo V1 (`smartd`), sin detener PBS:**

1. Consultar `sudo /opt/pbs/smart-alerts/pbs-smart-queue status` y `systemctl is-active pbs-smart-queue.timer`.
2. Confirmar integridad del respaldo `/opt/pbs/smart-alerts/20pbs-smart.direct.pre-v2`, que contiene `exec /opt/pbs/smart-alerts/smartd-to-pbs "$1"`.
3. Restaurar el wrapper **atómicamente** (ejemplo para uso en una recuperación justificada, no en chequeos normales):

```bash
WR=/etc/smartmontools/run.d/20pbs-smart
BAK=/opt/pbs/smart-alerts/20pbs-smart.direct.pre-v2
sudo test -x "$BAK" && sudo grep -Fq 'exec /opt/pbs/smart-alerts/smartd-to-pbs "$1"' "$BAK" || exit 1
TMP=$(sudo mktemp /etc/smartmontools/run.d/.20pbs-smart.rollback.XXXXXXXX) || exit 1
sudo install -o root -g root -m 0755 "$BAK" "$TMP"
sudo sh -n "$TMP" && sudo mv -f "$TMP" "$WR"
sudo cat "$WR"
```

Esto restaura nuevos avisos SMART al flujo directo V1 (menos resiliente). **Dejar el timer V2 funcionando para drenar mensajes anteriores**, especialmente si `pending > 0`. El helper V2 es compatible con el adaptador directo mientras siga activo.

**B. Volver también al helper V1** (solo si fuera imprescindible y en una ventana sin tareas PBS):

1. Asegurar que el wrapper ya apunta al adaptador directo; verificar que la cola se haya vaciado **o** exista un plan explícito para preservarla. Sin drenaje, los pendientes quedarían sin salida.
2. Deshabilitar el timer **solo cuando sea seguro suspender los reintentos**: `sudo systemctl disable --now pbs-smart-queue.timer`.
3. Restaurar únicamente el `source` del bind mount del helper en `/opt/pbs/compose.yml` a la ruta V1 versionada, preservando todos los demás mounts (se dispone de `/opt/pbs/compose.yml.pre-v2-20261014-161215` como referencia).
4. Comprobar antes de recrear: `findmnt /mnt/pbs`, `sudo docker exec pbs proxmox-backup-manager task list --output-format json-pretty` (sin tareas), `sudo docker compose -p pbs -f /opt/pbs/compose.yml config --quiet`. Recién entonces hacer la recreación controlada, comprobar estado `healthy` y probar Gmail.
5. **No ejecutar el worker de cola con el helper V1**: la validación del protocolo `checked-delivery-v1` lo bloquea deliberadamente para evitar eliminar avisos no entregados.

Los registros locales de `smartd`, la configuración SMTP y el datastore no deben modificarse para efectuar un rollback del adaptador.

**Límites:** ningún sistema de almacenamiento garantiza colas si falla la unidad del host o se llena el filesystem; un SMTP puede aceptar y rechazar correo posteriormente; ante varios endpoints, los reintentos completos pueden duplicar el mensaje en destinos que sí aceptaron.
