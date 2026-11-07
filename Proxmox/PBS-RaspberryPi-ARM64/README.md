# Proxmox Backup Server en Raspberry Pi 5 (ARM64, Docker)

Registro de la instalación **no oficial** de PBS observada el 7 de noviembre de 2026.

## Componentes conocidos

| Parámetro | Valor observado |
| --- | --- |
| Sistema | Raspberry Pi, Linux `aarch64`, tamaño de página 4096 |
| Imagen | `dockurr/proxmox-backup:latest` |
| Imagen SHA256 local | `a0891cf788786ab2721995bf790efcd727aff1b141411f79ac385062541c2346` |
| Digest reportado | `dockurr/proxmox-backup@sha256:06ee3733387df837a02ff12f476752465e1cd0373071e778ef07da17751cf18e` |
| Contenedor | `pbs` |
| Estado de salud observado | `healthy` |
| Compose original | `/opt/pbs/compose.yml` |
| Configuración persistente | `/opt/pbs/config` -> `/etc/proxmox-backup` |
| Datastore persistente | `/mnt/pbs/datastore` -> `/var/lib/proxmox-backup` |
| Reenviador SMTP personalizado | `/opt/pbs/smart-alerts/versions/V2.0-RC1/proxmox-mail-forward` -> `/usr/bin/proxmox-mail-forward` |
| SSD datastore | ADATA SU650, ext4, UUID `004f411f-b58d-4c99-bbe9-d8d55f178fff` |

**Importante:** la imagen comunitaria de Docker no es el instalador oficial de Proxmox. Proyecto de referencia: https://github.com/dockur/proxmox-backup

## Qué conserva este directorio

- Inventario técnico y digest de la imagen observada (para evitar depender exclusivamente de `latest`).
- Relación con el watchdog y los scripts SMART personalizados.
- Identificación de los datos que deben respaldarse por separado.

## Qué falta para una copia completa y reproducible

1. Copia **saneada** de `/opt/pbs/compose.yml`. No publicar el original: previamente contenía una variable `PASSWORD`.
2. Código completo de `pbs-smart-queue` y código fuente / construcción reproducible del reenviador modificado.
3. Configuración de servicios systemd, montaje SSD por UUID y smartd, sin información sensible.
4. Respaldo privado de `/opt/pbs/config`, secretos, certificados y demás archivos necesarios para recuperar la identidad de PBS.
5. Respaldo independiente del **datastore** con los datos de copias de seguridad.
6. Copia del código fuente del proyecto comunitario, preservando procedencia/licencia y preferentemente un commit o etiqueta exacta. El digest de imagen no reemplaza el código fuente ni la copia física de la imagen.

No se ha reconstruido desde cero el sistema usando este directorio; este documento **no garantiza una restauración completa**.

## Verificación

```bash
uname -m
sudo docker inspect pbs --format 'Image={{.Config.Image}} ImageID={{.Image}}'
sudo docker image inspect dockurr/proxmox-backup:latest --format '{{json .RepoDigests}}'
sudo docker inspect pbs --format 'Running={{.State.Running}} Health={{.State.Health.Status}}'
```

## Seguridad

Nunca subir archivos de `/opt/pbs/config` sin saneamiento exhaustivo. Evitar especialmente `notifications-priv.cfg`, `token.shadow`, contraseñas del Compose, credenciales, certificados, bases SQLite y los datos de respaldo de PBS. Las copias privadas deben mantenerse cifradas y fuera del repositorio público.
