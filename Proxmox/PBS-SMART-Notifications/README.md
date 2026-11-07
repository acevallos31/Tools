# Alertas SMART y notificaciones PBS (Raspberry Pi)

Documentación del sistema personalizado de alertas SMART para PBS no oficial ARM64. Los cuatro archivos de ejemplo de esta carpeta corresponden al **contenido mostrado en la terminal** el 7 de noviembre de 2026. No constituyen una copia completa del mecanismo de notificaciones.

## Arquitectura

`smartd` -> `/etc/smartmontools/run.d/20pbs-smart` -> `/opt/pbs/smart-alerts/smartd-to-pbs-queued` -> `pbs-smart-queue enqueue` -> SQLite persistente -> `pbs-smart-queue.service`/timer -> contenedor `pbs` -> `/usr/bin/proxmox-mail-forward` modificado -> configuración SMTP de PBS.

- El handler pasa la ruta del mensaje recibido de smartd al adaptador.
- El adaptador crea un mensaje RFC 822 con `To: root@localhost`, lo encola y solicita iniciar el servicio de entrega.
- El timer efectúa reintentos periódicos cada ~60 segundos.
- Un mensaje **encolado** no equivale necesariamente a un correo **entregado**; la prueba de laboratorio mostró un mensaje procesado por el reenviador, pero debe confirmarse la recepción en el buzón.

## Archivos aún pendientes de respaldar

**No se incluyeron estos componentes porque no se dispone aquí de sus contenidos completos o porque son binarios:**

- `/opt/pbs/smart-alerts/pbs-smart-queue`: script Python de 205 líneas, SHA256 `9b343ffe6d145148c3e2d63583214a462a0cf0c8fdc28d523603f238be6d59ba`.
- `/opt/pbs/smart-alerts/versions/V2.0-RC1/proxmox-mail-forward`: **binario** de ~7.2 MB, SHA256 `4664dab7916ba1955a398bf966fa8862aee0edc4411cb8010b1fbc7ef1b58e35`, identificado como bind mount usado por el contenedor.
- `/opt/pbs/smart-alerts/versions/V1.0/proxmox-mail-forward`: binario anterior, SHA256 `a2db207ddf30226eb0be4ad537fc0f563f65a925e54fea7549bc7d2fc468267c`.
- `/opt/pbs/smart-alerts/bin/proxmox-mail-forward`: mismo SHA256 que V1.0.
- `/etc/smartd.conf` y configuración SMART del host, si contiene datos relevantes: requiere revisión y saneamiento.
- La configuración SMTP real de PBS, certificados, credenciales, `notifications-priv.cfg` y el archivo SQLite **no deben publicarse**.

Para respaldar el ejecutable sin publicar un binario opaco se recomienda recuperar su código fuente y proceso de compilación o guardar el artefacto en un repositorio privado con procedencia y versión verificadas.

## Instalación

No aplicar automáticamente en otro servidor. Estos archivos **dependen** del componente Python `pbs-smart-queue`, de un reenviador PBS modificado y de la configuración SMTP. Copiar únicamente los handlers sin ellos romperá las notificaciones.

Rutas de referencia:

| Archivo | Destino |
| --- | --- |
| `20pbs-smart` | `/etc/smartmontools/run.d/20pbs-smart` |
| `smartd-to-pbs-queued` | `/opt/pbs/smart-alerts/smartd-to-pbs-queued` |
| `pbs-smart-queue.service` | `/etc/systemd/system/pbs-smart-queue.service` |
| `pbs-smart-queue.timer` | `/etc/systemd/system/pbs-smart-queue.timer` |

## Verificación sin alterar servicios

```bash
sudo run-parts --test --lsbsysinit /etc/smartmontools/run.d
sudo /opt/pbs/smart-alerts/pbs-smart-queue status
systemctl is-active pbs-smart-queue.timer
systemctl cat pbs-smart-queue.service
sudo docker inspect pbs --format 'Running={{.State.Running}} Health={{.State.Health.Status}}'
```

**Nota de seguridad:** los archivos de esta carpeta no incluyen contraseñas, tokens, certificados ni contenido de mensajes reales. Antes de publicar código adicional, revisar sus secretos por separado sin imprimirlos en la conversación.
