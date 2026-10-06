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

También puede ejecutarse localmente cuando exista Docker:

```powershell
cd Skills\MikroTik-MCP
python -m pytest -q -m integration
```

El fixture levanta un RouterOS temporal mediante Docker/QEMU, inicializa únicamente la contraseña del sandbox y ejecuta después consultas read-only.

Criterios:

- SSH del sandbox disponible;
- inventario health real parseable;
- CPU temporal real con valores 0–100;
- `actual_duration_seconds >= requested_duration_seconds`;
- interfaz `ether1` medible mediante `/interface monitor-traffic ether1 once`;
- tasas RX/TX no negativas;
- no se usan comandos RouterOS arbitrarios desde el MCP.

Si este gate falla, no continuar a hardware real hasta clasificar si el fallo es código, imagen RouterOS, Docker/QEMU o infraestructura de CI.

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
