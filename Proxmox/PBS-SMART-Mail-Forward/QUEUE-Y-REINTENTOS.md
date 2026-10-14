# V2.0-RC1 — Cola local persistente de reintentos SMART → PBS → Gmail

Historial y diferencias con la **V1.0 preservada para rollback**: [VERSIONES.md](./VERSIONES.md).

**Estado al 14-10-2026 (tras Paso 88):** helper ARM64 V2 corregido activo, cola SQLite instalada, worker y timer habilitados, ejecución periódica verificada, prueba desde SQLite hasta Gmail recibida, y `20pbs-smart` conmutado a `smartd-to-pbs-queued` con respaldo V1. Pruebas de fallo y recuperación aisladas aprobadas. **Pendiente prueba sintética final desde `smartd-runner` hasta Gmail; por ello sigue siendo RC1.**

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
    → smartd-to-pbs (versión encolada) → pbs-smart-queue enqueue
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
| Pruebas | 5 casos aislados con transportes simulados; no se envían mensajes reales |

Los fallos recurrentes se registran en `journalctl -u pbs-smart-queue.service`. La cola contiene correos diagnósticos: conservar permisos restringidos y respaldar cifrada si corresponde. No almacena contraseñas SMTP.

## Despliegue por fases — NO ejecutar en bloque

1. **Preparación sin impacto**: descargar y revisar `pbs-smart-queue`, `tests/test_queue.py`, unidades systemd y adaptador `smartd-to-pbs-queued` desde esta rama; ejecutar `python3 -m unittest discover -s tests -v` en un directorio temporal. No tocar las rutas operativas.
2. **Helper ARM64 verificado**: esperar éxito del nuevo workflow GitHub Actions; validar hash del artefacto; preservar copia del binario anterior; instalar en el host y recrear PBS en una ventana **sin tareas de backup activas**. Confirmar `sudo docker exec pbs /usr/bin/proxmox-mail-forward --pbs-smart-queue-protocol` → `checked-delivery-v1` y hacer una prueba de envío sintético recibida en Gmail.
3. **Validación del fallo**: el flujo de pruebas aisladas debe retener en SQLite un mensaje cuando un forwarder falso devuelve código no cero. No cortar la conectividad real del PBS ni generar fallos SMART físicos.
4. **Activación controlada**: crear `/var/spool/pbs-smart-mail` `root:root 0700`; copiar script Python a `/opt/pbs/smart-alerts/pbs-smart-queue` `root:root 0750`; instalar el `.service` y `.timer` bajo `/etc/systemd/system/`; respaldar `/opt/pbs/smart-alerts/smartd-to-pbs` como `smartd-to-pbs.prequeue`; sustituirlo por `smartd-to-pbs-queued` modo 0750; ejecutar `systemctl daemon-reload` y `systemctl enable --now pbs-smart-queue.timer`. El notificador `20pbs-smart` sigue igual.
5. **Verificación final**: repetir una alerta sintética por `smartd-runner`, recibir correo Gmail; `sudo /opt/pbs/smart-alerts/pbs-smart-queue status` debe informar `pending=0`. Consultar el journal del worker y el temporizador.

## Mantenimiento

```bash
sudo /opt/pbs/smart-alerts/pbs-smart-queue status
sudo systemctl status pbs-smart-queue.timer --no-pager
sudo journalctl -u pbs-smart-queue.service -n 50 --no-pager
sudo systemctl start --no-block pbs-smart-queue.service
```

No borrar archivos SQLite para resolver fallas SMTP. Antes de recrear PBS, comprobar tareas activas con `proxmox-backup-manager task list --output-format json-pretty`, estado `healthy` y datastore montado.

## Rollback sin pérdida de pendientes

Para suspender el worker sin afectar `smartd` ni PBS:

```bash
sudo systemctl disable --now pbs-smart-queue.timer
```

Si se vuelve al adaptador antiguo, respaldar primero el archivo en uso y restaurar `smartd-to-pbs.prequeue`; esto recupera el envío inmediato **sin cola**. Los mensajes ya encolados permanecen en SQLite y deben drenarse con helper checked antes de retirar spool. Mantener `20pbs-smart` y logs locales sin cambios.

**Límites:** ningún sistema de almacenamiento garantiza colas si falla la unidad del host o se llena el filesystem; un SMTP puede aceptar y rechazar correo posteriormente; ante varios endpoints, los reintentos completos pueden duplicar el mensaje en destinos que sí aceptaron.
