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
