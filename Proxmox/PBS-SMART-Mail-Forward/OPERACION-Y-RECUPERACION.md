# Operación y recuperación — SMART → PBS → Gmail (Raspberry Pi 5)

**Alcance:** Debian 12 en Raspberry Pi 5; `smartd` supervisa Micron 2400A NVMe y ADATA SU650 SATA; contenedor `pbs` con configuración persistente en `/opt/pbs/compose.yml`. Validado con mensajes sintéticos y recepción confirmada en Gmail el **14 de octubre de 2026**.

## 1. Comprobación rutinaria (solo lectura)

```bash
sudo systemctl is-active smartmontools
sudo systemctl status smartmontools --no-pager -l
sudo smartctl --scan
sudo run-parts --test --lsbsysinit /etc/smartmontools/run.d
sudo docker inspect pbs --format 'PBS={{.State.Status}} Salud={{.State.Health.Status}}'
sudo docker inspect pbs --format '{{range .Mounts}}{{if eq .Destination "/usr/bin/proxmox-mail-forward"}}Origen={{.Source}} SoloLectura={{not .RW}}{{end}}{{end}}'
sudo docker compose -p pbs -f /opt/pbs/compose.yml config --quiet
findmnt /mnt/pbs
```

Esperado: `smartmontools` activo, **2 dispositivos** en el estado de systemd, `20pbs-smart` activo, PBS `running/healthy`, helper montado desde `/opt/pbs/smart-alerts/bin` en modo solo lectura, datastore `/mnt/pbs` operativo. `smartctl --scan` por sí solo demuestra detección SMART, no configuración activa de `smartd`: comprobar también `systemctl status smartmontools`.

### Registros

```bash
sudo journalctl -u smartmontools --since '24 hours ago' --no-pager
sudo journalctl -b -t smartd --no-pager
sudo docker logs --since 30m pbs
```

La ausencia de entradas recientes no es prueba de fallo; pueden existir rotaciones del journal. No deshabilitar el registro local. Para revisar la salud SMART física, consultar `sudo smartctl -a /dev/nvme0` y `sudo smartctl -a -d sat /dev/sda` sin iniciar tests ni operaciones de escritura; respetar el estado/uso del adaptador USB.

## 2. Prueba sintética sin provocar fallos físicos

La ruta más representativa es el runner original de Debian, que entrega a `20pbs-smart` el archivo de mensaje temporal. Ejecutar en el **host Raspberry**:

```bash
printf '%s\n' \
  'SMARTD - PRUEBA SINTETICA' \
  'Servidor: Raspberry Pi 5' \
  'Dispositivo: /dev/sda' \
  'NO existe ninguna falla real en los discos.' |
sudo env SMARTD_SUBJECT='[PRUEBA FINAL SMARTD] Raspberry Pi 5' \
  /usr/share/smartmontools/smartd-runner
```

**Comprobar recepción real en Gmail**. El exit code por sí solo no demuestra entrega SMTP. No activar pruebas destructivas, reiniciar discos o simular degradación de estado SMART. El notificador de PBS previamente configurado se llama `smtp-pbs-alerts`; el matcher conocido es `pbs-important-alerts`.

## 3. Rutas y estructura operativa

```text
/etc/smartd.conf                                 configuración de smartd (sin cambios)
/usr/share/smartmontools/smartd-runner             lanzador Debian
/etc/smartmontools/run.d/20pbs-smart               notificador ejecutable
/etc/smartmontools/run.d/10mail                    original sin bit de ejecución
/opt/pbs/smart-alerts/10mail.original              copia original
/opt/pbs/smart-alerts/smartd-to-pbs                normaliza cuerpo/asunto de smartd
/opt/pbs/smart-alerts/pbs-smart-forward            conexión al contenedor
/opt/pbs/smart-alerts/bin/proxmox-mail-forward     binario ARM64 firmado por SHA256
/opt/pbs/compose.yml                               Compose de mantenimiento
/opt/pbs/compose.smart-mail.override.yml           histórico; no necesario en despliegues futuros
/opt/pbs/compose.yml.backup-20261014-144827        respaldo previo a consolidación
```

SHA256 correcto del binario: `a2db207ddf30226eb0be4ad537fc0f563f65a925e54fea7549bc7d2fc468267c`.

```bash
sudo sha256sum /opt/pbs/smart-alerts/bin/proxmox-mail-forward
sudo docker exec pbs sha256sum /usr/bin/proxmox-mail-forward
```

El montaje declarado en `/opt/pbs/compose.yml`:

```yaml
- type: bind
  source: /opt/pbs/smart-alerts/bin/proxmox-mail-forward
  target: /usr/bin/proxmox-mail-forward
  read_only: true
```

Otros dos volúmenes existentes, **no modificar ni desmontar**:

- `/opt/pbs/config:/etc/proxmox-backup`
- `/mnt/pbs/datastore:/var/lib/proxmox-backup`

## 4. Mantenimiento y futuras actualizaciones de PBS

- Usar el **Compose principal**: `-f /opt/pbs/compose.yml`. No omitirlo ni sustituirlo por archivos históricos. El archivo de override ya está consolidado en el principal.
- Antes de recrear/actualizar, revisar que no haya tareas activas y que el datastore esté montado:
  ```bash
  sudo docker exec pbs proxmox-backup-manager task list --output-format json-pretty
  findmnt /mnt/pbs
  sudo docker compose -p pbs -f /opt/pbs/compose.yml config --quiet
  ```
  Esperar a que termine cualquier tarea; comprobar ventanas de respaldo programadas. El resultado `[]` indica que no hay tareas activas en ese instante; comprobar nuevamente inmediatamente antes de intervenir.
- Crear copia de seguridad del Compose **antes** de modificarlo; resguardar configuración y scripts del host según política local, **fuera de repositorios públicos** cuando contengan secretos.
- Solo en una ventana aprobada, con PBS inactivo en tareas, aplicar cambios con Compose. Ejemplo para operación controlada, **no ejecutarlo como validación rutinaria**:
  ```bash
  cd /opt/pbs
  sudo docker compose -p pbs -f compose.yml up -d --no-deps --no-build --pull never --wait --wait-timeout 120 pbs
  ```
- Después verificar `running/healthy`, los **3** montajes, `/mnt/pbs`, las tareas PBS y repetir una alerta sintética con recepción Gmail.
- La política Docker actual es `unless-stopped`; un reinicio del host no requiere recrear Compose para restaurar un montaje ya creado.

## 5. Recuperación / rollback por niveles

### A. Desactivar solo correos SMART (sin reiniciar PBS)

```bash
sudo chmod a-x /etc/smartmontools/run.d/20pbs-smart
sudo run-parts --test --lsbsysinit /etc/smartmontools/run.d
```

Esto **no detiene** la monitorización SMART ni la generación local de logs; suspende el envío de correos mediante este script. Para reactivar:

```bash
sudo chmod 755 /etc/smartmontools/run.d/20pbs-smart
sudo run-parts --test --lsbsysinit /etc/smartmontools/run.d
```

**No** reactivar `10mail` mientras `/usr/bin/mail` no exista; el notificador original fallaría. Evitar habilitar simultáneamente dos notificadores salvo que se busque expresamente duplicar correos.

### B. Si PBS está inaccesible

```bash
sudo docker inspect pbs --format 'Estado={{.State.Status}} Salud={{.State.Health.Status}}'
sudo docker logs --since 30m pbs
sudo docker exec pbs test -x /usr/bin/proxmox-mail-forward && echo helper-OK
sudo docker compose -p pbs -f /opt/pbs/compose.yml config --quiet
```

No cambiar contraseñas ni editar `notifications-priv.cfg` para diagnosticar una caída sin tener evidencias. Comprobar el destino SMTP de PBS mediante la interfaz administrativa. Si el contenedor está parado, el script del host devuelve error: **no hay reintentos persistentes**.

### C. Volver al Compose anterior (solo si resulta estrictamente necesario)

El respaldo `/opt/pbs/compose.yml.backup-20261014-144827` contiene la configuración previa al montaje consolidado. Recuperarlo implicaría **eliminar la persistencia del helper**, por lo que la ruta SMART → Gmail dejaría de funcionar tras recreación. No aplicar mientras haya backups activos ni de forma automática; validar diferencias, preservar respaldo del Compose actual y planificar ventana de mantenimiento. Si se retira el montaje, desactivar primero `20pbs-smart` para evitar mensajes de fallo repetidos.

## 6. Seguridad, limitaciones y pendientes

- El ejecutable ARM64 está en el host con propietario `root:root`, modo `0755`, montado solo lectura. **No** asignar setuid.
- El helper reutiliza la configuración interna de notificaciones de PBS; no requiere otro usuario SMTP ni contraseñas en los scripts. No publicar `notifications-priv.cfg` ni secretos de la configuración Docker.
- `proxmox-mail-forward` puede finalizar con estado 0 incluso cuando el envío falla: verificar Gmail; revisar logs de PBS si no llega.
- Se probó un mensaje sintético; **no** se provocó un evento físico real. La monitorización real de ambos dispositivos aparece activa en systemd.
- Sin mecanismo de cola local ni reintentos: una alerta emitida durante caída de PBS/SMTP puede no entregarse. Mejora futura: cola segura + retry/backoff y prueba controlada de indisponibilidad.
- Las notificaciones de tipo `info` dependen de filtros de PBS; no modificar el matcher para resolver alertas SMART sin analizar previamente el efecto en el resto de notificaciones.
- Cambios bajo PR [#4](https://github.com/acevallos31/Tools/pull/4), rama `feat/pbs-smart-mail-forward-arm64`; **mantener draft, sin merge a main** hasta aprobación.
