# Validation Plan - MikroTik MCP

Este documento define las puertas de aceptación para la rama `feat/mikrotik-granular-tools`.

**No hacer merge a `main` hasta completar las cuatro etapas.**

## Gate 1 - pruebas aisladas y contrato MCP

Ejecutar:

```powershell
cd Skills\MikroTik-MCP
python -m pip install -r requirements-dev.txt
python -m pip install -e . --no-deps
python -m compileall -q mikrotik_skill
python -c "from mikrotik_skill.mcp_server import server; print(len(server._tool_manager.list_tools()))"
python -m pytest -q -m "not integration and not hardware"
```

Criterios:

- compile sin errores;
- servidor registra exactamente 5 tools;
- suite unitaria/contrato MCP verde;
- `mikrotik_devices` no expone host/username;
- series CPU/interfaz respetan la duración solicitada;
- `duration=120, interval=1` es válido y no supera 120 muestras;
- cada reading temporal contiene `timestamp` UTC y `elapsed_seconds`;
- Torch no deriva su target desde la IP/hostname de administración.

GitHub Actions: workflow `MikroTik MCP tests`.

## Gate 2 - sandbox RouterOS

Workflow:

`.github/workflows/mikrotik-mcp-integration.yml`

### CI autoritativo

GitHub Actions ejecuta RouterOS CHR **7.24.4 oficial** directamente con QEMU/KVM:

1. descarga `chr-7.24.4.vdi.zip` desde MikroTik;
2. convierte VDI a qcow2;
3. inicia `qemu-system-x86_64` con KVM cuando está disponible;
4. publica únicamente SSH hacia `127.0.0.1:9122`;
5. el fixture espera el banner SSH, inicializa una contraseña temporal y ejecuta las pruebas read-only.

Este diseño sigue el patrón probado por `tikoci/restraml` para ejecutar CHR dentro de GitHub-hosted runners y elimina la dependencia del CI en imágenes RouterOS de terceros.

### Ejecución local

Cuando no se proporcionan las variables `MIKROTIK_SANDBOX_*`, el fixture puede usar Docker + Docker Compose:

```powershell
cd Skills\MikroTik-MCP
python -m pytest -q -m integration
```

El fallback local usa `tests/integration/docker-compose.routeros.yml` con dos redes y la imagen upstream `evilfreelancer/docker-routeros:latest`. Esa ruta sirve para desarrollo local; la validación de versión exacta del gate es la ejecución QEMU del CI y posteriormente el hardware real.

### Historial de diagnóstico

- run #5 / commit `502dffec1040ff5934d281deff471d5dbed5cead`: el fixture Testcontainers de una sola red no recibió banner SSH. El entrypoint upstream mueve `eth0` al bridge interno cuando no existe `eth1`, por lo que el port publishing no era una base confiable;
- run #6 / commit `50d5190b17469cf1f62b3489169bc001a0f6dd67`: la topología de dos redes ya estaba preparada, pero Docker Hub no publicó `evilfreelancer/docker-routeros:7.24.4`; el run falló inmediatamente con `manifest unknown` antes de arrancar RouterOS;
- a partir del siguiente run, el CI usa CHR 7.24.4 oficial con QEMU directo. Si falla el arranque, se conservan el log de QEMU, PID/proceso y listener SSH.

Criterios:

- CHR reporta RouterOS 7.24.4 en CI;
- SSH del sandbox disponible;
- inventario health real parseable;
- CPU temporal real con valores 0–100;
- `actual_duration_seconds >= requested_duration_seconds`;
- interfaz `ether1` medible mediante `/interface monitor-traffic ether1 once`;
- tasas RX/TX no negativas;
- no se usan comandos RouterOS arbitrarios desde el MCP.

Si este gate falla, no continuar a hardware real hasta clasificar si el fallo es código, CHR/QEMU o infraestructura de CI.

## Gate 3 - hardware real

Objetivo: perfil local `laboratorio`.

Antes:

```powershell
git switch feat/mikrotik-granular-tools
git pull
cd Skills\MikroTik-MCP
python -m pip install -e .
.\scripts\install-hermes-skill.ps1
hermes gateway restart
hermes mcp test mikrotik
```

Con la allowlist de `HERMES.md`, Hermes debe registrar solo:

- `mikrotik_devices`
- `mikrotik_status`
- `mikrotik_inventory`
- `mikrotik_torch_flows`

Pruebas MCP/hardware:

1. health puntual;
2. CPU 5 s / interval 1;
3. CPU 30 s / interval 1;
4. interfaz real 5 s;
5. interfaz real 30 s;
6. Torch 5 s;
7. session status antes/después para confirmar reuse;
8. gráfico CPU;
9. gráfico interfaz.

Validar en resultados:

- `device=laboratorio`;
- no aparece la IP/hostname de administración como target;
- CPU puntual se presenta como instantánea;
- series contienen timestamps, elapsed, estadísticas y readings;
- contadores acumulados no se presentan como bps;
- Torch contiene únicamente evidencia de flujos observados;
- gráfico y structuredContent corresponden a las mismas lecturas;
- audit JSONL registra tool, params, duración, operación y session telemetry sin secretos.

Host-key pinning:

- laboratorio puede conservar temporalmente compatibilidad sin pin;
- antes de producción debe obtenerse y verificar fuera de banda `host_key_sha256`;
- un pin incorrecto debe fallar con `SSH_HOST_KEY_MISMATCH`.

## Gate 4 - Hermes + Qwen3 Coder 30B

Mantener reasoning/thinking desactivado para el endpoint OpenAI-compatible local usado en este proyecto.

Usar un chat nuevo para evitar que valores previos parezcan datos actuales.

Prompts de aceptación:

```text
¿Cómo está el CPU del MikroTik laboratorio?
```

Esperado: `mikrotik_status(section="health")`.

```text
Monitorea el CPU del MikroTik laboratorio durante 30 segundos.
```

Esperado: `mikrotik_status(section="health", duration=30, interval=1)`.

```text
Grafica el CPU del MikroTik laboratorio durante 30 segundos.
```

Esperado: misma llamada temporal con `chart=true`. No Terminal, subagente ni puntos inventados.

```text
Monitorea el tráfico de ether1 durante 30 segundos.
```

Esperado: `mikrotik_status(section="interfaces", interface="ether1", duration=30, interval=1)`.

```text
¿Quién está generando tráfico ahora en ether1?
```

Esperado: `mikrotik_torch_flows`.

```text
Vuelve a consultar el CPU ahora.
```

Esperado: una llamada MCP nueva. No reutilizar una lectura anterior.

Criterios de interpretación:

- no inferir estabilidad fuera de la ventana;
- no inferir causa de CPU desde Torch sin evidencia adicional;
- no afirmar ausencia de tráfico malicioso;
- no llamar WAN/Internet a una interfaz sin evidencia;
- si ImageContent no se renderiza, conservar y reportar las lecturas reales.

## Evidencia a conservar

Para cada gate registrar:

- commit SHA probado;
- fecha/hora;
- resultado;
- número de tests;
- duración aproximada;
- errores o warnings relevantes;
- para hardware/Hermes, correlation IDs del audit log cuando ayuden al diagnóstico.

Las credenciales, IP de administración, username, secretos DPAPI y contenido sensible de perfiles no deben copiarse a este documento ni al repositorio.


### Hallazgo de rendimiento Hermes/Qwen durante Gate 3

En la validación Windows + Hermes + Qwen local se confirmó que `mikrotik_devices` funciona y devuelve únicamente el perfil lógico `laboratorio`, pero el turno del agente presenta una sobrecarga significativa antes/después de la llamada MCP:

- prueba `-t terminal`: ~7.09 s;
- prueba con toolsets completos y `--ignore-rules`: ~90.87 s;
- prueba `-t mikrotik` con las cuatro tools: ~67.34 s;
- prueba temporal con solo `mikrotik_devices`: ~129.87 s;
- usage de una ejecución `-t mikrotik --ignore-rules`: 15,489 input tokens, 115 output tokens, 15,604 total tokens y 4 llamadas API;
- `auxiliary` fue 0 en esa ejecución, por lo que la generación de títulos no explica esa sobrecarga residual;
- el endpoint OpenAI-compatible directo sí responde correctamente a chat, streaming, tool calling y streaming+tool calling.

Conclusión provisional: la funcionalidad MCP está operativa, pero Gate 3 queda bloqueado por latencia del loop/prompt de Hermes-Qwen. No atribuir la demora al SSH, RouterOS o a la ejecución de `mikrotik_devices` hasta analizar las cuatro llamadas principales y su uso/latencia individual.



### Confirmación: degradación del backend con contexto grande

Se ejecutó una prueba directa contra el endpoint OpenAI-compatible del proveedor local, sin Hermes, sin OpenCode, sin MCP y sin RouterOS. La petición usó `qwen3-coder:30b`, `stream=false`, `max_tokens=5` y un contexto sintético grande de aproximadamente 15k unidades `"test "`.

Resultado observado en 2026-10-14:

- la llamada directa agotó `TimeoutSec 180`;
- tiempo medido por el cliente: ~180.14 s;
- no se recibió objeto `response` ni usage porque el request terminó por timeout.

Esto contrasta con las pruebas directas pequeñas del mismo endpoint, que sí responden correctamente, y con los registros históricos donde prompts de ~15k tokens respondían en pocos segundos. Por tanto, el bloqueo actual de Gate 3 se clasifica provisionalmente como degradación/regresión externa del backend Basecamp/Qwen para contextos grandes, no como un fallo demostrado del MCP MikroTik, SSH o RouterOS.

No modificar los schemas ni reducir funcionalidad del MCP para compensar este problema hasta que el backend vuelva a procesar contextos de tamaño agente en tiempos razonables.



### Prueba escalonada de contexto: fallo desde el primer nivel

Se ejecutó una prueba directa adicional contra el endpoint local, nuevamente sin Hermes/OpenCode/MCP, con `qwen3-coder:30b`, `stream=false`, `max_tokens=5` y contexto sintético basado en repeticiones de `"test "`.

Primer escalón:

- target sintético: 1000 repeticiones;
- timeout cliente: 60 s;
- resultado: `TIMEOUT/ERROR`;
- tiempo observado: ~60.02 s;
- no hubo usage del proveedor porque la solicitud no completó.

El umbral de degradación actual está por debajo de este primer nivel de prueba. Se requiere una segunda pasada con tamaños menores para localizar el punto de quiebre. Este resultado refuerza que la regresión está en el backend/model runtime y no en el MCP MikroTik.

