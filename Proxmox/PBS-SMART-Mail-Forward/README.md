# Proxmox Backup Server — SMART mail-forward ARM64

## Estado
Investigación y compilación aislada. **No está desplegado ni probado con PBS de producción.**

PBS 4.2.8 ARM64 ejecutado en Docker en Raspberry Pi 5. El host Debian ejecuta un único `smartd` y supervisa `/dev/nvme0` (Micron) y `/dev/sda` (ADATA USB/SAT). El contenedor PBS ya puede mostrar SMART. El endpoint `smtp-pbs-alerts` de PBS envió correctamente un correo de prueba a Gmail.

La imagen actual **no incluye** `proxmox-mail-forward`, y ni host ni contenedor disponen de `/usr/bin/mail`. El script del host `/opt/pbs/smart-alerts/pbs-smart-forward` está creado, pero **no debe activarse todavía**.

## Construcción

Workflow manual: `.github/workflows/build-proxmox-mail-forward-arm64.yml`. Usa un runner hospedado ARM64, obtiene el código fuente oficial de `proxmox/proxmox-mail-forward`, compila Rust y publica un artifact descargable por 14 días.

1. GitHub → Actions → **Build Proxmox Mail Forward ARM64** → Run workflow, seleccionando esta rama.
2. Revisar logs: resultado de Cargo, arquitectura aarch64, listado `ldd`, SHA256 y commit exacto de origen.
3. Descargar artifact únicamente para evaluación. **No copiar ni ejecutar en PBS automáticamente.**

### Compatibilidad que falta validar

La versión upstream de `proxmox-mail-forward` puede usar una revisión de las librerías `proxmox-notify` distinta de la integrada en PBS 4.2.8. Se necesita inspeccionar sus dependencias dinámicas y comprobar el comportamiento real con configuraciones de prueba antes de producción. El workflow usa `cargo --locked`: si upstream no aporta un Cargo.lock o el lock no resuelve correctamente, la ejecución fallará deliberadamente; no se omite la verificación sin revisar las dependencias.

### Diseño de integración previsto (no desplegado)

`smartd` (host) → `smartd-runner` → puente del host → `docker exec -i pbs proxmox-mail-forward` → matcher `pbs-important-alerts` → destino `smtp-pbs-alerts` → Gmail.

La ruta anterior **no está validada de extremo a extremo**. El helper oficial puede requerir entorno y rutas específicas del servicio de correo; probarlo primero con mensaje sintético y sin incluir credenciales en logs.

Antes de activar:
- Validar y fijar por SHA una revisión fuente compatible; documentar dependencias, licencias y hashes.
- Empaquetar el ejecutable en una imagen derivada o montaje persistente **solo después** de prueba de compatibilidad.
- Revisar el script `pbs-smart-forward`: actualmente exige el ejecutable en `/usr/bin/proxmox-mail-forward`; asegurar que reciba un mensaje MIME válido y que los errores queden registrados.
- Configurar invocación desde `smartd-runner`, sustituyendo o inhabilitando el `10mail` fallido, evitando duplicados y revisando permisos.
- Ensayar alerta sintética, verificar la llegada a Gmail, probar fallo de contenedor y una eventual recreación.
- No reiniciar, desmontar discos ni ejecutar tests SMART destructivos durante la preparación.

## Riesgos

No introducir contraseñas SMTP en repositorio ni registrar `notifications-priv.cfg`. Las capacidades `SYS_ADMIN` y `SYS_RAWIO` de PBS ya concedidas tienen implicaciones de seguridad; evaluar el mínimo privilegio posteriormente. No sobreescribir `/opt/pbs/compose.yml` de producción en este workflow.

## Primera compilación en GitHub Actions

Run [38621684016](https://github.com/acevallos31/Tools/actions/runs/38621684016), job 116050525231: **falló en `cargo generate-lockfile`**, antes de compilar. El runner redirigía `crates-io` a `/usr/share/cargo/registry`, que no existía (`failed to query replaced source registry`). El workflow de la rama de pruebas fue modificado para preparar `$HOME/.cargo/config.toml` con el registro público crates.io; **requiere una nueva ejecución manual**, no `Re-run failed jobs` sobre el commit antiguo. Aún no se ha verificado que esta corrección resuelva toda la compilación.

## Tercer intento: dependencia interna no publicada

Ejecución [38622558033](https://github.com/acevallos31/Tools/actions/runs/38622558033): la eliminación del reemplazo Debian de Cargo permitió acceder a crates.io, pero falló porque `proxmox-http` no está publicado allí. Según la documentación de [proxmox-rs](https://github.com/proxmox/proxmox-rs), la forma de compilar fuera del repositorio oficial es referenciar **todos** sus crates mediante `[patch.crates-io]`. El workflow ahora obtiene dos revisiones fijadas por SHA: mail-forward `9890c29a3d3da04262fe5564b2321be59928de5e` y proxmox-rs `89c1d597a9d15743049eadcb1add380573265904`, genera los parches locales, resuelve dependencias públicas desde crates.io y conserva ambos SHA y el Cargo.lock en el artifact. **No se ha ejecutado todavía esta versión corregida.**

## Cuarto intento: error del enlazador ARM64

En la [ejecución 38623313190](https://github.com/acevallos31/Tools/actions/runs/38623313190), Cargo descargó y compiló las dependencias, incluidas `proxmox-notify`, `proxmox-http` y el proyecto principal, pero el enlace final falló con `/usr/bin/ld: cannot find -luuid`. La causa es la ausencia del paquete de desarrollo `uuid-dev` en el runner, no una incompatibilidad demostrada con ARM64. El workflow ahora instala `uuid-dev`, verifica `pkg-config uuid/openssl`, inspecciona la arquitectura ELF y falla cuando `ldd` encuentra bibliotecas ausentes. **No se ha ejecutado aún el workflow corregido.**

## Quinta ejecución: compilación exitosa (pendiente de despliegue)
- Run: [38623764393](https://github.com/acevallos31/Tools/actions/runs/38623764393)
- Job: 116057594625
- Artifact: [proxmox-mail-forward-linux-arm64](https://github.com/acevallos31/Tools/actions/runs/38623764393/artifacts/11922951805)
- Estado: **success** tras instalar `uuid-dev`, que resuelve el error previo `cannot find -luuid`.
- El comando `file` confirmó ELF64 AArch64; `readelf` confirmó `Machine: AArch64`. En el runner `ldd` resolvió `libssl.so.3`, `libcrypto.so.3`, `libuuid.so.1`, `libc.so.6`, `libgcc_s.so.1` y `libm.so.6`, sin bibliotecas ausentes.
- Incluye revisiones upstream, lockfile, bibliotecas dinámicas y checksum del ejecutable.
- **Sin validar**: compatibilidad de bibliotecas de runtime dentro de la imagen Docker PBS 4.2.8 en Debian Trixie y entrega de email `system-mail` real mediante `smtp-pbs-alerts`.
- El upstream `src/main.rs` captura errores de notificación, los registra y puede salir con estado 0 incluso sin entrega; verificar **recepción real** en Gmail en la prueba sintética, sin fiarse solo del exit code.
- No copiar a `/usr/bin` directamente ni activar el `smartd-runner` hasta resolver compatibilidad, persistencia y plan de rollback.

## Validación real — 14 de octubre de 2026

- Raspberry Pi ARM64 con PBS 4.2.8-1 en contenedor Docker `pbs`: todas las dependencias de `proxmox-mail-forward` resolvieron mediante `ldd` y `ldd -r`; contenedor en estado `healthy`.
- Artefacto descargado desde GitHub Actions: SHA256 del ZIP y del tarball correctos; binario ELF AArch64 de aproximadamente 6.9 MB verificado mediante el `SHA256SUMS` incluido.
- Binario copiado **temporalmente** a `pbs:/tmp/proxmox-mail-forward` (no persistente).
- Prueba manual: un mensaje MIME sintético con asunto `[PRUEBA SMART] Raspberry Pi 5 - PBS` fue inyectado mediante `docker exec -i pbs /tmp/proxmox-mail-forward`.
- **Recepción confirmada por captura en Gmail**: remitente `Proxmox Backup Server - pbs`, asunto y cuerpo del mensaje correctos; se reutilizó el destino SMTP previamente configurado en PBS.
- Esta validación no activa las alertas automáticas de `smartd`: aún falta persistir el binario fuera del contenedor, montarlo de manera segura y enlazarlo con el runner en el host, con rollback y prueba sintética extremo a extremo.
- El puente `/opt/pbs/smart-alerts/pbs-smart-forward` actualmente requiere `/usr/bin/proxmox-mail-forward` en el contenedor, por lo que no funcionará hasta configurar el montaje persistente hacia esa ruta.
- No asumir que las advertencias quedan cubiertas solo por SMTP: antes de habilitar alertas reales, validar si el matcher de PBS acepta el tipo `system-mail` y si existen filtros o exclusiones relevantes.
