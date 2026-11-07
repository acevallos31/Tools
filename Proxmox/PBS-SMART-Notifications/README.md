# Alertas SMART y notificaciones PBS (Raspberry Pi)

Documentación del sistema personalizado de alertas SMART para PBS no oficial ARM64. Los archivos de texto de esta carpeta reproducen el **contenido mostrado en la terminal** el 7 de noviembre de 2026. La cola SQLite Python ya está incluida; el reenviador auxiliar ya está incluido; todavía falta el ejecutable personalizado. No constituyen una copia completa del mecanismo de notificaciones.

## Arquitectura

`smartd` -> `/etc/smartmontools/run.d/20pbs-smart` -> `/opt/pbs/smart-alerts/smartd-to-pbs-queued` -> `pbs-smart-queue enqueue` -> SQLite persistente -> `pbs-smart-queue.service`/timer -> contenedor `pbs` -> `/usr/bin/proxmox-mail-forward` modificado -> configuración SMTP de PBS.

- El handler pasa la ruta del mensaje recibido de smartd al adaptador.
- El adaptador crea un mensaje RFC 822 con `To: root@localhost`, lo encola y solicita iniciar el servicio de entrega.
- El timer efectúa reintentos periódicos cada ~60 segundos.
- Un mensaje **encolado** no equivale necesariamente a un correo **entregado**; la prueba de laboratorio mostró un mensaje procesado por el reenviador, pero debe confirmarse la recepción en el buzón.

## Archivos aún pendientes de respaldar

**No se incluyeron estos componentes porque no se dispone aquí de sus contenidos completos o porque son binarios:**

- `/opt/pbs/smart-alerts/pbs-smart-forward`: **respaldado** en esta carpeta, hash SHA256 reportado por la Raspberry Pi `b1277aedad9275abb259138a2dec2dd3e8098077295ea0427da1ef1b4490d34a`.
- `/opt/pbs/smart-alerts/versions/V2.0-RC1/proxmox-mail-forward`: **binario** de ~7.2 MB, SHA256 `4664dab7916ba1955a398bf966fa8862aee0edc4411cb8010b1fbc7ef1b58e35`, identificado como bind mount usado por el contenedor.
- `/opt/pbs/smart-alerts/versions/V1.0/proxmox-mail-forward`: binario anterior, SHA256 `a2db207ddf30226eb0be4ad537fc0f563f65a925e54fea7549bc7d2fc468267c`.
- `/opt/pbs/smart-alerts/bin/proxmox-mail-forward`: mismo SHA256 que V1.0.
- `/etc/smartd.conf` y configuración SMART del host, si contiene datos relevantes: requiere revisión y saneamiento.
- La configuración SMTP real de PBS, certificados, credenciales, `notifications-priv.cfg` y el archivo SQLite **no deben publicarse**.

El binario activo V2.0-RC1 se identifica como ELF de 64 bits para ARM aarch64, enlazado dinámicamente, no despojado de símbolos y con Build ID SHA1 `ef1d7ff728463dce64d414a2c82bc6d4359dee94`. Este ejecutable no ha sido copiado al repositorio. El 7 de noviembre de 2026 se creó una copia local en `/opt/pbs/image-backup/proxmox-mail-forward-V2.0-RC1-arm64`; `cmp` confirmó identidad con el original, con SHA256 `4664dab7916ba1955a398bf966fa8862aee0edc4411cb8010b1fbc7ef1b58e35`. La copia está en el mismo NVMe que la fuente: **todavía falta una copia externa privada**.

Para respaldar el ejecutable sin publicar un binario opaco se recomienda recuperar su código fuente y proceso de compilación o guardar el artefacto en un repositorio privado con procedencia y versión verificadas.

## Cola SQLite incluida

Se incorporó `pbs-smart-queue`, script Python de **205 líneas y 7865 bytes**, con SHA256 informado por la Raspberry Pi: `9b343ffe6d145148c3e2d63583214a462a0cf0c8fdc28d523603f238be6d59ba`. Implementa `enqueue`, `run` y `status`, cola SQLite en modo WAL y transacciones persistentes, reintentos con espera exponencial, límites de cantidad/tamaño y validación del protocolo `checked-delivery-v1`. El contenido publicado tiene el mismo tamaño que el script original mostrado por el usuario; se recomienda comparar el SHA256 tras descargarlo a la Raspberry Pi para verificar identidad binaria completa.

## Instalación

No aplicar automáticamente en otro servidor. Estos archivos **dependen** del componente Python `pbs-smart-queue` incluido, de un reenviador PBS modificado y de la configuración SMTP. Copiar únicamente los handlers sin ellos romperá las notificaciones.

Rutas de referencia:

| Archivo | Destino |
| --- | --- |
| `20pbs-smart` | `/etc/smartmontools/run.d/20pbs-smart` |
| `smartd-to-pbs-queued` | `/opt/pbs/smart-alerts/smartd-to-pbs-queued` |
| `pbs-smart-queue` | `/opt/pbs/smart-alerts/pbs-smart-queue` (root:root, modo 750) |
| `pbs-smart-forward` | `/opt/pbs/smart-alerts/pbs-smart-forward` |
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
