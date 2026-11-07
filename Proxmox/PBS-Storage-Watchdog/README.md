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
| `10-incident-lock.conf` | `/etc/systemd/system/pbs-guard.service.d/10-incident-lock.conf` | Bloquea el arranque protegido si existe `critical.lock` |
| `10-timeout.conf` | `/etc/systemd/system/pbs-storage-watchdog.service.d/10-timeout.conf` | Amplía el tiempo máximo del watchdog a 360 segundos |
| `pbs-storage-recover` | `/usr/local/sbin/pbs-storage-recover` | Diagnóstico `--check` y recuperación supervisada `--recover` (ruta de fallo todavía no probada) |

El script verifica el UUID del montaje, el enlace persistente `/dev/disk/by-id`, la presencia del directorio `.chunks` y un `stat` con tiempo de espera.

## 3. Comportamiento previsto

1. **Almacenamiento disponible:** el watchdog termina sin alterar PBS.
2. **Primera comprobación fallida — WARNING:** registra el problema e intenta encolar un correo preventivo.
3. **Segunda comprobación fallida — CRITICAL:** registra y encola la alerta crítica; intenta detener `pbs-guard.service` y el contenedor Docker `pbs`.
4. **Falla persistente o reinicio de la Raspberry Pi:** conserva el bloqueo crítico en el NVMe para impedir el arranque mediante `pbs-guard.service` hasta una revisión manual.
5. **Almacenamiento nuevamente disponible — RECOVERED:** encola un aviso de recuperación del **SSD** una sola vez mediante `recovered.notified`, pero **no elimina `critical.lock` ni inicia PBS automáticamente**.

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
- **Estado parcialmente persistente:** `critical.lock` y `recovered.notified` permanecen en `/var/lib/pbs-storage-watchdog` (NVMe); el marcador del primer fallo continúa en `/run` y se reinicia al arrancar. No existe todavía un procedimiento automatizado y validado para levantar el bloqueo.
- **Correo dependiente de PBS:** la cola SQLite guarda las alertas, pero las entrega a través del propio contenedor PBS. Al detenerse PBS, un correo CRITICAL puede quedar pendiente hasta que se recupere manualmente el servicio.
- **Encolado no implica recepción:** que un correo se haya procesado no garantiza por sí solo que llegó a Gmail.
- **RECOVERED solo confirma almacenamiento:** no prueba que PBS esté operativo ni que se hayan reanudado los respaldos.
- **Posibles arranques fuera del control de systemd:** reiniciar el contenedor desde Docker u otra herramienta podría evitar la comprobación inicial de `pbs-guard.service`.
- **Dependencia de los eventos de montaje:** `BindsTo=mnt-pbs.mount` reacciona cuando systemd reconoce el cambio de estado, pero no detecta necesariamente todos los fallos físicos de USB.
- **Errores al encolar:** actualmente se registra el error, pero no existe un mecanismo independiente de reintento de la alerta no encolada.
- **Apagado bajo fallas graves de E/S:** el watchdog intenta detener PBS, pero no puede garantizar un apagado limpio si el subsistema de almacenamiento está bloqueado.

## 8. Recuperación manual recomendada

Después de una falla real, revisar primero alimentación, cableado, adaptador USB-SATA y registros del kernel. Confirmar que la partición correcta está montada, que el UUID coincide y que el datastore se puede leer con seguridad. Revisar los eventos del watchdog y el estado del contenedor **antes** de reactivar `pbs-guard.service`.

**El archivo `critical.lock` debe liberarse únicamente tras confirmar la salud del SSD y el datastore, y siguiendo un procedimiento de recuperación manual aprobado.** No se debe eliminar para forzar un arranque sin investigar el incidente. El bloqueo protege el arranque mediante `pbs-guard.service`, pero un arranque directo con Docker puede eludirlo.

Una vez recuperado PBS, verificar su salud, el estado de la cola de correos y realizar un respaldo de prueba hacia el datastore. No desconectar deliberadamente el SSD en producción para probar las alertas.

## 9. Relación con otras notificaciones

Las notificaciones habituales de copias de seguridad de Proxmox/PBS y el sistema de alertas SMART existente deben permanecer independientes de este watchdog. La integración reutiliza la cola de correo personalizada; **no requiere modificar las reglas SMART ni la configuración SMTP ya operativa**.

## 10. Estado de la mejora de persistencia (7 de noviembre de 2026)

El directorio `/var/lib/pbs-storage-watchdog` fue creado como `root:root` con permisos `700` sobre el NVMe raíz (`/dev/nvme0n1p2`). Se añadieron los dos *drop-ins* de systemd incluidos en esta carpeta y se instaló la lógica persistente del watchdog. Con el SSD disponible se verificó sintaxis válida, temporizadores activos, PBS `healthy` y directorio sin bloqueos críticos.

**Pendiente:** prueba controlada sin interrumpir servicios que confirme la lógica de incidente, la persistencia real tras reinicios, los envíos de alarma bajo fallo y la liberación manual segura. La rama de recuperación supervisada solo se ha probado hasta su rechazo sin incidente. Los archivos de este PR son copia de referencia; publicarlos aquí no los despliega automáticamente a la Raspberry Pi.

---
Documentación del laboratorio Raspberry Pi / Proxmox Backup Server. Su instalación en otros entornos requiere revisar las rutas, identificadores y mecanismos de recuperación.

## 11. Diagnóstico previo a recuperación

Se instaló `pbs-storage-recover --check` y se verificó en condiciones normales: comprueba el dispositivo persistente, UUID, tipo de sistema de archivos, origen real del montaje, directorio `.chunks` y una lectura directa de 4096 bytes. También informa si existe `critical.lock`.

```bash
sudo /usr/local/sbin/pbs-storage-recover --check
```

**El modo `--recover` ya está instalado, pero no se ha ensayado con un incidente crítico real ni simulado.** Se verificó que, sin `critical.lock`, responde `ERROR: No critical incident to recover` con código 1, y deja PBS activo y sin cambios. Con incidente crítico exige root, bloqueo de concurrencia, SSD validado, PBS detenido, confirmación interactiva `RECOVER-PBS`, archivo de incidente archivado y arranque mediante `pbs-guard.service`. La lectura directa es una comprobación básica, no certifica la integridad total del SSD ni de los respaldos.

**Advertencia pendiente:** si el arranque falla o PBS no se vuelve `healthy`, la versión actual restaura `critical.lock`, pero puede dejar un contenedor iniciado o un servicio activo. Antes de utilizar `--recover` en un incidente real, se debe corregir y verificar la parada de PBS cuando falle la comprobación de salud; no se debe asumir que restaurar el archivo por sí solo detiene un contenedor.
