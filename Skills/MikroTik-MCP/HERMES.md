# Integración con Hermes Agent

## Requisitos validados

- Hermes Agent v0.21.3.
- MCP Python SDK 2.3.0.
- Servidor MCP local por stdio.
- Python 3.11+ con el paquete `mikrotik-mcp-skill` instalado (editable durante desarrollo).
- Qwen3 Coder 30B con reasoning/thinking desactivado para el endpoint local usado en laboratorio.

## Diseño

Hermes y MCP tienen responsabilidades distintas:

- El **Hermes Skill** `mikrotik-operator` contiene procedimiento, routing de intención y reglas de interpretación.
- El **MCP server** ejecuta mediciones exactas, valida parámetros y devuelve evidencia estructurada.
- Terminal/subagentes no deben recrear funciones que el MCP ya ofrece.

Esto evita cargar descripciones MCP enormes y reduce la ambigüedad de selección en modelos locales.

## Ruta efectiva de configuración en Windows

No asumir que Hermes usa siempre `%USERPROFILE%\.hermes`. Si la variable `HERMES_HOME` está definida, esa ruta es autoritativa para la configuración y estado de Hermes.

Resolverla primero con:

```powershell
Get-ChildItem Env:HERMES_HOME -ErrorAction SilentlyContinue
where.exe hermes
```

El archivo MCP efectivo se busca en:

```text
$env:HERMES_HOME\config.yaml
```

Esto evita editar un `config.yaml` inexistente en el perfil del usuario mientras Hermes sigue leyendo otra configuración. El Python usado por el MCP puede ser distinto del entorno interno de Hermes; se valida por separado con:

```powershell
python -c "import sys, mikrotik_skill; print(sys.executable); print(mikrotik_skill.__file__)"
```

## Herramientas MCP

Superficie completa del servidor:

- `mikrotik_devices`
- `mikrotik_status`
- `mikrotik_inventory`
- `mikrotik_torch_flows`
- `mikrotik_full`

Para Qwen local se recomienda inicialmente **no exponer `mikrotik_full`**. Hermes soporta una allowlist por servidor:

```yaml
mcp_servers:
  mikrotik:
    command: F:\proyectos\Inst_Tocoa\.venv\Scripts\python.exe
    args:
      - -m
      - mikrotik_skill.mcp_server
    env:
      PYTHONPATH: F:\proyectos\Tools\Skills\MikroTik-MCP
    enabled: true
    timeout: 150
    connect_timeout: 30
    supports_parallel_tool_calls: false
    tools:
      include:
        - mikrotik_devices
        - mikrotik_status
        - mikrotik_inventory
        - mikrotik_torch_flows
      resources: false
      prompts: false
```

`include` limita las herramientas nativas que Hermes registra. Desactivar `resources` y `prompts` evita wrappers que este servidor no necesita. `supports_parallel_tool_calls: false` evita que el modelo lance dos diagnósticos temporales simultáneos contra el mismo proceso/RouterOS. El timeout de 150 s deja margen para la ventana máxima de muestreo de 120 s y el tiempo de transporte.

Durante desarrollo, `PYTHONPATH` sigue siendo válido. El proyecto ya tiene `pyproject.toml`; tras instalarlo en editable se puede migrar a:

```powershell
F:\proyectos\Inst_Tocoa\.venv\Scripts\python.exe -m pip install -e F:\proyectos\Tools\Skills\MikroTik-MCP
```

y después eliminar el `PYTHONPATH` del servidor si se desea.

## Companion Skill

Instalar:

```powershell
cd F:\proyectos\Tools\Skills\MikroTik-MCP
.\scripts\install-hermes-skill.ps1
```

Destino:

```text
%USERPROFILE%\.hermes\skills\networking\mikrotik-operator
```

El skill contiene:

- regla de dato fresco para "ahora"/"actual"/"vuelve a revisar";
- CPU temporal → `mikrotik_status(section=health, duration=N)`;
- interfaz temporal → `mikrotik_status(section=interfaces, interface=..., duration=N)`;
- gráfico → misma medición con `chart=true`;
- Torch solo para hosts/protocolos/puertos/flujos;
- prohibición de inventar muestras o reemplazar una capacidad MCP con un subagente.

## Semántica de series temporales

Una respuesta temporal válida conserva en `structuredContent`:

- `requested_duration_seconds`;
- `actual_duration_seconds`;
- `interval_seconds`;
- `sample_count`;
- `statistics`;
- `readings[]`.

Cada reading incluye `timestamp` UTC y `elapsed_seconds`. Qwen debe interpretar únicamente la ventana devuelta. Si se perdieron slots porque SSH tardó más que el intervalo, el backend no inventa puntos ni ejecuta una ráfaga de consultas para rellenarlos.

## Verificación

Después de un cambio MCP:

```powershell
hermes gateway restart
hermes mcp test mikrotik
```

Con la allowlist recomendada, Hermes debe registrar cuatro herramientas para el agente. El servidor MCP sigue anunciando cinco herramientas nativas.

Importante: `hermes mcp test mikrotik` hace un probe directo del servidor y muestra el catálogo bruto devuelto por `tools/list`; por eso puede mostrar `Tools discovered: 5` e incluir `mikrotik_full` aunque `tools.include` esté correctamente configurado. La allowlist se aplica durante el registro runtime de herramientas para el agente/modelo, no durante ese probe de diagnóstico. Para validar la política se debe comprobar la superficie efectiva en una sesión Hermes y/o la selección real de herramientas, no exigir que `hermes mcp test` baje a cuatro.

Después de cambiar solamente filtros MCP, Hermes también documenta `/reload-mcp` como mecanismo de recarga en una sesión compatible.

## Auditoría

Cada llamada pública genera un evento JSONL redacted en:

```text
%APPDATA%\MikroTikSkill\logs\mcp-audit.jsonl
```

Esto permite comprobar exactamente qué herramienta eligió Qwen, los parámetros, la duración y la operación backend, en lugar de depender solo de "Used N tools" en la GUI.

## Resultados

Las consultas compactas devuelven:

- `TextContent` breve/estructurado para el modelo;
- `structuredContent` como fuente de verdad.

Las series temporales con `chart=true` incluyen además `ImageContent` PNG. La renderización visual depende de la capacidad del cliente Hermes; aunque la imagen no se muestre, las lecturas y estadísticas reales siguen disponibles.

Los resultados grandes, como inventario completo, evitan duplicar todo el payload en texto.

La dirección de administración del perfil no forma parte del resultado MCP. Para tráfico, el equipo se identifica mediante el nombre lógico del perfil; las direcciones origen/destino devueltas por Torch sí son parte de la evidencia observada.

## Problemas observados y mitigación

Durante las pruebas Qwen confundió:

- CPU temporal con Torch;
- CPU temporal con una lectura puntual;
- una petición de gráfico con un subagente/Terminal.

La mitigación ya no depende de frases mágicas:

1. `mikrotik_status` concentra estado puntual y series temporales.
2. El Hermes Skill contiene routing procedural explícito.
3. Torch tiene semántica separada.
4. El backend calcula las estadísticas.
5. El chart renderer usa exactamente la misma serie medida.
6. La auditoría permite revisar la selección real de herramientas.

## Secuencia de aceptación

Antes de usar esta rama como estable:

1. suite aislada verde;
2. sandbox RouterOS verde;
3. prueba en hardware real;
4. prueba de selección natural con Hermes/Qwen;
5. revisión del audit log.

Los comandos y prompts de aceptación están en `VALIDATION.md`.
