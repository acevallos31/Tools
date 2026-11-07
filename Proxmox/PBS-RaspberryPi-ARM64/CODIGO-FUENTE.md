# Codigo fuente comunitario de PBS ARM64

Proyecto de origen: https://github.com/dockur/proxmox-backup

Esta instalacion **no es el PBS oficial de Proxmox**. Utiliza una imagen comunitaria creada por Dockur para Docker/ARM64. Se debe mantener la atribucion y condiciones de la licencia MIT del proyecto original.

## Revision del codigo fuente inspeccionada

- Repositorio: `dockur/proxmox-backup`.
- Rama por defecto: `master`.
- Ultimo commit consultado al 7 de noviembre de 2026: `cf974879b04c8b71027b1c8b095e8145abd9eb18` (27 de agosto de 2026).
- Revision fija: https://github.com/dockur/proxmox-backup/tree/cf974879b04c8b71027b1c8b095e8145abd9eb18
- Licencia: MIT, https://github.com/dockur/proxmox-backup/blob/cf974879b04c8b71027b1c8b095e8145abd9eb18/license.md
- Archivo Dockerfile: https://github.com/dockur/proxmox-backup/blob/cf974879b04c8b71027b1c8b095e8145abd9eb18/Dockerfile

**Revision vinculada a la imagen instalada:** la etiqueta OCI `org.opencontainers.image.revision` reporta exactamente `cf974879b04c8b71027b1c8b095e8145abd9eb18`. Esto identifica la revision declarada por el constructor de la imagen; no constituye una prueba independiente de reproducibilidad binaria.

## Metadatos OCI observados el 7 de noviembre de 2026

- `org.opencontainers.image.revision`: `cf974879b04c8b71027b1c8b095e8145abd9eb18`
- `org.opencontainers.image.version`: `4.2.8`
- `org.opencontainers.image.source`: `https://github.com/dockur/proxmox-backup`
- `org.opencontainers.image.created`: `2026-10-06T10:56:57.809Z`
- Fecha de construccion Docker: `2026-10-06T11:04:34.553207383Z`
- SO / arquitectura: `linux/arm64`
- Tamano reportado por Docker: `654576393` bytes
- Espacio disponible en NVMe al realizar el inventario: 672 GB

## Imagen instalada identificada

```text
dockurr/proxmox-backup:latest
dockurr/proxmox-backup@sha256:06ee3733387df837a02ff12f476752465e1cd0373071e778ef07da17751cf18e
Image ID: sha256:a0891cf788786ab2721995bf790efcd727aff1b141411f79ac385062541c2346
```

Estos valores fueron obtenidos en la Raspberry Pi. La etiqueta `latest` puede variar con el tiempo, pero el digest permite identificar la imagen esperada. **Se debe comprobar que la imagen esta disponible y que es compatible con ARM64 antes de restaurar.**

## Guardar copia local de la revision fuente (no afecta PBS)

El siguiente procedimiento crea una copia local del repositorio original con historial Git. Requiere `git` y acceso a GitHub, y no toca el contenedor ni el datastore:

```bash
mkdir -p "$HOME/pbs-source-backup"
git clone https://github.com/dockur/proxmox-backup.git "$HOME/pbs-source-backup/proxmox-backup"
git -C "$HOME/pbs-source-backup/proxmox-backup" checkout --detach cf974879b04c8b71027b1c8b095e8145abd9eb18
git -C "$HOME/pbs-source-backup/proxmox-backup" rev-parse HEAD
```

Para preservar el historial Git en un archivo transportable:

```bash
git -C "$HOME/pbs-source-backup/proxmox-backup" bundle create "$HOME/pbs-source-backup/proxmox-backup.bundle" --all
git -C "$HOME/pbs-source-backup/proxmox-backup" bundle verify "$HOME/pbs-source-backup/proxmox-backup.bundle"
```

El bundle contiene el codigo y su historial, **no** la imagen Docker, su sistema de archivos, los respaldos PBS ni los archivos locales de configuracion.

## Respaldar la imagen Docker (privado, fuera de Git)

Cuando haya espacio suficiente y un destino privado confiable, se puede guardar la imagen existente con `docker save`, sin detener el contenedor. **No usar Git para almacenar la imagen ni guardar archivos grandes en el NVMe sin comprobar capacidad disponible.** Un `docker save` puede ocupar varios GB y generar carga de disco. Se realizara posteriormente bajo un procedimiento separado y con espacio verificado.

La imagen Docker y el codigo fuente se deben respaldar por separado de:

1. `/opt/pbs/compose.yml` y configuracion personalizada sin secretos en el repositorio.
2. Configuracion privada `/opt/pbs/config`, incluidos certificados y credenciales bajo copia cifrada.
3. Binario local `V2.0-RC1/proxmox-mail-forward`, que no se encuentra incluido en el repositorio.
4. Datos del datastore en el SSD externo.
5. Scripts SMART y watchdog preservados en este repositorio.

## Pendiente de verificar en el contenedor real

Las etiquetas OCI ya se consultaron y vinculan la revision de origen al commit mencionado. Sigue pendiente guardar una copia fisica y verificarla, ademas de los datos privados y el datastore.

```bash
sudo docker image inspect dockurr/proxmox-backup:latest --format '{{json .Config.Labels}}'
sudo docker image inspect dockurr/proxmox-backup:latest --format 'OS={{.Os}} Architecture={{.Architecture}} Created={{.Created}}'
```
