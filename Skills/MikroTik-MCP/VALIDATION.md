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



### Baseline mínimo también agotó timeout

Después de dejar de usar Hermes/OpenCode y antes de continuar la prueba escalonada, se ejecutó una llamada directa mínima al endpoint con `qwen3-coder:30b`: un único mensaje de usuario `"Responde únicamente OK"`, `stream=false` y `max_tokens=5`.

Resultado observado:

- timeout cliente: 30 s;
- tiempo medido: ~30.11 s;
- no hubo respuesta ni usage del proveedor.

Esto invalida temporalmente la interpretación del test de 1000 repeticiones como umbral de contexto: el backend/modelo está degradado incluso con un prompt mínimo. Se suspende la prueba de escalado hasta confirmar que el baseline pequeño vuelve a responder.

Siguiente aislamiento recomendado: probar otros modelos expuestos por el mismo endpoint. Si otro modelo responde normalmente, la degradación queda acotada a `qwen3-coder:30b`; si todos fallan, el problema es más amplio en el runtime/servidor.



### Recuperación observada tras cambio temporal de modelo

Después de que `qwen3-coder:30b` agotara timeouts incluso con un prompt mínimo, se ejecutó una petición directa a `qwen2.5-coder:1.5b`, que respondió correctamente (~3.33 s). Inmediatamente después se volvió a probar `qwen3-coder:30b` con el mismo prompt mínimo.

Resultado:

- `qwen3-coder:30b` respondió correctamente en ~1.87 s;
- usage observado: 14 prompt tokens, 2 completion tokens, 16 total tokens;
- respuesta: `OK`.

Interpretación: el problema previo no se considera una degradación permanente demostrada del modelo. El cambio temporal de modelo pudo forzar una descarga/recarga de la instancia, liberar una cola bloqueada o limpiar otro estado transitorio del runtime. La causalidad exacta no puede confirmarse sin acceso al servidor GPU.

Gate 3 puede reanudarse, pero se deben repetir primero una prueba de contexto moderado y una prueba limpia en OpenCode/Hermes antes de atribuir estabilidad al backend.



### Contexto moderado vuelve a responder tras recuperación

Después de recuperar `qwen3-coder:30b` con un prompt mínimo (~1.87 s), se repitió una prueba directa con contexto sintético moderado:

- 1000 repeticiones de `"test "`;
- usage real: 1020 prompt tokens, 2 completion tokens, 1022 total tokens;
- tiempo: ~12.86 s;
- respuesta: `OK`.

Esto confirma que el timeout previo de 1000 repeticiones no representaba un umbral fijo de contexto; ocurrió mientras el runtime/modelo estaba en un estado transitorio degradado. La siguiente validación debe hacerse en OpenCode/Hermes con sesión nueva, sin modificar la skill MikroTik.



### OpenCode: causa aislada en snapshots del workspace

Durante el diagnóstico del cliente OpenCode en Windows se observó que el mismo `qwen3-coder:30b` respondía correctamente en un entorno mínimo, pero OpenCode dentro del repositorio podía quedar bloqueado incluso con un saludo simple.

Datos de aislamiento:

- OpenCode: v2.0.29;
- raíz Git: `F:/proyectos/Tools`;
- archivos tracked: 31;
- archivos untracked no ignorados: 14;
- `git ls-files` y `git status` completan en ~0.1 s;
- no se encontraron `index.lock` bajo el directorio de snapshots de OpenCode;
- al iniciar OpenCode con `OPENCODE_CONFIG_CONTENT='{"snapshot":false}'`, el mismo proyecto respondió normalmente (~2.5 s).

Conclusión: el bloqueo de OpenCode queda aislado al mecanismo/estado de snapshots del workspace en este entorno, no al tamaño del repositorio, al modelo Qwen ni al MCP MikroTik. Se recomienda mantener snapshots deshabilitados temporalmente mientras se valida/actualiza OpenCode y conservar Git como mecanismo de recuperación de cambios.



### OpenCode tool calling: backend confirmado, fallo de compatibilidad en cliente

Se ejecutó una prueba directa contra el endpoint OpenAI-compatible con `qwen3-coder:30b`, definiendo una función `shell(command: string)` y solicitando ejecutar `dir`.

Resultado directo del backend:

- latencia: ~5.02 s;
- `message.content`: vacío;
- `message.tool_calls`: presente;
- tool: `shell`;
- arguments: `{"command":"dir"}`;
- `finish_reason`: `tool_calls`;
- usage: 299 prompt tokens, 22 completion tokens, 321 total tokens.

Por tanto, Basecamp/Qwen/Ollama-compatible entrega correctamente el formato OpenAI de tool calling. Sin embargo, OpenCode 2.0.29, usando `@ai-sdk/openai-compatible`, muestra llamadas equivalentes como texto `<function=shell>...</tool_call>` en lugar de ejecutarlas.

Conclusión: el problema de tool execution queda aislado a la capa de compatibilidad/interpretación de OpenCode para proveedores OpenAI-compatible con Qwen3-Coder, no al modelo ni al MCP MikroTik.



### Responses API confirmada para Basecamp/Qwen

Se probó directamente `POST /v1/responses` contra el endpoint Basecamp con `qwen3-coder:30b`, definiendo una función `shell(command: string)`.

Resultado:

- latencia: ~2.01 s;
- respuesta completada correctamente;
- `output[0].type`: `function_call`;
- `output[0].name`: `shell`;
- arguments: `{"command":"dir"}`;
- usage: 299 input tokens, 22 output tokens, 321 total tokens.

Esto demuestra que el backend soporta OpenAI Responses API con function calling. Dado que OpenCode 2.0.29 muestra tool calls como texto usando `@ai-sdk/openai-compatible` + `/v1/chat/completions`, la siguiente prueba recomendada es configurar temporalmente OpenCode con `@ai-sdk/openai` para usar `/v1/responses`, manteniendo `snapshot:false`.



### OpenCode recuperado: Responses API ejecuta tools correctamente

Se validó OpenCode 2.0.29 con una configuración temporal usando `@ai-sdk/openai` contra el mismo Basecamp y `qwen3-coder:30b`, manteniendo `snapshot:false`.

Resultado observado:

- saludo simple: respuesta normal (~2.8 s);
- petición para revisar el directorio: OpenCode ejecutó una tool real (`$ dir`);
- la salida del shell fue capturada y utilizada para redactar la respuesta final;
- ya no aparecieron etiquetas literales `<function=shell>...</tool_call>`.

Conclusión:

1. `snapshot:false` corrige el bloqueo/hang del workspace en este entorno Windows.
2. `@ai-sdk/openai` + `/v1/responses` corrige la ejecución de tools con `qwen3-coder:30b`.
3. El modelo y Basecamp quedan validados para chat y tool calling estructurado.
4. El fallo previo estaba en la combinación OpenCode 2.0.29 + `@ai-sdk/openai-compatible` sobre `/v1/chat/completions`.

Recomendación operativa: mantener OpenCode con `snapshot:false` y el proveedor `@ai-sdk/openai` para este backend mientras se usa Qwen3-Coder 30B.



### OpenCode run normal también reproduce tool call como texto

Con la configuración global mostrando `snapshot:false` y `@ai-sdk/openai`, se probó `opencode run` normal (sin `--standalone`) en el proyecto MikroTik-MCP.

Resultados:

- chat simple: `OK` en ~2.84 s;
- petición que requiere shell: terminó en ~6.07 s pero imprimió literalmente `<function=shell>...` en lugar de ejecutar la herramienta.

Esto descarta que el fallo esté limitado a la TUI o a `--standalone`. El comportamiento coincide con incidencias conocidas de OpenCode con modelos locales/Ollama donde tool calls válidos del backend terminan expuestos como texto en ciertos caminos del runtime.

La API directa de Basecamp continúa devolviendo function calling válido tanto en `/v1/chat/completions` como en `/v1/responses`. Por tanto, no modificar el modelo ni el MCP para compensar este problema del cliente.



### OpenCode: tool calling operativo, pero sobreuso de tools

Con la configuración temporal que sí ejecuta tools, se midió una petición controlada:

`Usa la herramienta shell para ejecutar exactamente dir. Después responde únicamente OK.`

Resultado:

- OpenCode ejecutó `dir` correctamente;
- el modelo realizó además una llamada de escritura y creó `OK.txt`, aunque no se solicitó;
- finalmente respondió `OK`;
- tiempo total: ~27.87 s.

La medición queda contaminada por una tool extra no solicitada. Para medir el costo real de un único ciclo shell -> resultado -> respuesta, la siguiente prueba debe restringir el agente a `shell` únicamente mediante permisos V2.



### Prueba de restricción shell-only descartada por loop

Se intentó restringir una ejecución de OpenCode a un único ciclo de shell y dos pasos de modelo mediante un overlay temporal. La ejecución no quedó correctamente limitada:

- el modelo ejecutó `dir`;
- luego intentó invocar una herramienta de pregunta/interacción;
- `opencode run` rechazó la pregunta por ser no interactivo;
- el modelo volvió a ejecutar `dir`;
- el patrón se repitió, generando un loop.

Dado que una herramienta distinta de shell siguió disponible y el límite esperado de pasos no detuvo el ciclo, esta prueba no se considera válida para medir rendimiento. El overlay de permisos/steps debe considerarse no aplicado o no compatible con la ruta/configuración utilizada en OpenCode 2.0.29.

Acción: abortar con Ctrl+C, limpiar variables temporales de OpenCode y no usar este resultado para estimar latencia.



### Gate 3 - preflight real en Windows/Hermes

Preflight ejecutado en la estación Windows antes de consultar hardware real:

- rama local: `feat/mikrotik-granular-tools`;
- working tree limpio;
- HEAD observado: `a2a8c64`;
- `hermes mcp test mikrotik`: conexión correcta;
- servidor MCP: 5 tools descubiertas (incluye `mikrotik_full` internamente);
- allowlist efectiva de Hermes: exactamente 4 tools:
  - `mikrotik_devices`
  - `mikrotik_status`
  - `mikrotik_inventory`
  - `mikrotik_torch_flows`
- `mikrotik_full` no está incluida en la allowlist de Hermes.

El preflight de Gate 3 se considera aprobado. Siguiente paso: validar `mikrotik_devices` contra la configuración real sin exponer IP, usuario ni credenciales.



### Gate 3.1 - mikrotik_devices directo aprobado

Se ejecutó `mikrotik_devices()` directamente desde Python, sin Hermes ni Qwen.

Resultado observado:

- `status: ok`;
- `operation: devices`;
- `device_count: 1`;
- perfil lógico: `laboratorio`;
- `default_interface: ether1`;
- `host_key_pinned: false`;
- `session_connected: false`.

No se expusieron IP/hostname de administración, username ni secretos. Gate 3.1 queda aprobado.



### Gate 3.2 - health real por SSH aprobado

Se ejecutó `health --device laboratorio` directamente desde Python/CLI, sin Hermes ni Qwen.

Resultado:

- `status: ok`;
- conexión administrada por Session Manager;
- RouterOS: `7.24.4 (stable)`;
- modelo: `CRS112-8P-4S`;
- arquitectura: `mipsbe`;
- CPU instantáneo observado: `100%`;
- memoria libre observada: `83.5 MiB` de `128.0 MiB`;
- storage libre observado: ~`3036 KiB` de `16 MiB`;
- firmware RouterBOARD actual: `7.22`;
- upgrade-firmware reportado: `7.24.4`;
- backend elapsed: ~`6.89 s`;
- extremo a extremo medido desde PowerShell: ~`7.69 s`;
- sesión conectada correctamente;
- primera conexión, sin reutilización previa.

La lectura de CPU es point-in-time y no demuestra carga sostenida. Siguiente paso: muestreo temporal real de CPU.



### Gate 3.3 - CPU temporal real de 5 s aprobado

Se ejecutó `cpu_sample --device laboratorio --duration 5` directamente desde Python/CLI.

Resultado observado:

- ventana solicitada: 5 s;
- duración real: 5.0 s;
- intervalo: 1 s;
- muestras: 5;
- timestamps UTC presentes;
- lecturas en aproximadamente 0, 1, 2, 3 y 4 s;
- mínimo: 26%;
- máximo: 47%;
- promedio: 36.4%;
- mediana: 33%;
- primera muestra: 47%;
- última muestra: 26%;
- backend elapsed: ~9.21 s;
- extremo a extremo desde PowerShell: ~10.12 s.

La ventana cerró exactamente al tiempo solicitado y no sobrepasó la duración. La lectura instantánea anterior de 100% no representa carga sostenida en esta ventana posterior de 5 s.

`session_reused: false` es esperado en esta prueba porque cada invocación de `python -m mikrotik_skill.cli` crea un proceso nuevo. La reutilización de sesión debe validarse con dos operaciones dentro del mismo proceso Python.



### Gate 3.4 - CPU 30 s + reutilización SSH aprobados

Se ejecutaron dos operaciones dentro del mismo proceso Python:

1. `health --device laboratorio`
2. `cpu_sample --device laboratorio --duration 30 --interval 1`

Resultados:

- primera operación:
  - `status: ok`;
  - CPU instantáneo observado: 96%;
  - `session_reused: false`;
  - `session_reuse_count: 0`;
  - `session_connected: true`;
  - elapsed backend: ~4.88 s.

- segunda operación:
  - `status: ok`;
  - duración solicitada: 30 s;
  - duración real: 30.0 s;
  - muestras: 30;
  - mínimo: 22%;
  - máximo: 96%;
  - promedio: 28.77%;
  - mediana: 26%;
  - primera muestra: 96%;
  - última muestra: 25%;
  - `session_reused: true`;
  - `session_reuse_count: 1`;
  - `session_connected: true`;
  - elapsed backend: ~30.00 s.

Tiempo extremo a extremo del bloque completo desde PowerShell: ~35.66 s.

Conclusiones de aceptación:

- la ventana temporal respeta exactamente los 30 s solicitados;
- la sesión SSH persistente se reutiliza dentro del mismo proceso;
- el pico inicial de CPU no representa carga sostenida durante la ventana; no se atribuye causalidad sin evidencia adicional.



### Gate 3.5 - tráfico real de interfaz 5 s aprobado

Se ejecutó `interface_sample --device laboratorio --interface ether1 --duration 5`.

Resultado:

- `status: ok`;
- fuente: `/interface monitor-traffic ether1 once`;
- duración solicitada: 5 s;
- duración real: ~5.001 s;
- muestras: 5;
- timestamps UTC presentes;
- RX:
  - mínimo: 125300 bps;
  - máximo: 304900 bps;
  - promedio: 255000 bps;
  - mediana: 272900 bps;
- TX:
  - mínimo: 36500 bps;
  - máximo: 167600 bps;
  - promedio: 103420 bps;
  - mediana: 87500 bps;
- RX packets/s promedio: 48.8;
- TX packets/s promedio: 38.6;
- queue drops observados: 0;
- backend elapsed: ~9.21 s;
- extremo a extremo desde PowerShell: ~10.03 s;
- sesión conectada correctamente.

La medición corresponde a tasas actuales observadas en la ventana y no a contadores acumulados.

