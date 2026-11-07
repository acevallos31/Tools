# Protección del almacenamiento de PBS en Raspberry Pi

Este proyecto documenta la configuración del **watchdog de almacenamiento** y el **arranque protegido** de Proxmox Backup Server (PBS), ejecutado como contenedor Docker en una Raspberry Pi.

> **Estado de validación:** el sistema se verificó con el SSD disponible, PBS en estado `healthy`, los temporizadores activos y una prueba independiente de envío de correo a través de la cola persistente. **Todavía no se ha probado una desconexión real o simulada del SSD.** Este repositorio conserva la versión instalada al 6 de noviembre de 2026; no representa una versión de recuperación ante desastres completamente validada.

## 1. Problema que resuelve

El datastore de PBS reside en un SSD SATA conectado por USB a la Raspberry Pi. En un incidente anterior el SSD se desconectó y reapareció con otro nombre de dispositivo (`/dev/sda` pasó a `/dev/sdb`). El punto de montaje `/mnt/pbs` dejó de estar disponible y el contenedor PBS continuó ejecutándose, provocando errores de entrada/salida y fallos en los respaldos.

La protección pretende evitar que PBS se inicie sin su datastore y detectar su pérdida durante la operación.

## 2. Componentes

| Archivo | Destino de instalación | Función |
| --- | --- | --- |
| `pbs-storage-watchdog` | `/usr/local/sbin/pbs-storage-watchdog` | Comprueba SSD/datastore, registra fallos, genera alertas e intenta detener PBS |
| `pbs-guard.service` | `/etc/systemd/system/pbs-guard.service` | Comprueba el montaje antes de permitir el arranque del contenedor |
| `pbs-storage-watchdog.service` | `/etc/systemd/system/pbs-storage-watchdog.service` | Ejecuta el watchdog mediante systemd |
| `pbs-storage-watchdog.timer` | `/etc/systemd/system/pbs-storage-watchdog.timer` | Programa comprobaciones aproximadamente cada minuto |

El script verifica el UUID del montaje, el enlace persistente `/dev/disk/by-id`, la presencia del directorio `.chunks` y un `stat` con tiempo de espera.

## 3. Comportamiento previsto

1. **Almacenamiento disponible:** el watchdog termina sin alterar PBS.
2. **Primera comprobación fallida — WARNING:** registra el problema e intenta encolar un correo preventivo.
3. **Segunda comprobación fallida — CRITICAL:** registra y encola la alerta crítica; intenta detener `pbs-guard.service` y el contenedor Docker `pbs`.
4. **Falla persistente:** utiliza archivos de estado para evitar repetir la alerta crítica en cada ciclo.
5. **Almacenamiento nuevamente disponible — RECOVERED:** encola un aviso de recuperación del **SSD**, elimina los indicadores de fallo y **no inicia PBS automáticamente**.

La recuperación del montaje no equivale a la recuperación del servicio PBS.

## 4. Dependencias y particularidades del laboratorio

- Raspberry Pi con Debian, Docker y systemd.
- Contenedor Docker denominado `pbs`, con reinicio automático de Docker deshabilitado (`Restart=no`).
- SSD de datastore montado mediante `/etc/fstab` en `/mnt/pbs`, con unidad systemd `mnt-pbs.mount`.
- Datastore con directorio `/mnt/pbs/datastore/datastore/.chunks`.
- Cola de correo **personalizada**, independiente de esta carpeta: `/opt/pbs/smart-alerts/pbs-smart-queue`, respaldada por SQLite y ejecutada por `pbs-smart-queue.service` / `pbs-smart-queue.timer`.
- Encaminamiento de `root@localhost` a través de la configuración de notificaciones de PBS.

**Atención:** `pbs-smart-queue` no es una utilidad estándar incluida en todas las instalaciones de Proxmox Backup Server. Los archivos de este repositorio no la instalan ni incluyen su código.

## 5. Antes de reutilizar la configuración

**No copies estos archivos directamente a otro equipo sin adaptarlos.**

1. Cambia el UUID de la unidad y la ruta `DEVICE` de `/dev/disk/by-id` por los correspondientes al SSD de destino.
2. Revisa las rutas del datastore y del directorio `.chunks`, el nombre real del contenedor y la unidad de montaje systemd.
3. Confirma que la cola SQLite personalizada existe y que sus notificaciones se envían al destinatario correcto.
4. Comprueba la política de reinicio de Docker, pues otro mecanismo de arranque podría omitir `pbs-guard.service`.
5. Asegúrate de que el almacenamiento de la cola de correo se encuentre fuera del SSD que se vigila.
6. Verifica permisos y dependencias antes de habilitar el servicio en un entorno productivo.

Los identificadores de disco incluidos son específicos de este laboratorio. No se publicaron contraseñas SMTP, tokens ni credenciales Docker.

## 6. Comandos de verificación

Ejecutar desde la Raspberry Pi. Los comandos son ASCII y no realizan cambios:

```bash
echo "===== VALIDACION DE SINTAXIS ====="
sudo bash -n /usr/local/sbin/pbs-storage-watchdog

echo "===== SERVICIOS ====="
systemctl is-enabled pbs-guard.service
systemctl is-active pbs-guard.service
systemctl is-active pbs-storage-watchdog.timer
systemctl is-active pbs-smart-queue.timer

echo "===== SSD ====="
findmnt /mnt/pbs -o TARGET,SOURCE,FSTYPE,UUID

echo "===== PBS ====="
sudo docker inspect pbs \
  --format 'Running={{.State.Running}} Health={{.State.Health.Status}} Restart={{.HostConfig.RestartPolicy.Name}}'

echo "===== COLA DE CORREOS ====="
sudo /opt/pbs/smart-alerts/pbs-smart-queue status

echo "===== EJECUCIONES DEL WATCHDOG ====="
journalctl -u pbs-storage-watchdog.service -n 20 --no-pager

echo "===== INCIDENTES ====="
journalctl -t pbs-storage-watchdog -n 20 --no-pager
```

Para revisar los avisos pendientes de correo, el comando `status` de la cola solo muestra contadores y no el contenido de los mensajes.

## 7. Limitaciones conocidas

- **No se ha probado la ruta de fallo:** las comprobaciones realizadas corresponden a operación normal; no se ha retirado el SSD ni simulado su pérdida.
- **Posible lectura desde caché:** el comando `stat` puede responder utilizando metadatos en memoria aun cuando el disco físico haya dejado de responder. No sustituye una prueba real de entrada/salida.
- **Estado no persistente:** los indicadores de incidente se almacenan actualmente en `/run` y desaparecen después de reiniciar la Raspberry Pi. La persistencia entre reinicios está pendiente de mejora.
- **Correo dependiente de PBS:** la cola SQLite guarda las alertas, pero las entrega a través del propio contenedor PBS. Al detenerse PBS, un correo CRITICAL puede quedar pendiente hasta que se recupere manualmente el servicio.
- **Encolado no implica recepción:** que un correo se haya procesado no garantiza por sí solo que llegó a Gmail.
- **RECOVERED solo confirma almacenamiento:** no prueba que PBS esté operativo ni que se hayan reanudado los respaldos.
- **Posibles arranques fuera del control de systemd:** reiniciar el contenedor desde Docker u otra herramienta podría evitar la comprobación inicial de `pbs-guard.service`.
- **Dependencia de los eventos de montaje:** `BindsTo=mnt-pbs.mount` reacciona cuando systemd reconoce el cambio de estado, pero no detecta necesariamente todos los fallos físicos de USB.
- **Errores al encolar:** actualmente se registra el error, pero no existe un mecanismo independiente de reintento de la alerta no encolada.
- **Apagado bajo fallas graves de E/S:** el watchdog intenta detener PBS, pero no puede garantizar un apagado limpio si el subsistema de almacenamiento está bloqueado.

## 8. Recuperación manual recomendada

Después de una falla real, revisar primero alimentación, cableado, adaptador USB-SATA y registros del kernel. Confirmar que la partición correcta está montada, que el UUID coincide y que el datastore se puede leer con seguridad. Revisar los eventos del watchdog y el estado del contenedor **antes** de reactivar `pbs-guard.service`.

Una vez recuperado PBS, verificar su salud, el estado de la cola de correos y realizar un respaldo de prueba hacia el datastore. No desconectar deliberadamente el SSD en producción para probar las alertas.

## 9. Relación con otras notificaciones

Las notificaciones habituales de copias de seguridad de Proxmox/PBS y el sistema de alertas SMART existente deben permanecer independientes de este watchdog. La integración reutiliza la cola de correo personalizada; **no requiere modificar las reglas SMART ni la configuración SMTP ya operativa**.

---
Documentación del laboratorio Raspberry Pi / Proxmox Backup Server. Su instalación en otros entornos requiere revisar las rutas, identificadores y mecanismos de recuperación.
