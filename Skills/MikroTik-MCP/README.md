# MikroTik MCP Skill

Herramienta profesional de observabilidad y diagnóstico **read-only** para MikroTik RouterOS mediante Model Context Protocol (MCP).

El proyecto separa tres responsabilidades:

- **Hermes Skill**: procedimiento, selección de herramientas y reglas de interpretación.
- **MCP Server**: contrato tipado, validación, auditoría y resultados estructurados.
- **RouterOS backend**: medición real mediante sesiones SSH administradas.

## Objetivo

Permitir que un agente consulte y diagnostique equipos MikroTik sin entregar al LLM una consola SSH/RouterOS genérica, credenciales ni comandos arbitrarios.

## Superficie MCP

- `mikrotik_devices()`: descubre perfiles locales sin exponer host, usuario ni secretos.
- `mikrotik_status(...)`: salud, interfaces, red, sesión SSH y series temporales.
- `mikrotik_inventory(device)`: inventario completo y análisis determinístico.
- `mikrotik_torch_flows(...)`: flujos de red con RouterOS Torch.
- `mikrotik_full(...)`: inventario completo + Torch; operación costosa y explícita.

### Estado y series temporales

`mikrotik_status` concentra observaciones relacionadas y evita herramientas MCP solapadas:

- `section="health", duration=0`: CPU/RAM/storage/uptime/firmware puntual.
- `section="health", duration>0`: muestreo real de CPU.
- `section="interfaces", duration=0`: estado y contadores acumulados.
- `section="interfaces", interface="ether1", duration>0`: RX/TX actuales mediante RouterOS `monitor-traffic ... once`.
- `section="network"`: IPs, rutas y connection tracking.
- `section="session"`: telemetría de la sesión SSH.
- `chart=true`: para una serie temporal devuelve además un PNG construido a partir de las mismas muestras.

Torch permanece separado porque responde otra pregunta: **quién/qué genera tráfico** (hosts, protocolos, puertos y flujos), no CPU ni ancho de banda temporal de una interfaz.

## Evidencia y análisis

El backend diferencia explícitamente:

- muestra instantánea;
- contador acumulado;
- serie temporal medida;
- captura Torch acotada.

Reglas importantes:

- una muestra de CPU no demuestra carga sostenida;
- RX/TX bytes acumulados no representan ancho de banda actual;
- `link-downs` es histórico;
- Torch no demuestra estabilidad, causalidad ni ausencia de amenazas;
- datos faltantes permanecen desconocidos.

Los promedios, mínimos, máximos y series se calculan en Python; el LLM interpreta los resultados, no inventa las mediciones.

## Seguridad

- Solo lectura.
- Sin `execute_command`, shell, SSH arbitrario o RouterOS CLI libre.
- Parámetros tipados y limitados mediante JSON Schema.
- Torch limitado a 1–30 s.
- Muestreos temporales limitados a 5–120 s y máximo 120 muestras.
- Contraseñas locales protegidas con Windows DPAPI.
- Pin SHA256 opcional de host key SSH por perfil; recomendado/requerido para uso fuera de laboratorio.
- Tool annotations MCP marcan todas las operaciones como read-only/closed-world.
- Auditoría JSONL con argumentos sensibles redactados.

Consulta `SECURITY.md` para el modelo de confianza.

## Observabilidad

Cada llamada MCP pública registra un evento redacted en:

`%APPDATA%\MikroTikSkill\logs\mcp-audit.jsonl`

Incluye correlation ID, herramienta, perfil, parámetros no sensibles, duración, operación backend, resultado y telemetría de sesión. La auditoría está diseñada para permitir un dashboard posterior sin cambiar el contrato MCP.

## Sesiones SSH

Existe una sesión persistente por perfil para evitar repetir handshake/autenticación. El Session Manager:

- reutiliza conexiones vivas;
- reconstruye sesiones muertas antes de una nueva operación;
- cachea el secreto DPAPI solo durante la vida del proceso;
- expone edad/reutilizaciones/estado;
- no reenvía secretos al LLM.

## Hermes companion skill

El skill está en:

`hermes_skill/mikrotik-operator/`

y enseña al modelo:

- intención → herramienta;
- cuándo una consulta exige dato fresco;
- cuándo usar serie temporal;
- cuándo usar Torch;
- cómo interpretar evidencia sin sobreafirmar;
- no reemplazar una capacidad MCP existente con Terminal/subagentes/scripts improvisados.

Instalación:

```powershell
.\scripts\install-hermes-skill.ps1
```

## Instalación Python

El proyecto ya es instalable:

```powershell
python -m pip install -e .
```

También puede ejecutarse durante desarrollo mediante `PYTHONPATH`, pero la instalación editable es la opción preferida.

## Pruebas

Pruebas aisladas:

```powershell
python -m pytest -q -m "not integration and not hardware"
```

Prueba de integración RouterOS aislada, con Docker/QEMU:

```powershell
python -m pytest -q -m integration
```

La suite de integración levanta un RouterOS temporal, inicializa únicamente su credencial de laboratorio y después ejecuta consultas read-only.

GitHub Actions ejecuta la suite rápida en cada PR; el sandbox RouterOS tiene workflow separado.

## Estado de desarrollo

La rama de desarrollo permanece en `0.8.0-dev`. No se aumenta la versión por cada corrección. El siguiente cambio de versión se hará al cerrar un hito probado en sandbox y hardware real.

## Investigación de referencia

`PROFESSIONALIZATION.md` documenta patrones estudiados en proyectos MikroTik/RouterOS MCP existentes y qué decisiones se adoptaron o descartaron.
